using AdventureGuide.Config;
using AdventureGuide.Data;
using AdventureGuide.State;
using UnityEngine;

namespace AdventureGuide.Navigation;

/// <summary>
/// Computes and renders world markers for quest-relevant NPCs and objectives.
/// Markers are billboard quads in 3D space with depth occlusion.
///
/// Each spawn point gets its own marker based on live game state:
/// - Alive + expected NPC → quest marker (!, ?, crosshairs)
/// - Dead / respawning → skull + timer
/// - Night-locked → moon + time info
/// - Directly-placed dead → clock + "re-enter zone"
/// - Quest-gated or wrong NPC → no marker
///
/// When multiple quests reference the same spawn point, the highest-priority
/// quest marker wins. Absence markers always supersede quest markers.
/// </summary>
public sealed class WorldMarkerSystem
{
    private const float StaticHeightOffset = 2.5f;
    private const float LiveHeightAboveCollider = 0.8f;

    private readonly GuideData _data;
    private readonly QuestStateTracker _state;
    private readonly EntityRegistry _entities;
    private readonly MiningNodeTracker _miningTracker;
    private readonly SpawnPointBridge _bridge;
    private readonly MarkerPool _pool;
    private readonly GuideConfig _config;

    // Cached marker state — rebuilt on dirty
    private readonly List<MarkerEntry> _markers = new();
    private readonly Dictionary<string, int> _intentIndex = new(System.StringComparer.OrdinalIgnoreCase);
    private string _lastScene = "";
    private bool _enabled;
    private bool _configDirty;
    private int _lastHour = -1;

    public bool Enabled
    {
        get => _enabled;
        set
        {
            _enabled = value;
            if (!value)
                _pool.DeactivateAll();
        }
    }

    public WorldMarkerSystem(
        GuideData data, QuestStateTracker state,
        EntityRegistry entities, SpawnPointBridge bridge,
        MiningNodeTracker miningTracker, GuideConfig config)
    {
        _data = data;
        _state = state;
        _entities = entities;
        _bridge = bridge;
        _miningTracker = miningTracker;
        _config = config;
        _pool = new MarkerPool();

        // Rebuild markers when any visual config changes
        config.MarkerScale.SettingChanged += OnConfigChanged;
        config.IconSize.SettingChanged += OnConfigChanged;
        config.SubTextSize.SettingChanged += OnConfigChanged;
        config.IconYOffset.SettingChanged += OnConfigChanged;
        config.SubTextYOffset.SettingChanged += OnConfigChanged;
    }

    /// <summary>
    /// Call each frame from Plugin.Update. Rebuilds markers when quest
    /// state or scene changes. Updates live NPC positions and distance
    /// fade every frame.
    /// </summary>
    public void Update(string currentScene)
    {
        if (!_enabled || GameData.PlayerControl == null || !MarkerFonts.IsReady)
            return;

        int hour = GameData.Time.hour;
        bool sceneChanged = currentScene != _lastScene;
        bool hourChanged = hour != _lastHour;
        bool needsRebuild = sceneChanged || hourChanged || _state.IsDirty || _configDirty;
        _configDirty = false;
        _lastHour = hour;

        if (needsRebuild)
        {
            _lastScene = currentScene;
            if (sceneChanged)
                _bridge.Rebuild();
            RebuildMarkers(currentScene);
        }

        UpdateLiveState(currentScene);
    }

    private void OnConfigChanged(object sender, System.EventArgs e) => _configDirty = true;

    public void Destroy()
    {
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

        foreach (var quest in _data.All)
        {
            bool isActive = _state.IsActive(quest.DBName);
            bool isCompleted = _state.IsCompleted(quest.DBName);
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

        CollectMinedNodeMarkers(currentScene);

        // Apply to pool
        _pool.SetActiveCount(_markers.Count);
        for (int i = 0; i < _markers.Count; i++)
        {
            var m = _markers[i];
            var instance = _pool.Get(i);
            instance.Configure(m.Type, m.SubText,
                _config.MarkerScale.Value, _config.IconSize.Value,
                _config.SubTextSize.Value, _config.IconYOffset.Value,
                _config.SubTextYOffset.Value);
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
        if (quest.Acquisition == null) return;

        // Check chain prerequisites — skip if any isn't completed.
        // Prerequisites with an Item field are item-acquisition chains (needed
        // to complete the quest, not to start it) and don't gate availability.
        if (quest.Prerequisites != null)
        {
            foreach (var prereq in quest.Prerequisites)
            {
                if (prereq.Item != null) continue;
                var prereqQuest = _data.GetByStableKey(prereq.QuestKey);
                if (prereqQuest == null || !_state.IsCompleted(prereqQuest.DBName))
                    return;
            }
        }

        foreach (var acq in quest.Acquisition)
        {
            if (acq.SourceType != "character" || acq.SourceStableKey == null)
                continue;

            var questType = repeatable ? MarkerType.QuestGiverRepeat : MarkerType.QuestGiver;
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
        if (quest.Completion == null) return;

        bool hasAllItems = HasAllRequiredItems(quest);

        foreach (var comp in quest.Completion)
        {
            if (comp.SourceType != "character" || comp.SourceStableKey == null)
                continue;

            MarkerType questType;
            if (hasAllItems)
                questType = repeatable ? MarkerType.TurnInRepeatReady : MarkerType.TurnInReady;
            else
                questType = MarkerType.TurnInPending;

            string subText = FormatTurnInText(quest);
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
        if (quest.Steps == null) return;

        int currentIdx = StepProgress.GetCurrentStepIndex(quest, _state);
        if (currentIdx >= quest.Steps.Count) return;

        var step = quest.Steps[currentIdx];

        // Current step target
        if (step.TargetKey != null && step.TargetType == "character")
        {
            EmitPerSpawnMarkers(step.TargetKey, scene,
                step.TargetName ?? step.Description,
                MarkerType.Objective, FormatStepActionText(step));
        }

        // NPC sources for ALL uncollected required items (not just current step)
        if (quest.RequiredItems == null) return;

        foreach (var ri in quest.RequiredItems)
        {
            int have = _state.CountItemInInventory(ri.ItemName);
            if (have >= ri.Quantity) continue; // already have enough

            string progress = $"{have}/{ri.Quantity} {ri.ItemName}";

            if (ri.Sources == null) continue;
            foreach (var src in ri.Sources)
            {
                if (src.SourceKey == null) continue;

                EmitPerSpawnMarkers(src.SourceKey, scene,
                    src.Name ?? ri.ItemName,
                    MarkerType.Objective, progress);
            }
        }
    }

    // ── Per-spawn-point marker emission ──────────────────────────

    /// <summary>
    /// Iterate all static spawns for a character in the given scene. For each
    /// spawn, check live state via SpawnPointBridge and emit the appropriate
    /// marker: quest marker when alive, absence marker when not.
    /// </summary>
    private void EmitPerSpawnMarkers(
        string stableKey, string scene, string displayName,
        MarkerType questType, string? questSubText)
    {
        if (!_data.CharacterSpawns.TryGetValue(stableKey, out var spawns))
            return;

        foreach (var sp in spawns)
        {
            if (!string.Equals(sp.Scene, scene, System.StringComparison.OrdinalIgnoreCase))
                continue;

            var staticPos = new Vector3(sp.X, sp.Y, sp.Z) + Vector3.up * StaticHeightOffset;
            string spawnKey = $"{stableKey}@{sp.X:F2},{sp.Y:F2},{sp.Z:F2}";

            var info = _bridge.GetState(sp.X, sp.Y, sp.Z, displayName);

            // Use live NPC position when available (NPCs drift from placed position)
            var pos = info.LiveNPC != null ? GetMarkerPosition(info.LiveNPC) : staticPos;

            switch (info.State)
            {
                case SpawnPointBridge.SpawnState.Alive:
                    TryAddMarker(spawnKey, questType, displayName, questSubText, pos, stableKey);
                    break;

                case SpawnPointBridge.SpawnState.Dead:
                {
                    string timer = info.RespawnSeconds > 0f
                        ? SpawnTimerTracker.FormatTimer(info.RespawnSeconds)
                        : "Respawning...";
                    TryAddMarker(spawnKey, MarkerType.DeadSpawn, displayName,
                        $"{displayName}\n{timer}", pos, targetKey: null);
                    break;
                }

                case SpawnPointBridge.SpawnState.NightLocked:
                {
                    int hour = GameData.Time.hour;
                    int min = GameData.Time.min;
                    TryAddMarker(spawnKey, MarkerType.NightSpawn, displayName,
                        $"{displayName}\nNight only (23:00-04:00)\nNow: {hour}:{min:D2}",
                        pos, targetKey: null);
                    break;
                }

                case SpawnPointBridge.SpawnState.DirectlyPlacedDead:
                    TryAddMarker(spawnKey, MarkerType.ZoneReentry, displayName,
                        $"{displayName}\nRe-enter zone to respawn",
                        pos, targetKey: null);
                    break;

                // QuestGated, NotFound: no marker
            }
        }
    }

    // ── Mined node markers (separate system) ─────────────────────

    private void CollectMinedNodeMarkers(string scene)
    {
        foreach (var node in _miningTracker.Nodes)
        {
            if (node == null || !node.gameObject.activeInHierarchy) continue;
            if (!MiningNodeTracker.IsMined(node)) continue;

            // Only show in current scene
            string nodeScene = node.gameObject.scene.name;
            if (!string.Equals(nodeScene, scene, System.StringComparison.OrdinalIgnoreCase))
                continue;

            var pos = node.transform.position + Vector3.up * StaticHeightOffset;
            float? remaining = MiningNodeTracker.GetRemainingSeconds(node);
            string timer = remaining.HasValue
                ? SpawnTimerTracker.FormatTimer(remaining.Value)
                : "Regenerating...";

            _markers.Add(new MarkerEntry
            {
                Position = pos,
                Type = MarkerType.DeadSpawn, // reuse skull marker for mined nodes
                DisplayName = "Mineral Deposit",
                TargetKey = null,
                SubText = $"Mineral Deposit\n{timer}",
            });
        }
    }

    // ── Per-frame updates ─────────────────────────────────────────

    private void UpdateLiveState(string currentScene)
    {
        var cam = CameraCache.Get();
        if (cam == null) return;

        var playerPos = GameData.PlayerControl?.transform.position;

        // Update each active marker
        for (int i = 0; i < _markers.Count; i++)
        {
            var m = _markers[i];
            var instance = _pool.Get(i);

            // Live NPC position tracking (alive markers only)
            if (m.TargetKey != null)
            {
                var liveNpc = _entities.FindClosest(m.DisplayName, playerPos ?? Vector3.zero);
                if (liveNpc != null)
                    m.Position = GetMarkerPosition(liveNpc);
                // else: keep static position from last rebuild
            }

            instance.SetPosition(m.Position);

            // Distance fade — MarkerInstance handles separate icon/sub-text ramps
            if (playerPos.HasValue)
            {
                float dist = Vector3.Distance(playerPos.Value, m.Position);
                instance.SetAlpha(dist);
            }

            _markers[i] = m; // write back mutated position
        }
    }

    // ── Text formatting ──────────────────────────────────────────

    /// <summary>Format sub-text for turn-in markers: "Give {name}" or "Give {n} items".</summary>
    private static string FormatTurnInText(QuestEntry quest)
    {
        if (quest.RequiredItems == null || quest.RequiredItems.Count == 0)
            return "Talk to";

        // Filter out or_group alternatives — only count truly required items
        int count = 0;
        string? firstName = null;
        foreach (var ri in quest.RequiredItems)
        {
            if (ri.OrGroup != null) continue;
            count++;
            firstName ??= ri.ItemName;
        }

        if (count == 0)
            return "Talk to";
        if (count == 1)
            return $"Give {firstName}";
        return $"Give {count} items";
    }

    /// <summary>Format sub-text for objective step markers based on step action.</summary>
    private static string FormatStepActionText(QuestStep step)
    {
        return step.Action switch
        {
            "shout" when step.Keyword != null => $"Shout '{step.Keyword}'",
            "shout" => "Shout near",
            _ => "Talk to",
        };
    }

    // ── Helpers ───────────────────────────────────────────────────

    /// <summary>
    /// Try to add a marker for the given spawn-point key. If a marker already
    /// exists for this key, only replace it if the new type has higher
    /// priority (lower enum ordinal).
    /// </summary>
    private void TryAddMarker(
        string spawnKey, MarkerType type, string displayName,
        string? subText, Vector3 position, string? targetKey)
    {
        if (_intentIndex.TryGetValue(spawnKey, out int existingIdx))
        {
            var existing = _markers[existingIdx];
            if (type < existing.Type) // lower ordinal = higher priority
            {
                _markers[existingIdx] = new MarkerEntry
                {
                    Position = existing.Position,
                    Type = type,
                    DisplayName = displayName,
                    TargetKey = targetKey,
                    SubText = subText,
                };
            }
            return;
        }

        _intentIndex[spawnKey] = _markers.Count;
        _markers.Add(new MarkerEntry
        {
            Position = position,
            Type = type,
            DisplayName = displayName,
            TargetKey = targetKey,
            SubText = subText,
        });
    }

    /// <summary>Get marker position above a live NPC using its CapsuleCollider height.</summary>
    private static Vector3 GetMarkerPosition(NPC npc)
    {
        var collider = npc.GetComponent<CapsuleCollider>();
        float height = collider != null
            ? collider.height * Mathf.Max(npc.transform.localScale.y, 1f) + LiveHeightAboveCollider
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
            if (_state.CountItemInInventory(ri.ItemName) < ri.Quantity)
                return false;
        }
        return true;
    }
}

/// <summary>
/// A computed marker to display. Position is mutable for live NPC tracking.
/// </summary>
public struct MarkerEntry
{
    public Vector3 Position;
    public MarkerType Type;
    public string DisplayName;
    public string? TargetKey;
    public string? SubText;
}
