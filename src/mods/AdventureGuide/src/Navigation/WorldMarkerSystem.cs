using AdventureGuide.Config;
using AdventureGuide.Data;
using AdventureGuide.State;
using UnityEngine;

namespace AdventureGuide.Navigation;

/// <summary>
/// Computes and renders world markers for quest-relevant NPCs and objectives,
/// and optionally respawn timers at every spawn point of the zone.
/// Markers are billboard quads in 3D space with depth occlusion.
///
/// Each spawn a quest references gets its own marker from live game state:
/// - Expected NPC alive → quest marker (!, ?, objective)
/// - Dead / respawning → clock + respawn timer
/// - Night-locked → moon + time info
/// - Directly-placed dead → clock + "re-enter zone"
/// - Withheld, still populating, or another NPC alive → no marker
///
/// With ShowAllRespawnTimers, every other SpawnPoint whose NPC died or
/// despawned gets the same clock or moon marker.
///
/// When several quests reference the same spawn, MarkerType order decides
/// which marker shows.
/// </summary>
public sealed class WorldMarkerSystem
{
    private const float StaticHeightOffset = 2.5f;
    private const float LiveHeightAboveCollider = 0.8f;
    private const float CorpseHeightOffset = 1.5f;
    private const string RespawnDueText = "Respawning...";
    private const string RegenerationDueText = "Regenerating...";

    private readonly GuideData _data;
    private readonly QuestStateTracker _state;
    private readonly SpawnPointBridge _bridge;
    private readonly MarkerPool _pool;
    private readonly GuideConfig _config;
    private readonly LootScanner _lootScanner;

    // Cached marker state — rebuilt on dirty
    private readonly List<MarkerEntry> _markers = new();
    private readonly Dictionary<IntentKey, int> _intentIndex = new();

    // SpawnPoints a quest marker covers during the current rebuild, by
    // instance ID. Respawn timers skip them.
    private readonly HashSet<int> _questSpawnPoints = new();

    // Ground pickups present in the scene, found once per rebuild when a
    // quest item has an itembag source. A pickup is destroyed when taken.
    private ItemBag[]? _itemBags;
    private string _lastScene = "";

    // Set by every scene load, including a reload of the scene already shown
    // (death respawn or recall inside the bind zone). The scene name alone
    // cannot detect such a reload, but it replaces every SpawnPoint and NPC.
    private bool _sceneLoaded = true;
    private bool _enabled;
    private bool _configDirty;
    private bool _spawnDirty;
    private int _spawnResetFrame = -1;
    private int _lastHour = -1;
    private int _lastStateVersion = -1;
    private int _lastLootVersion = -1;

    public bool Enabled
    {
        get => _enabled;
        set
        {
            if (_enabled == value)
                return;
            _enabled = value;
            if (value)
                _configDirty = true; // force RebuildMarkers on next Update
            else
                _pool.DeactivateAll();
        }
    }

    public WorldMarkerSystem(
        GuideData data,
        QuestStateTracker state,
        SpawnPointBridge bridge,
        LootScanner lootScanner,
        GuideConfig config
    )
    {
        _data = data;
        _state = state;
        _bridge = bridge;
        _lootScanner = lootScanner;
        _config = config;
        _pool = new MarkerPool();

        // Rebuild markers when any marker config changes
        config.ShowAllRespawnTimers.SettingChanged += OnConfigChanged;
        config.MarkerScale.SettingChanged += OnConfigChanged;
        config.IconSize.SettingChanged += OnConfigChanged;
        config.SubTextSize.SettingChanged += OnConfigChanged;
        config.IconYOffset.SettingChanged += OnConfigChanged;
        config.SubTextYOffset.SettingChanged += OnConfigChanged;
    }

    /// <summary>
    /// Call each frame from Plugin.Update. Rebuilds markers when quest
    /// state or scene changes. Updates live NPC positions, respawn timers,
    /// and distance fade every frame.
    /// </summary>
    public void Update(string currentScene)
    {
        if (!_enabled || GameData.PlayerControl == null || !MarkerFonts.IsReady)
            return;
        // LootScanner is updated by Plugin.Update before this method,
        // ensuring fresh corpse/chest data regardless of marker visibility.
        // Loot markers come only from rebuilds, so every rescan rebuilds,
        // such as after a loot window returns a corpse's remaining drops.

        int hour = GameData.Time.hour;
        bool sceneChanged = _sceneLoaded || currentScene != _lastScene;
        bool spawnPointsChanged = !sceneChanged && _bridge.HasNewRegistrations;
        bool hourChanged = hour != _lastHour;
        bool stateChanged = _state.Version != _lastStateVersion;
        bool lootChanged = _lootScanner.Version != _lastLootVersion;
        bool resetReady = SpawnMarkerPolicy.ResetReady(_spawnResetFrame, Time.frameCount);
        bool needsRebuild =
            sceneChanged
            || spawnPointsChanged
            || hourChanged
            || stateChanged
            || lootChanged
            || _configDirty
            || _spawnDirty
            || resetReady;
        if (stateChanged)
            _lastStateVersion = _state.Version;
        _lastLootVersion = _lootScanner.Version;
        _configDirty = false;
        _spawnDirty = false;
        if (resetReady)
            _spawnResetFrame = -1;
        _lastHour = hour;

        if (needsRebuild)
        {
            _lastScene = currentScene;
            if (sceneChanged)
            {
                _sceneLoaded = false;
                _bridge.Rebuild();
            }
            else if (spawnPointsChanged)
                _bridge.IndexNewRegistrations();
            RebuildMarkers(currentScene);
        }

        UpdateLiveState();
    }

    private void OnConfigChanged(object sender, System.EventArgs e) => _configDirty = true;

    /// <summary>Signal that an NPC died. Triggers marker rebuild next frame.</summary>
    public void MarkSpawnDirty() => _spawnDirty = true;

    /// <summary>Wait for deferred NPC destruction before rebuilding a reset point.</summary>
    public void OnSpawnPointReset() => _spawnResetFrame = Time.frameCount;

    /// <summary>
    /// Index an NPC that started after the scene loaded, such as a scene
    /// object an event switched on, and rebuild markers next frame.
    /// </summary>
    public void OnNpcStarted(NPC npc)
    {
        _bridge.OnNpcStarted(npc);
        _spawnDirty = true;
    }

    /// <summary>
    /// Record the NPC a SpawnPoint just spawned and rebuild markers next
    /// frame. Called from the SpawnNPC postfix.
    /// </summary>
    public void OnNPCSpawned(SpawnPoint spawnPoint)
    {
        _bridge.RecordSpawn(spawnPoint);
        _spawnDirty = true;
    }

    /// <summary>
    /// Drop every marker on scene load. The loaded scene replaces all
    /// SpawnPoints and NPCs the markers reference, so the next gameplay
    /// Update re-indexes the scene before it builds markers again.
    /// </summary>
    public void OnSceneLoaded()
    {
        _pool.DeactivateAll();
        _markers.Clear();
        _intentIndex.Clear();
        _questSpawnPoints.Clear();
        _bridge.OnSceneLoaded();
        _sceneLoaded = true;
    }

    /// <summary>One line per current marker, for DebugAPI.DumpMarkers.</summary>
    internal string Describe()
    {
        var sb = new System.Text.StringBuilder();
        sb.Append("Markers: ").Append(_markers.Count).Append('\n');
        foreach (var m in _markers)
        {
            sb.Append(m.Type)
                .Append(m.RespawnOnly ? " (respawn)" : "")
                .Append(" | ")
                .Append(m.DisplayName)
                .Append(" | ")
                .Append((m.SubText ?? "").Replace('\n', '/'))
                .Append(" | ")
                .Append(m.LiveSpawnPoint != null ? m.LiveSpawnPoint.name : "-")
                .Append('\n');
        }
        return sb.ToString();
    }

    public void Destroy()
    {
        _config.ShowAllRespawnTimers.SettingChanged -= OnConfigChanged;
        _config.MarkerScale.SettingChanged -= OnConfigChanged;
        _config.IconSize.SettingChanged -= OnConfigChanged;
        _config.SubTextSize.SettingChanged -= OnConfigChanged;
        _config.IconYOffset.SettingChanged -= OnConfigChanged;
        _config.SubTextYOffset.SettingChanged -= OnConfigChanged;
        _pool.Destroy();
    }

    // ── Marker computation ────────────────────────────────────────

    private void RebuildMarkers(string currentScene)
    {
        _markers.Clear();
        _intentIndex.Clear();
        _questSpawnPoints.Clear();
        _itemBags = null;

        foreach (var quest in _data.All)
        {
            bool isActive = _state.IsActionable(quest);
            bool isCompleted = _state.IsCompleted(quest);
            bool isRepeatable = quest.Flags is { Repeatable: true };

            // Quest givers: available quests (not active, not completed, or repeatable+completed)
            if (!isActive && (!isCompleted || isRepeatable))
                CollectQuestGiverMarkers(quest, currentScene, isRepeatable);

            if (!isActive)
                continue;

            // Turn-in markers and objectives: only for active quests
            CollectTurnInMarkers(quest, currentScene, isRepeatable);
            CollectObjectiveMarkers(quest, currentScene);
        }

        CollectLootContainerMarkers();
        if (_config.ShowAllRespawnTimers.Value)
            CollectRespawnTimerMarkers();

        // Apply to pool
        _pool.SetActiveCount(_markers.Count);
        for (int i = 0; i < _markers.Count; i++)
        {
            var m = _markers[i];
            var instance = _pool.Get(i);
            Configure(instance, m);
            instance.SetPosition(m.Position);
            instance.SetActive(true);
        }
    }

    /// <summary>
    /// Quest giver markers: ! over NPCs that can assign quests the player
    /// hasn't started (or repeatable quests they've completed).
    /// </summary>
    private void CollectQuestGiverMarkers(QuestEntry quest, string scene, bool repeatable)
    {
        if (quest.Acquisition == null)
            return;

        // Check chain prerequisites — skip if any isn't completed.
        // Prerequisites with an Item field are item-acquisition chains (needed
        // to complete the quest, not to start it) and don't gate availability.
        if (quest.Prerequisites != null)
        {
            foreach (var prereq in quest.Prerequisites)
            {
                if (prereq.Item != null)
                    continue;
                var prereqQuest = _data.GetByStableKey(prereq.QuestKey);
                if (prereqQuest == null || !_state.IsCompleted(prereqQuest))
                    return;
            }
        }

        foreach (var acq in quest.Acquisition)
        {
            if (acq.SourceType != "character" || acq.SourceStableKey == null)
                continue;

            var questType = MarkerDecision.GetQuestGiverType(repeatable);
            string? subText = acq.Keyword != null ? $"Say '{acq.Keyword}'" : "Talk to";
            string displayName = acq.SourceName ?? quest.DisplayName;

            EmitPerSpawnMarkers(acq.SourceStableKey, scene, displayName, questType, subText);
        }
    }

    /// <summary>
    /// Turn-in markers: ? over NPCs that accept quest item turn-ins.
    /// Gold when all items collected, grey when items still needed.
    /// </summary>
    private void CollectTurnInMarkers(QuestEntry quest, string scene, bool repeatable)
    {
        if (quest.Completion == null)
            return;

        bool hasAllItems = HasAllRequiredItems(quest);

        foreach (var comp in quest.Completion)
        {
            if (comp.SourceType != "character" || comp.SourceStableKey == null)
                continue;

            MarkerType questType = MarkerDecision.GetTurnInType(hasAllItems, repeatable);

            string subText = MarkerTextFormatter.FormatTurnInText(quest, comp);
            string displayName = comp.SourceName ?? quest.DisplayName;

            EmitPerSpawnMarkers(comp.SourceStableKey, scene, displayName, questType, subText);
        }
    }

    /// <summary>
    /// Objective markers: target icons over current step targets and
    /// drop sources for collect steps. Shows progress for collect steps.
    /// </summary>
    private void CollectObjectiveMarkers(QuestEntry quest, string scene)
    {
        if (quest.Steps == null)
            return;

        int currentIdx = StepProgress.GetCurrentStepIndex(quest, _state, _data);
        if (currentIdx < 0 || currentIdx >= quest.Steps.Count)
            return;

        var step = quest.Steps[currentIdx];

        // When the current step is complete_quest, resolve to the sub-quest's
        // actionable step so we emit markers for its target and item sources.
        var (resolved, resolvedQuest) = StepProgress.ResolveActiveStep(step, quest, _state, _data);
        bool hasSubQuest = resolved != step && resolvedQuest != null;

        // Current step target (or resolved sub-quest step target)
        EmitStepTargetMarker(step, scene);
        if (hasSubQuest)
            EmitStepTargetMarker(resolved!, scene);

        // NPC sources for ALL uncollected required items (not just current step)
        EmitItemSourceMarkers(quest, scene);
        if (hasSubQuest)
            EmitItemSourceMarkers(resolvedQuest!, scene);
    }

    private void EmitStepTargetMarker(QuestStep step, string scene)
    {
        if (
            step.Location != null
            && string.Equals(step.Location.Scene, scene, System.StringComparison.OrdinalIgnoreCase)
        )
        {
            TryAddMarker(
                new IntentKey(step.Location.StableKey),
                new MarkerEntry
                {
                    Position =
                        new Vector3(step.Location.X, step.Location.Y, step.Location.Z)
                        + Vector3.up * StaticHeightOffset,
                    Type = MarkerType.Objective,
                    DisplayName = step.TargetName ?? step.Description,
                    SubText = MarkerTextFormatter.FormatStepActionText(step),
                }
            );
        }

        if (step.TargetKey != null && step.TargetType == "character")
        {
            EmitPerSpawnMarkers(
                step.TargetKey,
                scene,
                step.TargetName ?? step.Description,
                MarkerType.Objective,
                MarkerTextFormatter.FormatStepActionText(step)
            );
        }
    }

    private void EmitItemSourceMarkers(QuestEntry quest, string scene)
    {
        if (quest.RequiredItems == null)
            return;

        foreach (var ri in quest.RequiredItems)
        {
            int have = _state.CountItem(ri.ItemStableKey);
            if (have >= ri.Quantity)
                continue;

            string progress = $"{have}/{ri.Quantity} {ri.ItemName}";

            if (ri.Sources == null)
                continue;
            foreach (var src in ri.Sources)
                EmitItemSourceMarker(src, ri, scene, progress);
        }
    }

    private void EmitItemSourceMarker(
        ItemSource source,
        RequiredItemInfo item,
        string scene,
        string progress
    )
    {
        if (
            source.RequiredQuestDBNames != null
            && !source.RequiredQuestDBNames.TrueForAll(_state.IsGameQuestCompleted)
        )
            return;

        if (source.SourceKey != null)
        {
            if (PositionedSource.TryParse(source.SourceKey, out var positioned))
                EmitPositionedSourceMarker(
                    source.SourceKey,
                    positioned,
                    source.Name ?? item.ItemName,
                    scene,
                    progress
                );
            else
                EmitPerSpawnMarkers(
                    source.SourceKey,
                    scene,
                    source.Name ?? item.ItemName,
                    MarkerType.Objective,
                    progress
                );
        }

        if (source.Children == null)
            return;
        foreach (var child in source.Children)
            EmitItemSourceMarker(child, item, scene, progress);
    }

    /// <summary>
    /// Mark a mining node or ground pickup that supplies a needed item. A
    /// mined node shows its regeneration timer; a pickup shows only while it
    /// lies in the scene. Fishing has no spot to mark: its key names the
    /// center of a water volume (<see cref="PositionedSource.IsZoneWide"/>).
    /// </summary>
    private void EmitPositionedSourceMarker(
        string sourceKey,
        PositionedSource source,
        string displayName,
        string scene,
        string progress
    )
    {
        if (
            source.IsZoneWide
            || !string.Equals(source.Scene, scene, System.StringComparison.OrdinalIgnoreCase)
        )
            return;

        var key = new IntentKey(sourceKey);
        var position = new Vector3(source.X, source.Y, source.Z);
        if (source.Kind == "mining")
        {
            var info = _bridge.GetState(source.X, source.Y, source.Z, sourceKey, displayName);
            if (info.LiveMiningNode == null || info.LiveNPC == null)
                return;
            var entry = new MarkerEntry
            {
                Position = GetMarkerPosition(info.LiveNPC),
                DisplayName = displayName,
                TrackedNPC = info.LiveNPC,
                LiveMiningNode = info.LiveMiningNode,
                QuestType = MarkerType.Objective,
                QuestSubText = progress,
            };
            if (info.State == SpawnPointBridge.SpawnState.Mined)
                SetRespawnTimer(ref entry, info.RespawnSeconds, RegenerationDueText);
            else
            {
                entry.Type = MarkerType.Objective;
                entry.SubText = progress;
                entry.TargetKey = sourceKey;
            }
            TryAddMarker(key, entry);
            return;
        }

        var bag = FindItemBag(position);
        if (bag == null)
            return;
        TryAddMarker(
            key,
            new MarkerEntry
            {
                Position = bag.transform.position + Vector3.up * StaticHeightOffset,
                Type = MarkerType.Objective,
                DisplayName = displayName,
                SubText = progress,
                QuestType = MarkerType.Objective,
                QuestSubText = progress,
                TrackedPickup = bag,
            }
        );
    }

    /// <summary>The ground pickup at an exported position, if it is still there.</summary>
    private ItemBag? FindItemBag(Vector3 position)
    {
        _itemBags ??= UnityEngine.Object.FindObjectsOfType<ItemBag>();
        foreach (var bag in _itemBags)
        {
            // Exported coordinates are rounded to centimeters.
            if (bag != null && (bag.transform.position - position).sqrMagnitude <= 0.01f)
                return bag;
        }
        return null;
    }

    // ── Per-spawn-point marker emission ──────────────────────────

    /// <summary>
    /// Iterate all static spawns for a character in the given scene. For each
    /// spawn, check live state via SpawnPointBridge and emit the appropriate
    /// marker: quest marker when alive, absence marker when not.
    /// </summary>
    private void EmitPerSpawnMarkers(
        string stableKey,
        string scene,
        string displayName,
        MarkerType questType,
        string? questSubText
    )
    {
        if (!_data.CharacterSpawns.TryGetValue(stableKey, out var spawns))
            return;

        foreach (var sp in spawns)
        {
            // A furnishing stands only in the rooms whose slot holds its set.
            if (
                !string.Equals(sp.Scene, scene, System.StringComparison.OrdinalIgnoreCase)
                || !_state.Furnishings.IsPresent(sp)
            )
                continue;

            var staticPos = new Vector3(sp.X, sp.Y, sp.Z) + Vector3.up * StaticHeightOffset;
            var key = new IntentKey(stableKey, sp.X, sp.Y, sp.Z);

            var info = _bridge.GetState(sp.X, sp.Y, sp.Z, stableKey, displayName);

            // Use live NPC position when available (NPCs drift from placed position)
            var pos = info.LiveNPC != null ? GetMarkerPosition(info.LiveNPC) : staticPos;
            var entry = new MarkerEntry
            {
                Position = pos,
                DisplayName = displayName,
                CharacterKey = stableKey,
                LiveSpawnPoint = info.LiveSpawnPoint,
                TrackedNPC = info.LiveNPC,
                LiveMiningNode = info.LiveMiningNode,
                TargetNpcName = info.TargetName,
                QuestType = questType,
                QuestSubText = questSubText,
            };

            switch (info.State)
            {
                case SpawnPointBridge.SpawnState.Alive:
                    entry.Type = questType;
                    entry.SubText = questSubText;
                    entry.TargetKey = stableKey;
                    TryAddMarker(key, entry);
                    break;

                case SpawnPointBridge.SpawnState.Dead:
                    SetRespawnTimer(ref entry, info.RespawnSeconds, RespawnDueText);
                    TryAddMarker(key, entry);
                    break;

                case SpawnPointBridge.SpawnState.Mined:
                    SetRespawnTimer(ref entry, info.RespawnSeconds, RegenerationDueText);
                    TryAddMarker(key, entry);
                    break;

                case SpawnPointBridge.SpawnState.NightLocked:
                    SetNightText(ref entry);
                    TryAddMarker(key, entry);
                    break;

                case SpawnPointBridge.SpawnState.DirectlyPlacedDead:
                    // A furnishing does not respawn on zone re-entry: building
                    // the planning table places it, and it is not built yet.
                    if (sp.FurnitureSlot != null)
                        break;
                    // A quest-unlock entry means direct-placement absence is ambiguous:
                    // do not claim this NPC will respawn on zone re-entry.
                    bool characterUnlockIsAmbiguous = _data.CharacterQuestUnlocks.ContainsKey(
                        stableKey
                    );
                    bool hasSourceScript = !string.IsNullOrEmpty(sp.SourceScript);
                    var gateState = DirectPlacementGateState.Absent;
                    string? gateStableKey = sp.SpawnUponQuestCompleteStableKey;
                    if (!characterUnlockIsAmbiguous && !hasSourceScript && gateStableKey != null)
                    {
                        var gateQuest = _data.GetByStableKey(gateStableKey);
                        gateState =
                            gateQuest == null ? DirectPlacementGateState.Unresolved
                            : _state.IsCompleted(gateQuest) ? DirectPlacementGateState.Completed
                            : DirectPlacementGateState.Incomplete;
                    }

                    if (
                        DirectPlacementPolicy.ShouldSuppressRespawn(
                            characterUnlockIsAmbiguous,
                            hasSourceScript,
                            gateState
                        )
                    )
                        break;

                    TryAddMarker(
                        key,
                        new MarkerEntry
                        {
                            Position = pos,
                            Type = MarkerType.ZoneReentry,
                            DisplayName = displayName,
                            SubText = RespawnTimerText.WithName(
                                displayName,
                                "Re-enter zone to respawn"
                            ),
                        }
                    );
                    break;
                // OtherAlive, Populating, Withheld: no marker
            }
        }
    }

    // ── Respawn timers without a quest target ─────────────────────

    /// <summary>
    /// Respawn markers for SpawnPoints no quest marker covers: a clock with
    /// the respawn timer while the NPC respawns, and a moon while a despawned
    /// night-only NPC waits for night. Points the zone load is still
    /// populating, and points that cannot spawn, show nothing.
    /// </summary>
    private void CollectRespawnTimerMarkers()
    {
        var spawnPoints = _bridge.SpawnPoints;
        for (int i = 0; i < spawnPoints.Count; i++)
        {
            var sp = spawnPoints[i];
            if (sp == null || _questSpawnPoints.Contains(sp.GetInstanceID()))
                continue;

            var phase = _bridge.GetPhase(sp, targetName: null);
            bool show =
                phase == SpawnPointPhase.Respawning
                || (phase == SpawnPointPhase.NightLocked && _bridge.HasRespawnHistory(sp));
            if (!show)
                continue;

            var entry = new MarkerEntry
            {
                Position = sp.transform.position + Vector3.up * StaticHeightOffset,
                DisplayName = _bridge.GetRespawnLabel(sp) ?? "",
                LiveSpawnPoint = sp,
                RespawnOnly = true,
            };
            if (phase == SpawnPointPhase.NightLocked)
                SetNightText(ref entry);
            else
                SetRespawnTimer(ref entry, SpawnPointBridge.GetRespawnSeconds(sp), RespawnDueText);
            _markers.Add(entry);
        }
    }

    // ── Loot container markers (corpses and RotChests) ────────────

    /// <summary>
    /// Emit Objective markers on corpses and RotChests that contain items
    /// needed by any active quest. These coexist with clock/timer markers
    /// at the spawn point, which stay at the spawn position.
    /// </summary>
    private void CollectLootContainerMarkers()
    {
        foreach (var container in _lootScanner.Containers)
        {
            _markers.Add(
                new MarkerEntry
                {
                    Position = container.Position + Vector3.up * CorpseHeightOffset,
                    Type = MarkerType.Objective,
                    DisplayName = container.DisplayName,
                    SubText = FormatLootContainerText(container),
                }
            );
        }
    }

    private string FormatLootContainerText(LootScanner.LootContainer container)
    {
        // Show progress for each matching item: "Loot: 0/1 Dragon Scale"
        // If multiple items match, show first with count hint.
        string? firstLine = null;
        int count = 0;
        foreach (var itemName in container.MatchingItems)
        {
            count++;
            if (firstLine == null)
            {
                int have = 0;
                // Find the required quantity from active quests
                int need = 1;
                foreach (var quest in _data.All)
                {
                    if (!_state.IsActionable(quest) || quest.RequiredItems == null)
                        continue;
                    foreach (var ri in quest.RequiredItems)
                    {
                        if (
                            string.Equals(
                                ri.ItemName,
                                itemName,
                                System.StringComparison.OrdinalIgnoreCase
                            )
                        )
                        {
                            have = _state.CountItem(ri.ItemStableKey);
                            need = ri.Quantity;
                            break;
                        }
                    }
                }
                firstLine = $"Loot: {have}/{need} {itemName}";
            }
        }
        if (count > 1)
            firstLine += $" (+{count - 1} more)";
        return firstLine ?? container.DisplayName;
    }

    // ── Per-frame updates ─────────────────────────────────────────

    private void UpdateLiveState()
    {
        var cam = CameraCache.Get();
        if (cam == null)
            return;

        var playerPos = GameData.PlayerControl.transform.position;

        // Update each active marker
        for (int i = 0; i < _markers.Count; i++)
        {
            var m = _markers[i];
            var instance = _pool.Get(i);
            // A taken pickup is destroyed; the rebuild that the inventory
            // change triggers drops its marker.
            if (!ReferenceEquals(m.TrackedPickup, null) && m.TrackedPickup == null)
            {
                instance.SetActive(false);
                continue;
            }
            // Track live positions before deciding whether sub-text is visible.
            if (!m.RespawnOnly && m.TargetKey != null)
            {
                NPC? tracked = m.LiveSpawnPoint?.SpawnedNPC ?? m.TrackedNPC;
                if (tracked != null)
                    m.Position = GetMarkerPosition(tracked);
            }

            float distance = Vector3.Distance(playerPos, m.Position);

            if (m.RespawnOnly || m.SharedNames != null)
            {
                if (!UpdateRespawnOnlyMarker(ref m, instance, distance))
                {
                    _markers[i] = m;
                    continue;
                }
            }
            else
            {
                // Per-frame spawn state: update timers and detect alive/dead transitions
                if (m.LiveMiningNode != null)
                    UpdateMiningMarkerState(ref m, instance, m.LiveMiningNode, distance);
                else if (m.LiveSpawnPoint != null)
                    UpdateSpawnMarkerState(ref m, instance, distance);
            }

            instance.SetPosition(m.Position);

            // Distance fade — MarkerInstance handles separate icon/sub-text ramps
            instance.SetAlpha(distance);

            _markers[i] = m; // write back mutated state
        }
    }

    /// <summary>
    /// Keep a respawn timer current. Returns false once its SpawnPoint has a
    /// living NPC again: the marker hides until the rebuild that the spawn
    /// triggers drops it.
    /// </summary>
    private static bool UpdateRespawnOnlyMarker(
        ref MarkerEntry m,
        MarkerInstance instance,
        float distance
    )
    {
        var sp = m.LiveSpawnPoint;
        if (sp == null || (sp.MyNPCAlive && sp.SpawnedNPC != null))
        {
            instance.SetActive(false);
            return false;
        }

        if (m.Type == MarkerType.NightSpawn)
            RefreshNightText(ref m, instance, distance);
        else
            RefreshRespawnTimer(
                ref m,
                instance,
                SpawnPointBridge.GetRespawnSeconds(sp),
                RespawnDueText,
                distance
            );
        return true;
    }

    /// <summary>
    /// Re-classify a quest spawn marker per-frame based on live SpawnPoint
    /// state. Handles alive↔dead transitions immediately and keeps respawn
    /// and night text current.
    /// </summary>
    private void UpdateSpawnMarkerState(ref MarkerEntry m, MarkerInstance instance, float distance)
    {
        var sp = m.LiveSpawnPoint!;

        bool isAlive = SpawnPointBridge.IsTargetAlive(sp, m.TargetNpcName ?? m.DisplayName);

        if (isAlive && m.Type != m.QuestType)
        {
            // Respawned: restore quest marker
            m.Type = m.QuestType;
            m.SubText = m.QuestSubText;
            m.TargetKey = "live"; // non-null activates position tracking
            Configure(instance, m);
            if (sp.SpawnedNPC != null)
                m.Position = GetMarkerPosition(sp.SpawnedNPC);
        }
        else if (!isAlive && m.Type == m.QuestType)
        {
            // Lost target: the spawn phase decides clock, moon, or no marker.
            m.TargetKey = null;
            var type = SpawnMarkerPolicy.TypeWhenTargetLost(
                _bridge.GetPhase(sp, m.TargetNpcName ?? m.DisplayName)
            );
            if (type == null)
            {
                instance.SetActive(false);
                return;
            }
            if (type == MarkerType.NightSpawn)
                SetNightText(ref m);
            else
                SetRespawnTimer(ref m, SpawnPointBridge.GetRespawnSeconds(sp), RespawnDueText);
            Configure(instance, m);
        }
        else if (m.Type == MarkerType.DeadSpawn)
        {
            RefreshRespawnTimer(
                ref m,
                instance,
                SpawnPointBridge.GetRespawnSeconds(sp),
                RespawnDueText,
                distance
            );
        }
        else if (m.Type == MarkerType.NightSpawn)
        {
            RefreshNightText(ref m, instance, distance);
        }
    }

    private void UpdateMiningMarkerState(
        ref MarkerEntry m,
        MarkerInstance instance,
        MiningNode node,
        float distance
    )
    {
        bool isMined = SpawnPointBridge.IsMiningNodeMined(node);

        if (!isMined && m.Type != m.QuestType)
        {
            // Regenerated: restore quest marker
            m.Type = m.QuestType;
            m.SubText = m.QuestSubText;
            m.TargetKey = "live";
            Configure(instance, m);
        }
        else if (isMined && m.Type == m.QuestType)
        {
            // Just mined: switch to clock with timer
            m.TargetKey = null;
            SetRespawnTimer(
                ref m,
                SpawnPointBridge.GetMiningNodeRespawnSeconds(node),
                RegenerationDueText
            );
            Configure(instance, m);
        }
        else if (isMined && m.Type == MarkerType.DeadSpawn)
        {
            RefreshRespawnTimer(
                ref m,
                instance,
                SpawnPointBridge.GetMiningNodeRespawnSeconds(node),
                RegenerationDueText,
                distance
            );
        }
    }

    // ── Respawn text ──────────────────────────────────────────────

    /// <summary>Turn a marker into a clock showing the respawn timer.</summary>
    private static void SetRespawnTimer(ref MarkerEntry m, float seconds, string dueText)
    {
        int shown = RespawnTimerText.DisplaySeconds(seconds);
        m.Type = MarkerType.DeadSpawn;
        m.ShownValue = shown;
        m.SubText = RespawnTimerText.WithName(
            m.DisplayName,
            RespawnTimerText.Timer(shown, dueText)
        );
    }

    /// <summary>Turn a marker into a moon showing the night window and game time.</summary>
    private static void SetNightText(ref MarkerEntry m)
    {
        int hour = GameData.Time.hour;
        int minute = GameData.Time.min;
        m.Type = MarkerType.NightSpawn;
        m.ShownValue = hour * 60 + minute;
        m.SubText = RespawnTimerText.WithName(
            m.DisplayName,
            RespawnTimerText.NightOnly(hour, minute)
        );
    }

    /// <summary>Rewrite the respawn timer only when its whole seconds change.</summary>
    private static void RefreshRespawnTimer(
        ref MarkerEntry m,
        MarkerInstance instance,
        float seconds,
        string dueText,
        float distance
    )
    {
        int shown = RespawnTimerText.DisplaySeconds(seconds);
        if (!MarkerFadePolicy.ShouldRefreshSubText(distance, shown, m.ShownValue))
            return;
        m.ShownValue = shown;
        m.SubText = RespawnTimerText.WithName(
            m.DisplayName,
            RespawnTimerText.Timer(shown, dueText)
        );
        instance.UpdateSubText(m.SubText);
    }

    /// <summary>Rewrite the game time only when its minute changes.</summary>
    private static void RefreshNightText(ref MarkerEntry m, MarkerInstance instance, float distance)
    {
        int hour = GameData.Time.hour;
        int minute = GameData.Time.min;
        int shown = hour * 60 + minute;
        if (!MarkerFadePolicy.ShouldRefreshSubText(distance, shown, m.ShownValue))
            return;
        m.ShownValue = shown;
        m.SubText = RespawnTimerText.WithName(
            m.DisplayName,
            RespawnTimerText.NightOnly(hour, minute)
        );
        instance.UpdateSubText(m.SubText);
    }

    // ── Helpers ───────────────────────────────────────────────────

    private void Configure(MarkerInstance instance, in MarkerEntry m) =>
        instance.Configure(
            m.Type,
            m.SubText,
            _config.MarkerScale.Value,
            _config.IconSize.Value,
            _config.SubTextSize.Value,
            _config.IconYOffset.Value,
            _config.SubTextYOffset.Value
        );

    /// <summary>
    /// Add a marker for an intent. If a marker already exists for the same
    /// intent, replace it only when the new type has higher priority (lower
    /// enum ordinal).
    /// </summary>
    private void TryAddMarker(in IntentKey key, MarkerEntry entry)
    {
        if (entry.LiveSpawnPoint != null)
            _questSpawnPoints.Add(entry.LiveSpawnPoint.GetInstanceID());

        int? absencePointId = SharedSpawnMarkerPolicy.AbsencePointId(
            entry.Type,
            entry.LiveSpawnPoint != null ? entry.LiveSpawnPoint.GetInstanceID() : null
        );
        var intentKey = absencePointId.HasValue ? new IntentKey(absencePointId.Value) : key;

        if (_intentIndex.TryGetValue(intentKey, out int existingIdx))
        {
            var existing = _markers[existingIdx];
            if (
                absencePointId.HasValue
                && entry.CharacterKey != null
                && existing.CharacterKey != null
            )
            {
                if (
                    existing.SharedNames != null
                    || !string.Equals(
                        existing.CharacterKey,
                        entry.CharacterKey,
                        System.StringComparison.OrdinalIgnoreCase
                    )
                )
                {
                    existing.SharedNames ??= new SharedSpawnMarkerNames(
                        existing.CharacterKey,
                        existing.DisplayName
                    );
                    existing.SharedNames.Add(entry.CharacterKey, entry.DisplayName);
                    existing.DisplayName = existing.SharedNames.DisplayName;
                    existing.TargetNpcName = null;
                }
                if (MarkerDecision.ShouldReplace(existing.QuestType, entry.QuestType))
                {
                    existing.QuestType = entry.QuestType;
                    existing.QuestSubText = entry.QuestSubText;
                }
                if (existing.Type == MarkerType.NightSpawn)
                    SetNightText(ref existing);
                else
                    SetRespawnTimer(
                        ref existing,
                        SpawnPointBridge.GetRespawnSeconds(existing.LiveSpawnPoint!),
                        RespawnDueText
                    );
                _markers[existingIdx] = existing;
                return;
            }
            if (MarkerDecision.ShouldReplace(existing.Type, entry.Type))
            {
                entry.Position = existing.Position;
                _markers[existingIdx] = entry;
            }
            return;
        }

        _intentIndex[intentKey] = _markers.Count;
        _markers.Add(entry);
    }

    /// <summary>Get marker position above a live NPC using its CapsuleCollider height.</summary>
    private static Vector3 GetMarkerPosition(NPC npc)
    {
        var collider = npc.GetComponent<CapsuleCollider>();
        float height =
            collider != null
                ? collider.height * Mathf.Max(npc.transform.localScale.y, 1f)
                    + LiveHeightAboveCollider
                : StaticHeightOffset;
        return npc.transform.position + Vector3.up * height;
    }

    /// <summary>Check if all required items for a quest are in the player's inventory.</summary>
    private bool HasAllRequiredItems(QuestEntry quest)
    {
        if (quest.RequiredItems == null || quest.RequiredItems.Count == 0)
            return false;

        foreach (var ri in quest.RequiredItems)
        {
            if (_state.CountItem(ri.ItemStableKey) < ri.Quantity)
                return false;
        }
        return true;
    }

    /// <summary>
    /// Identity of a marker intent: an empty live spawn point, a character at
    /// a spawn position (rounded to centimeters), or a step's stable key.
    /// A struct key avoids formatting a string per spawn on every rebuild.
    /// </summary>
    private readonly struct IntentKey : System.IEquatable<IntentKey>
    {
        private readonly string _key;
        private readonly int _spawnPointId;
        private readonly int _x,
            _y,
            _z;

        public IntentKey(string key)
            : this(key, 0f, 0f, 0f) { }

        public IntentKey(int spawnPointId)
            : this("", 0f, 0f, 0f)
        {
            _spawnPointId = spawnPointId;
        }

        public IntentKey(string key, float x, float y, float z)
        {
            _key = key;
            _spawnPointId = 0;
            _x = Mathf.RoundToInt(x * 100f);
            _y = Mathf.RoundToInt(y * 100f);
            _z = Mathf.RoundToInt(z * 100f);
        }

        public bool Equals(IntentKey other) =>
            _spawnPointId == other._spawnPointId
            && _x == other._x
            && _y == other._y
            && _z == other._z
            && string.Equals(_key, other._key, System.StringComparison.OrdinalIgnoreCase);

        public override bool Equals(object? obj) => obj is IntentKey other && Equals(other);

        public override int GetHashCode() =>
            System.StringComparer.OrdinalIgnoreCase.GetHashCode(_key)
            ^ _spawnPointId
            ^ (_x * 397)
            ^ (_y * 17)
            ^ _z;
    }
}

/// <summary>
/// A computed marker. Stores current visual state (Type, SubText) and
/// quest intent (QuestType, QuestSubText) so per-frame updates can switch
/// between alive and absence states without a full rebuild.
/// </summary>
public struct MarkerEntry
{
    public Vector3 Position;
    public MarkerType Type;
    public string DisplayName;

    internal string? CharacterKey;
    internal SharedSpawnMarkerNames? SharedNames;
    public string? TargetKey;
    public string? SubText;

    /// <summary>Live SpawnPoint for per-frame timer/state updates. Null for non-spawn markers.</summary>
    public SpawnPoint? LiveSpawnPoint;

    /// <summary>Live NPC for position tracking on directly-placed NPCs (no SpawnPoint).</summary>
    public NPC? TrackedNPC;

    /// <summary>Live MiningNode for per-frame mined state and timer updates.</summary>
    public MiningNode? LiveMiningNode;

    /// <summary>Ground pickup the marker stands over; it hides once taken.</summary>
    internal ItemBag? TrackedPickup;

    /// <summary>Quest marker type to restore when NPC respawns.</summary>
    public MarkerType QuestType;

    /// <summary>Quest sub-text to restore when NPC respawns.</summary>
    public string? QuestSubText;

    /// <summary>
    /// NPCName the quest target spawns with at <see cref="LiveSpawnPoint"/>;
    /// it can differ from <see cref="DisplayName"/>.
    /// </summary>
    public string? TargetNpcName;

    /// <summary>
    /// Respawn timer without a quest target (ShowAllRespawnTimers). It has
    /// no quest marker to restore, so it hides once its NPC is alive again.
    /// </summary>
    public bool RespawnOnly;

    /// <summary>
    /// Value the sub-text shows: whole seconds of the respawn timer, or the
    /// minute of the game day for night markers. The text is rebuilt only
    /// when it changes.
    /// </summary>
    public int ShownValue;
}
