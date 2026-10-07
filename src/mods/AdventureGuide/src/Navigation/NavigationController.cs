using AdventureGuide.Config;
using AdventureGuide.Data;
using AdventureGuide.State;
using UnityEngine;
using UnityEngine.AI;

namespace AdventureGuide.Navigation;

/// <summary>
/// Resolves quest steps to navigation targets and manages the active
/// navigation state. Uses EntityRegistry for O(1) live NPC lookups
/// (closest alive NPC by display name), falling back to static spawn
/// data from the guide JSON.
/// </summary>
public sealed class NavigationController
{
    private readonly GuideData _data;
    private readonly EntityRegistry _entities;
    private readonly QuestStateTracker _state;
    private readonly Func<string, int> _countItem;
    private readonly SpawnTimerTracker _timers;
    private readonly MiningNodeTracker _miningTracker;
    private readonly LootScanner _lootScanner;
    private readonly ZoneGraph _zoneGraph;

    // ── Cross-zone routing cache ──────────────────────────────────
    private ZoneLineEntry? _cachedZoneLine;
    private ZoneLineEntry? _pinnedZoneLine;
    private Vector3 _lastCrossZoneCalcPos;
    private string? _navigationScene;
    private bool _cachedRouteLocked;
    private readonly UnroutableRoute _unroutableRoute = new();
    private const float CrossZoneRecalcDistance = 10f;

    // ── Multi-source navigation state ─────────────────────────────
    // When navigating an item step, multiple sources may be active.
    // The controller picks the closest spawn among all active source
    // keys and points the arrow/path at it.

    /// <summary>All leaf sources for the current item step (for auto-mode recomputation).</summary>
    private List<Data.ItemSource> _allItemSources = new();
    private readonly Dictionary<string, PositionedSource> _positionedSources = new(
        System.StringComparer.OrdinalIgnoreCase
    );

    /// <summary>Source keys in the active navigation set.</summary>
    private readonly HashSet<string> _activeSourceKeys = new(
        System.StringComparer.OrdinalIgnoreCase
    );

    /// <summary>Item names the navigated quest still needs; refilled every frame.</summary>
    private readonly HashSet<string> _neededItems = new(System.StringComparer.OrdinalIgnoreCase);

    /// <summary>True when the user has manually toggled sources.</summary>
    private bool _manualOverride;

    /// <summary>Which specific source key is currently closest (drives display name and live tracking).</summary>
    private string? _currentSourceKey;

    /// <summary>Origin identity for the current NavigateTo call chain.</summary>
    private string? _originQuestKey;
    private int _originStepOrder;
    private QuestStep? _resolvedStep;

    // ── Per-character config persistence ──────────────────────────
    private IConfigValue<string>? _navQuestEntry;
    private IConfigValue<int>? _navStepEntry;
    private int _boundSlotIndex = -1;

    /// <summary>Throttle for multi-source closest-spawn resolution.</summary>
    private float _sourceRescanTimer;
    private const float SourceRescanInterval = 0.25f;

    // Scratch path for reachability checks — avoids allocation per candidate
    private readonly NavMeshPath _scratchPath = new();

    /// <summary>Currently active navigation target, or null if not navigating.</summary>
    public NavigationTarget? Target { get; private set; }

    /// <summary>Distance from player to current target. Updated each frame via Update().</summary>
    public float Distance { get; private set; }

    /// <summary>World-space direction from player to target (normalized). Zero if no target.</summary>
    public Vector3 Direction { get; private set; }

    /// <summary>
    /// When navigating cross-zone, this holds the zone line we're routing through.
    /// Null when navigating within the current zone.
    /// </summary>
    public NavigationTarget? ZoneLineWaypoint { get; private set; }

    public NavigationController(
        GuideData data,
        EntityRegistry entities,
        QuestStateTracker state,
        SpawnTimerTracker timers,
        MiningNodeTracker miningTracker,
        LootScanner lootScanner
    )
    {
        _data = data;
        _entities = entities;
        _state = state;
        _countItem = state.CountItem;
        _timers = timers;
        _miningTracker = miningTracker;
        _lootScanner = lootScanner;
        _zoneGraph = new ZoneGraph(data, state);
    }

    /// <summary>
    /// Start a new navigation session from a quest step. Records the
    /// quest+step as origin identity (for IsNavigating), then resolves
    /// through sub-quests and sets the navigation target.
    /// </summary>
    public bool NavigateTo(QuestStep step, QuestEntry quest, string currentScene)
    {
        _originQuestKey = quest.RuntimeKey;
        _originStepOrder = step.Order;
        SavePerCharacter();
        return ResolveAndNavigate(step, quest, currentScene);
    }

    internal static NavigationTarget CreateFixedPositionTarget(
        QuestStep step,
        QuestEntry quest,
        string originQuestKey,
        int originStepOrder
    )
    {
        var spec = NavigationPolicy.CreateFixedPositionTargetSpec(
            step,
            quest,
            originQuestKey,
            originStepOrder
        );
        return new NavigationTarget(
            NavigationTarget.Kind.Position,
            new Vector3(spec.X, spec.Y, spec.Z),
            spec.DisplayName,
            spec.Scene,
            spec.QuestKey,
            spec.StepOrder,
            spec.SourceId,
            spec.OriginQuestKey,
            spec.OriginStepOrder
        );
    }

    /// <summary>
    /// Resolve a step through sub-quests and set the navigation target.
    /// Does not change origin identity — used by both NavigateTo (after setting
    /// origin) and auto-advance (which preserves the existing origin).
    /// </summary>
    private bool ResolveAndNavigate(QuestStep step, QuestEntry quest, string currentScene)
    {
        var (resolved, resolvedQuest) = StepProgress.ResolveActiveStep(step, quest, _state, _data);
        if (resolved != null && resolvedQuest != null && resolved != step)
        {
            step = resolved;
            quest = resolvedQuest;
        }

        if (step.Action == "complete_quest")
            return false;

        ResetTargetState();
        _resolvedStep = step;

        if (step.Location != null)
        {
            Target = CreateFixedPositionTarget(
                step,
                quest,
                _originQuestKey ?? quest.RuntimeKey,
                _originStepOrder
            );
            return true;
        }

        if (step.TargetKey == null)
            return false;

        if (step.TargetType == "character")
        {
            var playerPos = GetPlayerPosition();
            if (playerPos.HasValue)
            {
                var liveNpc = _entities.FindClosest(step.TargetKey, playerPos.Value);
                if (liveNpc != null)
                {
                    Target = MakeTarget(
                        NavigationTarget.Kind.Character,
                        liveNpc.transform.position,
                        WithCharacterUnlockText(
                            step.TargetName ?? step.Description,
                            step.TargetKey
                        ),
                        currentScene,
                        quest.RuntimeKey,
                        step.Order,
                        step.TargetKey
                    );
                    return true;
                }
            }
        }

        return step.TargetType switch
        {
            "character" => ResolveCharacterTarget(step, quest, currentScene),
            "zone" => ResolveZoneTarget(step, quest, currentScene),
            "item" => ResolveItemTarget(step, quest, currentScene),
            _ => false,
        };
    }

    /// <summary>Clear active navigation.</summary>
    /// <summary>Pin a specific zone line for cross-zone routing, overriding auto-selection.</summary>
    public void PinZoneLine(ZoneLineEntry zoneLine)
    {
        _pinnedZoneLine = zoneLine;
        // Force recalculation on next update
        InvalidateCrossZoneCache();
    }

    /// <summary>End the navigation session entirely.</summary>
    public void Clear()
    {
        ResetTargetState();
        _originQuestKey = null;
        _originStepOrder = 0;
        SavePerCharacter();
    }

    /// <summary>Hide navigation without erasing the outgoing character's save.</summary>
    public void SuspendForMenu()
    {
        SavePerCharacter();
        ResetTargetState();
        _originQuestKey = null;
        _originStepOrder = 0;
        _navQuestEntry = null;
        _navStepEntry = null;
        _boundSlotIndex = -1;
    }

    // ── Per-character persistence ─────────────────────────────────

    /// <summary>
    /// Bind per-character config entries and restore the saved navigation
    /// target (if any). Call after character login. On zone transitions for
    /// the same character, the in-memory state is authoritative.
    /// </summary>
    public void LoadPerCharacter(GuideConfig config, string currentScene)
    {
        if (
            !NavigationPolicy.ShouldLoadCharacter(
                currentScene,
                _boundSlotIndex,
                GameData.CurrentCharacterSlot?.index
            )
        )
            return;
        var slot = GameData.CurrentCharacterSlot;
        if (slot == null)
            return;

        // Switching characters: save outgoing state before rebinding
        SavePerCharacter();
        ResetTargetState();
        _originQuestKey = null;
        _originStepOrder = 0;

        _boundSlotIndex = slot.index;
        _navQuestEntry = config.BindPerCharacter(slot.index, "NavQuest", "");
        _navStepEntry = config.BindPerCharacter(slot.index, "NavStep", 0);

        var savedQuest = _navQuestEntry.Value;
        var savedStep = _navStepEntry.Value;
        if (string.IsNullOrEmpty(savedQuest) || savedStep <= 0)
            return;

        var quest = _data.GetByRuntimeKey(savedQuest);
        if (quest?.Steps == null)
            return;
        if (_state.IsCompleted(quest))
            return;

        QuestStep? step = null;
        foreach (var s in quest.Steps)
        {
            if (s.Order == savedStep)
            {
                step = s;
                break;
            }
        }
        if (step == null)
            return;

        NavigateTo(step, quest, currentScene);
    }

    /// <summary>
    /// Write the current navigation origin to the per-character config.
    /// Called on mod destroy and before character switch.
    /// </summary>
    public void SavePerCharacter()
    {
        if (_navQuestEntry == null)
            return;
        _navQuestEntry.Value = _originQuestKey ?? "";
        _navStepEntry!.Value = _originStepOrder;
    }

    /// <summary>
    /// Clear target and rendering state without ending the session.
    /// Preserves origin identity so auto-advance and source toggles
    /// keep the parent quest's NAV button highlighted.
    /// </summary>
    private void ResetTargetState()
    {
        Target = null;
        InvalidateCrossZoneCache();
        _pinnedZoneLine = null;
        _activeSourceKeys.Clear();
        _allItemSources.Clear();
        _positionedSources.Clear();
        _manualOverride = false;
        _currentSourceKey = null;
        _sourceRescanTimer = 0f;
        Distance = 0f;
        Direction = Vector3.zero;
    }

    private void InvalidateCrossZoneCache()
    {
        _cachedZoneLine = null;
        _lastCrossZoneCalcPos = Vector3.zero;
        ZoneLineWaypoint = null;
        _unroutableRoute.Clear();
    }

    private bool ObserveScene(string currentScene)
    {
        if (!CrossZoneWaypointPolicy.SceneChanged(_navigationScene, currentScene))
            return false;
        _navigationScene = currentScene;
        InvalidateCrossZoneCache();
        ReResolveForScene(currentScene);
        return true;
    }

    private void ReResolveForScene(string currentScene)
    {
        if (
            Target == null
            || Target.TargetKind == NavigationTarget.Kind.Zone
            || _resolvedStep == null
            || _resolvedStep.Location != null
        )
            return;
        var quest = _data.GetByRuntimeKey(Target.QuestKey);
        if (quest == null)
            return;
        if (_allItemSources.Count > 0)
        {
            // Keep manually chosen sources; auto mode can prefer the new zone.
            if (!_manualOverride)
                ComputeAutoSourceSet(currentScene);
            ResolveClosestActiveSource(quest, _resolvedStep, currentScene);
        }
        else if (
            _resolvedStep.TargetType == "character"
            && StepSceneResolver.HasSourceInScene(
                quest,
                _resolvedStep,
                _data,
                currentScene,
                _state.IsGameQuestCompleted
            )
        )
            ResolveCharacterTarget(_resolvedStep, quest, currentScene);
    }

    /// <summary>
    /// Toggle a source key in/out of the active navigation set.
    /// Enters manual override mode. If the active set becomes empty,
    /// reverts to auto mode.
    /// </summary>
    public void ToggleSource(string sourceKey, string currentScene)
    {
        if (Target == null)
            return;

        _manualOverride = true;
        if (!_activeSourceKeys.Remove(sourceKey))
            _activeSourceKeys.Add(sourceKey);

        // Empty set → revert to auto
        if (_activeSourceKeys.Count == 0)
        {
            _manualOverride = false;
            ComputeAutoSourceSet(currentScene);
        }

        // Re-resolve target from the new active set. This handles both
        // same-zone (closest spawn) and cross-zone (zone line routing)
        // transitions when the user toggles between zones.
        var quest = _data.GetByRuntimeKey(Target.QuestKey);
        if (quest?.Steps != null)
        {
            var step = quest.Steps.Find(s => s.Order == Target.StepOrder);
            if (step != null)
            {
                // Clear stale target and cross-zone state before re-resolving.
                // The new target may be in a different zone.
                Target = null;
                ZoneLineWaypoint = null;
                _cachedZoneLine = null;
                _currentSourceKey = null;
                ResolveClosestActiveSource(quest, step, currentScene);
            }
        }
    }

    /// <summary>Whether a source key is in the active navigation set.</summary>
    public bool IsSourceActive(string sourceKey) => _activeSourceKeys.Contains(sourceKey);

    /// <summary>Whether the user has manually toggled sources.</summary>
    public bool IsManualSourceOverride => _manualOverride;

    /// <summary>
    /// Navigate to a zone by scene name. Used for sources that have a zone
    /// but no specific coordinates (e.g. fishing). When the player is already
    /// in the target zone, sets a same-zone Zone target so IsNavigating returns
    /// true (UI highlights the step) but arrow/path stay hidden.
    /// </summary>
    public bool NavigateToZone(
        string scene,
        string displayName,
        string sourceId,
        string questDBName,
        int stepOrder,
        string currentScene
    )
    {
        Clear();

        // Same zone: set a Zone target so UI shows this step as active.
        // Update() handles this by setting distance=0, direction=zero.
        if (string.Equals(scene, currentScene, System.StringComparison.OrdinalIgnoreCase))
        {
            Target = MakeTarget(
                NavigationTarget.Kind.Zone,
                Vector3.zero,
                displayName,
                scene,
                questDBName,
                stepOrder,
                sourceId
            );
            return true;
        }

        var zoneKey = FindZoneKeyBySceneName(scene);
        if (zoneKey == null)
            return false;

        Target = MakeTarget(
            NavigationTarget.Kind.Zone,
            Vector3.zero,
            displayName,
            scene,
            questDBName,
            stepOrder,
            sourceId
        );
        return true;
    }

    /// <summary>
    /// Called when game state changes (quest assigned, quest completed,
    /// inventory changed, NPC killed). Re-evaluates whether the current
    /// nav step is still the active step and auto-advances if not.
    /// </summary>
    public void OnGameStateChanged(string currentScene)
    {
        _zoneGraph.Rebuild();
        ObserveScene(currentScene);
        InvalidateCrossZoneCache();
        if (Target == null)
            return;

        var quest = _data.GetByRuntimeKey(Target.QuestKey);
        if (quest?.Steps == null)
        {
            Clear();
            return;
        }

        // Quest completed — clear nav entirely
        if (_state.IsCompleted(quest))
        {
            Clear();
            return;
        }

        // Determine which step the player is currently on
        int currentStepIdx = StepProgress.GetCurrentStepIndex(quest, _state, _data);

        // Find the index of the step we're navigating
        int navStepIdx = -1;
        for (int i = 0; i < quest.Steps.Count; i++)
        {
            if (quest.Steps[i].Order == Target.StepOrder)
            {
                navStepIdx = i;
                break;
            }
        }

        // Nav step is still the current step or ahead of it
        if (navStepIdx < 0 || navStepIdx >= currentStepIdx)
        {
            // Recompute auto source set for the new zone (unless manually overridden)
            if (!_manualOverride && _allItemSources.Count > 0)
                ComputeAutoSourceSet(currentScene);
            return;
        }

        // Nav step is behind current step — advance to the first navigable
        // step at or after the current step index
        for (int i = currentStepIdx; i < quest.Steps.Count; i++)
        {
            var step = quest.Steps[i];
            if (step.TargetKey != null)
            {
                ResolveAndNavigate(step, quest, currentScene);
                return;
            }
        }

        // No more navigable steps
        Clear();
    }

    /// <summary>
    /// Call each frame. Updates distance/direction to the active target.
    /// Upgrades to live NPC position when one becomes available.
    /// Routes through zone lines for cross-zone targets.
    /// </summary>
    public void Update(string currentScene)
    {
        ObserveScene(currentScene);
        if (Target == null)
            return;

        var playerPos = GetPlayerPosition();
        if (!playerPos.HasValue)
            return;

        // Cross-zone: navigate to zone line instead of target directly
        if (Target.IsCrossZone(currentScene))
        {
            UpdateCrossZoneRouting(currentScene, playerPos.Value);
            return;
        }

        if (ZoneLineWaypoint != null || _cachedZoneLine != null)
            InvalidateCrossZoneCache();

        // Same-zone Zone target (e.g. fishing): player is already in the
        // right zone. Keep Target alive so IsNavigating returns true (UI
        // highlights), but set distance/direction to zero so arrow hides.
        if (Target.TargetKind == NavigationTarget.Kind.Zone)
        {
            Distance = 0f;
            Direction = Vector3.zero;
            return;
        }

        // Same zone: update position from closest match
        // Priority: corpse/chest with quest loot > alive NPC > shortest respawn
        if (Target.TargetKind == NavigationTarget.Kind.Character || _activeSourceKeys.Count > 0)
        {
            var neededItems = BuildNeededItems(Target.QuestKey);
            var corpse =
                neededItems.Count > 0
                    ? _lootScanner.FindClosestWithAnyItem(neededItems, playerPos.Value)
                    : null;

            if (corpse.HasValue)
            {
                Target.Position = corpse.Value.Position;
            }
            else if (_activeSourceKeys.Count > 0)
            {
                // Multi-source: periodically re-resolve closest among all
                // active sources, then track the winner's NPC each frame.
                _sourceRescanTimer += UnityEngine.Time.deltaTime;
                if (_sourceRescanTimer >= SourceRescanInterval)
                {
                    _sourceRescanTimer = 0f;
                    UpdateClosestActiveSource(currentScene, playerPos.Value);
                }
                // Per-frame: track the current winner's live position
                TrackCurrentSourcePosition(playerPos.Value);
            }
            else
            {
                var liveNpc = _entities.FindClosest(Target.SourceId, playerPos.Value);
                if (liveNpc != null)
                    Target.Position = liveNpc.transform.position;
                else
                {
                    var bestRespawn = FindShortestRespawnPosition(Target.SourceId);
                    if (bestRespawn.HasValue)
                        Target.Position = bestRespawn.Value;
                }
            }
        }

        UpdateDistanceAndDirection(Target.Position, playerPos.Value);
    }

    /// <summary>
    /// Check if the given quest+step is the current navigation target.
    /// Matches against both the resolved target AND the originating quest
    /// so that parent quests and sub-quests both show as active.
    /// </summary>
    public bool IsNavigating(string questKey, int stepOrder) =>
        Target != null
        && (
            IsMatch(Target.QuestKey, Target.StepOrder, questKey, stepOrder)
            || IsMatch(Target.OriginQuestKey, Target.OriginStepOrder, questKey, stepOrder)
        );

    private static bool IsMatch(string aQuest, int aStep, string bQuest, int bStep) =>
        string.Equals(aQuest, bQuest, System.StringComparison.OrdinalIgnoreCase) && aStep == bStep;

    /// <summary>
    /// Get all zone lines from the current scene to the navigation target's zone.
    /// Returns empty if not cross-zone navigating or no zone lines found.
    /// </summary>
    public List<(
        ZoneLineEntry line,
        float distance,
        bool isActive,
        bool isAccessible
    )> GetAlternativeZoneLines(string currentScene)
    {
        var result =
            new List<(ZoneLineEntry line, float distance, bool isActive, bool isAccessible)>();
        if (Target == null || !Target.IsCrossZone(currentScene))
            return result;

        var playerPos = GetPlayerPosition() ?? Vector3.zero;
        var targetZoneKey = FindZoneKeyBySceneName(Target.Scene);
        if (targetZoneKey == null)
            return result;

        foreach (var zl in _data.ZoneLines)
        {
            if (!string.Equals(zl.Scene, currentScene, System.StringComparison.OrdinalIgnoreCase))
                continue;
            if (
                !string.Equals(
                    zl.DestinationZoneKey,
                    targetZoneKey,
                    System.StringComparison.OrdinalIgnoreCase
                )
            )
                continue;

            var zlPos = new Vector3(zl.X, zl.Y, zl.Z);
            float dist = Vector3.Distance(playerPos, zlPos);
            var activeZl = _pinnedZoneLine ?? _cachedZoneLine;
            bool selected =
                activeZl != null && zl.X == activeZl.X && zl.Y == activeZl.Y && zl.Z == activeZl.Z;
            bool accessible = IsZoneLineAccessible(zl);
            result.Add((zl, dist, selected, accessible));
        }

        // Accessible first, then by distance within each group
        result.Sort(
            (a, b) =>
            {
                int cmp = b.isAccessible.CompareTo(a.isAccessible);
                return cmp != 0 ? cmp : a.distance.CompareTo(b.distance);
            }
        );
        return result;
    }

    /// <summary>
    /// Throttled re-evaluation: find the closest alive NPC among all active
    /// source keys in the current scene. Updates _currentSourceKey and
    /// Target.SourceId when the winner changes.
    /// </summary>
    private void UpdateClosestActiveSource(string currentScene, Vector3 playerPos)
    {
        var quest = _data.GetByRuntimeKey(Target!.QuestKey);
        var step = quest?.Steps?.Find(s => s.Order == Target.StepOrder);
        if (quest != null && step != null)
            ResolveClosestActiveSource(quest, step, currentScene);
    }

    /// <summary>
    /// Per-frame: track the current winner's live NPC position for smooth arrow movement.
    /// </summary>
    private void TrackCurrentSourcePosition(Vector3 playerPos)
    {
        if (_currentSourceKey == null || _positionedSources.ContainsKey(_currentSourceKey))
            return;

        var liveNpc = _entities.FindClosest(_currentSourceKey, playerPos);
        if (liveNpc != null)
            Target!.Position = liveNpc.transform.position;
        else
        {
            var bestRespawn = FindShortestRespawnPosition(_currentSourceKey);
            if (bestRespawn.HasValue)
                Target!.Position = bestRespawn.Value;
        }
    }

    private Vector3? FindShortestRespawnPosition(string? stableKey)
    {
        if (stableKey == null)
            return null;

        // Check dead enemy spawns
        var bestPoint = _timers.FindSoonestRespawn(stableKey);
        return bestPoint != null ? bestPoint.transform.position : null;
    }

    // ── Target resolution ──────────────────────────────────────────

    private bool ResolveCharacterTarget(QuestStep step, QuestEntry quest, string currentScene)
    {
        if (
            !_data.CharacterSpawns.TryGetValue(step.TargetKey!, out var spawns)
            || spawns.Count == 0
        )
            return false;

        var spawn = PickBestSpawn(spawns, currentScene);
        Target = MakeTarget(
            NavigationTarget.Kind.Character,
            new Vector3(spawn.X, spawn.Y, spawn.Z),
            WithCharacterUnlockText(step.TargetName ?? step.Description, step.TargetKey),
            spawn.Scene,
            quest.RuntimeKey,
            step.Order,
            step.TargetKey
        );
        return true;
    }

    private bool ResolveZoneTarget(QuestStep step, QuestEntry quest, string currentScene)
    {
        // Resolve zone key from target_key or display name
        string? destZoneKey = step.TargetKey;
        if (
            destZoneKey != null
            && !_data.ZoneLookup.Values.Any(z =>
                string.Equals(z.StableKey, destZoneKey, System.StringComparison.OrdinalIgnoreCase)
            )
        )
        {
            destZoneKey = FindZoneKeyByDisplayName(step.TargetName);
        }

        if (destZoneKey == null)
            return false;

        // Find the scene name for this zone
        string? destScene = null;
        foreach (var kvp in _data.ZoneLookup)
        {
            if (
                string.Equals(
                    kvp.Value.StableKey,
                    destZoneKey,
                    System.StringComparison.OrdinalIgnoreCase
                )
            )
            {
                destScene = kvp.Key;
                break;
            }
        }

        if (destScene == null)
            return false;

        // The destination remains authoritative after arrival; zone lines are
        // only intermediate waypoints, including for adjacent destinations.
        Target = MakeTarget(
            NavigationTarget.Kind.Zone,
            Vector3.zero,
            step.TargetName ?? destScene,
            destScene,
            quest.RuntimeKey,
            step.Order
        );
        return true;
    }

    private bool ResolveItemTarget(QuestStep step, QuestEntry quest, string currentScene)
    {
        // For collect/read steps: build the active source set and navigate
        // to the closest spawn among all active sources.
        var item = quest.RequiredItems?.Find(ri =>
            string.Equals(ri.ItemName, step.TargetName, System.StringComparison.OrdinalIgnoreCase)
        );

        if (item?.Sources == null || item.Sources.Count == 0)
            return false;

        // Collect all leaf sources with spawn data
        _allItemSources.Clear();
        CollectLeafSources(item.Sources, _allItemSources);

        if (_allItemSources.Count == 0)
        {
            // No sources with spawn data — fallback to zone navigation
            return ResolveItemZoneFallback(item.Sources, quest, step, currentScene);
        }

        // Build the active set with zone preference
        _manualOverride = false;
        ComputeAutoSourceSet(currentScene);

        // Resolve initial target from the active set
        return ResolveClosestActiveSource(quest, step, currentScene);
    }

    /// <summary>
    /// Recursively collect all leaf sources that have spawn data.
    /// quest_reward sources always recurse into children (the source key
    /// points to the quest giver NPC, not the actual drop sources).
    /// </summary>
    private void CollectLeafSources(List<Data.ItemSource> sources, List<Data.ItemSource> result)
    {
        foreach (var src in sources)
        {
            if (!IsSourceAvailable(src))
                continue;
            // quest_reward: the SourceKey is the quest giver NPC, not a
            // drop source. Always recurse into children for the actual
            // obtainable sources (e.g., Seaspice drops under Percy's Seaspice).
            if (src.Type == "quest_reward" && src.Children is { Count: > 0 })
            {
                CollectLeafSources(src.Children, result);
                continue;
            }

            if (src.SourceKey == null)
            {
                if (src.Children != null)
                    CollectLeafSources(src.Children, result);
                continue;
            }

            if (PositionedSource.TryParse(src.SourceKey, out var positioned))
            {
                result.Add(src);
                _positionedSources[src.SourceKey] = positioned;
            }
            else if (
                _data.CharacterSpawns.TryGetValue(src.SourceKey, out var spawns)
                && spawns.Count > 0
            )
            {
                result.Add(src);
            }
            else if (src.Children != null)
            {
                CollectLeafSources(src.Children, result);
            }
        }
    }

    private bool IsSourceAvailable(Data.ItemSource source)
    {
        return source.RequiredQuestDBNames == null
            || source.RequiredQuestDBNames.TrueForAll(_state.IsGameQuestCompleted);
    }

    /// <summary>
    /// Compute the auto source set based on zone preference.
    /// In-zone sources take priority; falls back to lowest-level cross-zone source.
    /// </summary>
    private void ComputeAutoSourceSet(string currentScene)
    {
        _activeSourceKeys.Clear();

        // Find all sources with spawns/presence in the current zone
        foreach (var src in _allItemSources)
        {
            if (src.SourceKey == null)
                continue;

            if (_positionedSources.TryGetValue(src.SourceKey, out var positioned))
            {
                if (
                    string.Equals(
                        positioned.Scene,
                        currentScene,
                        System.StringComparison.OrdinalIgnoreCase
                    )
                )
                    _activeSourceKeys.Add(src.SourceKey);
                continue;
            }

            if (!_data.CharacterSpawns.TryGetValue(src.SourceKey, out var spawns))
                continue;
            if (
                spawns.Exists(s =>
                    string.Equals(s.Scene, currentScene, System.StringComparison.OrdinalIgnoreCase)
                )
            )
                _activeSourceKeys.Add(src.SourceKey);
        }

        // If no in-zone sources, pick the lowest-level source (first in list —
        // pipeline sorts by level ascending)
        if (_activeSourceKeys.Count == 0 && _allItemSources.Count > 0)
        {
            var fallback = _allItemSources[0];
            if (fallback.SourceKey != null)
                _activeSourceKeys.Add(fallback.SourceKey);
        }
    }

    /// <summary>
    /// Resolve the closest spawn among all active source keys and set as Target.
    /// Used both for initial target creation and periodic re-evaluation.
    /// </summary>
    private bool ResolveClosestActiveSource(QuestEntry quest, QuestStep step, string currentScene)
    {
        var playerPos = GetPlayerPosition() ?? Vector3.zero;
        string? bestScene = null;
        Vector3 bestPosition = Vector3.zero;
        string? bestSourceKey = null;
        float bestDistance = float.MaxValue;
        float bestRespawn = float.MaxValue;
        bool bestMined = true;
        var bestKind = NavigationTarget.Kind.Character;

        foreach (var sourceKey in _activeSourceKeys)
        {
            if (_positionedSources.TryGetValue(sourceKey, out var positioned))
            {
                if (
                    !string.Equals(
                        positioned.Scene,
                        currentScene,
                        System.StringComparison.OrdinalIgnoreCase
                    )
                )
                    continue;
                var position = new Vector3(positioned.X, positioned.Y, positioned.Z);
                var node =
                    positioned.Kind == "mining" ? _miningTracker.FindAtPosition(position) : null;
                bool mined = node != null && MiningNodeTracker.IsMined(node);
                float respawn =
                    node != null
                        ? MiningNodeTracker.GetRemainingSeconds(node) ?? float.MaxValue
                        : float.MaxValue;
                if (node != null)
                    position = node.transform.position;
                float distance = (position - playerPos).sqrMagnitude;
                if (
                    bestScene == null
                    || SourceSelectionPolicy.IsBetter(
                        mined,
                        distance,
                        respawn,
                        bestMined,
                        bestDistance,
                        bestRespawn
                    )
                )
                {
                    bestScene = currentScene;
                    bestPosition = position;
                    bestSourceKey = sourceKey;
                    bestDistance = distance;
                    bestRespawn = respawn;
                    bestMined = mined;
                    bestKind = NavigationTarget.Kind.Position;
                }
                continue;
            }

            if (!_data.CharacterSpawns.TryGetValue(sourceKey, out var spawns))
                continue;
            foreach (var spawn in spawns)
            {
                if (
                    !string.Equals(
                        spawn.Scene,
                        currentScene,
                        System.StringComparison.OrdinalIgnoreCase
                    )
                )
                    continue;
                var npc = _entities.FindClosest(sourceKey, playerPos);
                var position =
                    npc != null ? npc.transform.position : new Vector3(spawn.X, spawn.Y, spawn.Z);
                float distance = (position - playerPos).sqrMagnitude;
                if (
                    bestScene == null
                    || SourceSelectionPolicy.IsBetter(
                        false,
                        distance,
                        0f,
                        bestMined,
                        bestDistance,
                        bestRespawn
                    )
                )
                {
                    bestScene = currentScene;
                    bestPosition = position;
                    bestSourceKey = sourceKey;
                    bestDistance = distance;
                    bestMined = false;
                    bestKind = NavigationTarget.Kind.Character;
                }
            }
        }

        if (bestScene == null)
        {
            foreach (var sourceKey in _activeSourceKeys)
            {
                if (_positionedSources.TryGetValue(sourceKey, out var positioned))
                {
                    bestScene = positioned.Scene;
                    bestPosition = new Vector3(positioned.X, positioned.Y, positioned.Z);
                    bestKind = NavigationTarget.Kind.Position;
                }
                else if (
                    _data.CharacterSpawns.TryGetValue(sourceKey, out var spawns)
                    && spawns.Count > 0
                )
                {
                    bestScene = spawns[0].Scene;
                    bestPosition = new Vector3(spawns[0].X, spawns[0].Y, spawns[0].Z);
                }
                else
                    continue;
                bestSourceKey = sourceKey;
                break;
            }
        }
        if (bestScene == null)
            return false;

        _currentSourceKey = bestSourceKey;
        string displayName = bestSourceKey ?? step.TargetName ?? step.Description;
        foreach (var source in _allItemSources)
            if (
                string.Equals(
                    source.SourceKey,
                    bestSourceKey,
                    System.StringComparison.OrdinalIgnoreCase
                )
            )
            {
                displayName = source.Name ?? displayName;
                break;
            }
        displayName = WithCharacterUnlockText(displayName, bestSourceKey);
        if (Target != null && Target.SourceId == bestSourceKey && Target.TargetKind == bestKind)
        {
            Target.Position = bestPosition;
            Target.Scene = bestScene;
        }
        else
            Target = MakeTarget(
                bestKind,
                bestPosition,
                displayName,
                bestScene,
                quest.RuntimeKey,
                step.Order,
                bestSourceKey
            );
        return true;
    }

    /// <summary>Zone-only fallback for items without spawn data (fishing, etc.).</summary>
    private bool ResolveItemZoneFallback(
        List<Data.ItemSource> sources,
        QuestEntry quest,
        QuestStep step,
        string currentScene
    )
    {
        var firstSource = FindFirstSourceWithScene(sources);
        var firstScene = firstSource?.Scene;
        string? zoneKey =
            firstScene != null
                ? FindZoneKeyBySceneName(firstScene)
                : FindZoneKeyByDisplayName(sources[0].Zone);
        if (zoneKey == null)
            return false;

        string? destScene = null;
        foreach (var kvp in _data.ZoneLookup)
        {
            if (
                string.Equals(
                    kvp.Value.StableKey,
                    zoneKey,
                    System.StringComparison.OrdinalIgnoreCase
                )
            )
            {
                destScene = kvp.Key;
                break;
            }
        }
        if (destScene == null)
            return false;

        string displayName = firstSource?.Zone ?? destScene;
        string? sourceId = firstSource?.MakeSourceId();
        return NavigateToZone(
            destScene,
            displayName,
            sourceId!,
            quest.RuntimeKey,
            step.Order,
            currentScene
        );
    }

    // ── Cross-zone routing ─────────────────────────────────────────

    private void UpdateCrossZoneRouting(string currentScene, Vector3 playerPos)
    {
        if (_unroutableRoute.Matches(currentScene, Target!.Scene))
        {
            Distance = 0f;
            Direction = Vector3.zero;
            return;
        }
        // Only re-evaluate zone line selection when player moves significantly
        // to avoid per-frame CalculatePath calls on all zone line candidates
        bool needsRecalc =
            _cachedZoneLine == null
            || Vector3.Distance(_lastCrossZoneCalcPos, playerPos) > CrossZoneRecalcDistance;

        if (needsRecalc)
        {
            _lastCrossZoneCalcPos = playerPos;

            ZoneLineEntry? bestLine = null;
            bool routeIsLocked = false;

            // Manual pin takes priority over auto-selection
            if (
                _pinnedZoneLine != null
                && string.Equals(
                    _pinnedZoneLine.Scene,
                    currentScene,
                    System.StringComparison.OrdinalIgnoreCase
                )
            )
            {
                bestLine = _pinnedZoneLine;
                routeIsLocked = !IsZoneLineAccessible(bestLine);
            }
            else
            {
                // Clear stale pin (wrong scene or explicitly cleared)
                _pinnedZoneLine = null;

                // Use zone graph to find the correct next hop toward the target
                var route = _zoneGraph.FindRoute(currentScene, Target!.Scene);
                if (route == null)
                    _unroutableRoute.Remember(currentScene, Target.Scene);
                var nextHopZoneKey = route?.NextHopZoneKey;

                if (nextHopZoneKey != null)
                {
                    bestLine = route!.IsLocked
                        ? FindClosestZoneLineAny(nextHopZoneKey, currentScene, playerPos)
                        : FindClosestZoneLine(nextHopZoneKey, currentScene, playerPos);
                    routeIsLocked = route.IsLocked;
                }
            }

            if (
                CrossZoneWaypointPolicy.ShouldRebuild(
                    ZoneLineWaypoint != null,
                    bestLine != _cachedZoneLine,
                    _cachedRouteLocked,
                    routeIsLocked
                )
            )
            {
                _cachedZoneLine = bestLine;
                _cachedRouteLocked = routeIsLocked;
                if (bestLine != null)
                {
                    string displayText = routeIsLocked
                        ? $"To: {bestLine.DestinationDisplay}\nRequires: Complete \"{GetZoneLineLockReason(bestLine)}\""
                        : $"To: {bestLine.DestinationDisplay}";
                    ZoneLineWaypoint = MakeTarget(
                        NavigationTarget.Kind.ZoneLine,
                        new Vector3(bestLine.X, bestLine.Y, bestLine.Z),
                        displayText,
                        currentScene,
                        Target!.QuestKey,
                        Target.StepOrder
                    );
                }
                else
                {
                    ZoneLineWaypoint = null;
                }
            }
        }

        if (ZoneLineWaypoint != null)
            UpdateDistanceAndDirection(ZoneLineWaypoint.Position, playerPos);
        else
        {
            Distance = 0f;
            Direction = Vector3.zero;
        }
    }

    // ── Spawn resolution ───────────────────────────────────────────

    /// <summary>
    /// Pick the best spawn in the current scene. Prefers fully reachable
    /// spawns (PathComplete), then partially reachable (PathPartial), then
    /// the spatially closest as a last resort.
    /// </summary>
    private Data.SpawnPoint PickBestSpawn(List<Data.SpawnPoint> spawns, string currentScene)
    {
        var playerPos = GetPlayerPosition();
        Data.SpawnPoint? bestComplete = null;
        float bestCompDist = float.MaxValue;
        Data.SpawnPoint? bestPartial = null;
        float bestPartDist = float.MaxValue;
        Data.SpawnPoint? bestFallback = null;
        float bestFallDist = float.MaxValue;

        foreach (var sp in spawns)
        {
            if (!string.Equals(sp.Scene, currentScene, System.StringComparison.OrdinalIgnoreCase))
                continue;

            if (!playerPos.HasValue)
            {
                bestComplete ??= sp;
                continue;
            }

            var spPos = new Vector3(sp.X, sp.Y, sp.Z);
            float dist = Vector3.Distance(playerPos.Value, spPos);
            var reach = GetReachability(playerPos.Value, spPos);

            if (reach == NavMeshPathStatus.PathComplete)
            {
                if (dist < bestCompDist)
                {
                    bestCompDist = dist;
                    bestComplete = sp;
                }
            }
            else if (reach == NavMeshPathStatus.PathPartial)
            {
                if (dist < bestPartDist)
                {
                    bestPartDist = dist;
                    bestPartial = sp;
                }
            }
            else
            {
                if (dist < bestFallDist)
                {
                    bestFallDist = dist;
                    bestFallback = sp;
                }
            }
        }

        return bestComplete ?? bestPartial ?? bestFallback ?? spawns[0];
    }

    // ── Zone line helpers ──────────────────────────────────────────

    /// <summary>
    /// Check if a zone line is accessible to the player based on quest completion.
    /// Enabled by default with no requirements = accessible. Otherwise, any unlock
    /// group being fully completed = accessible.
    /// </summary>
    private bool IsZoneLineAccessible(ZoneLineEntry zl)
    {
        if (zl.IsEnabled && (zl.RequiredQuestGroups == null || zl.RequiredQuestGroups.Count == 0))
            return true;

        if (zl.RequiredQuestGroups == null || zl.RequiredQuestGroups.Count == 0)
            return zl.IsEnabled;

        foreach (var group in zl.RequiredQuestGroups)
        {
            if (group.TrueForAll(q => _state.IsGameQuestCompleted(q)))
                return true;
        }
        return false;
    }

    /// <summary>
    /// Get the display text describing why a zone line is locked.
    /// Returns the quest name(s) from the smallest incomplete unlock group.
    /// </summary>
    private string? GetZoneLineLockReason(ZoneLineEntry zl)
    {
        if (zl.RequiredQuestGroups == null || zl.RequiredQuestGroups.Count == 0)
            return null;

        // Find the smallest incomplete group (fewest quests to complete)
        List<string>? best = null;
        foreach (var group in zl.RequiredQuestGroups)
        {
            var incomplete = group.FindAll(q => !_state.IsGameQuestCompleted(q));
            if (incomplete.Count == 0)
                return null; // group satisfied
            if (best == null || incomplete.Count < best.Count)
                best = incomplete;
        }

        if (best == null)
            return null;

        // Look up display names for the required quests
        var names = new System.Collections.Generic.List<string>();
        foreach (var dbName in best)
        {
            var entry = _data.GetByDBName(dbName);
            names.Add(entry?.DisplayName ?? dbName);
        }
        return string.Join(" and ", names);
    }

    private ZoneLineEntry? FindClosestZoneLine(
        string destinationZoneKey,
        string currentScene,
        Vector3 playerPos
    )
    {
        ZoneLineEntry? bestComplete = null;
        float bestCompDist = float.MaxValue;
        ZoneLineEntry? bestPartial = null;
        float bestPartDist = float.MaxValue;
        ZoneLineEntry? bestFallback = null;
        float bestFallDist = float.MaxValue;

        foreach (var zl in _data.ZoneLines)
        {
            if (!string.Equals(zl.Scene, currentScene, System.StringComparison.OrdinalIgnoreCase))
                continue;
            if (
                !string.Equals(
                    zl.DestinationZoneKey,
                    destinationZoneKey,
                    System.StringComparison.OrdinalIgnoreCase
                )
            )
                continue;
            if (!IsZoneLineAccessible(zl))
                continue;

            var zlPos = new Vector3(zl.X, zl.Y, zl.Z);
            float dist = Vector3.Distance(playerPos, zlPos);
            var reach = GetReachability(playerPos, zlPos);

            if (reach == NavMeshPathStatus.PathComplete)
            {
                if (dist < bestCompDist)
                {
                    bestCompDist = dist;
                    bestComplete = zl;
                }
            }
            else if (reach == NavMeshPathStatus.PathPartial)
            {
                if (dist < bestPartDist)
                {
                    bestPartDist = dist;
                    bestPartial = zl;
                }
            }
            else
            {
                if (dist < bestFallDist)
                {
                    bestFallDist = dist;
                    bestFallback = zl;
                }
            }
        }

        return bestComplete ?? bestPartial ?? bestFallback;
    }

    /// <summary>
    /// Like FindClosestZoneLine but ignores accessibility — used to find locked
    /// zone lines when no accessible route exists, for directional guidance.
    /// </summary>
    private ZoneLineEntry? FindClosestZoneLineAny(
        string destinationZoneKey,
        string currentScene,
        Vector3 playerPos
    )
    {
        ZoneLineEntry? best = null;
        float bestDist = float.MaxValue;

        foreach (var zl in _data.ZoneLines)
        {
            if (!string.Equals(zl.Scene, currentScene, System.StringComparison.OrdinalIgnoreCase))
                continue;
            if (
                !string.Equals(
                    zl.DestinationZoneKey,
                    destinationZoneKey,
                    System.StringComparison.OrdinalIgnoreCase
                )
            )
                continue;

            float dist = Vector3.Distance(playerPos, new Vector3(zl.X, zl.Y, zl.Z));
            if (dist < bestDist)
            {
                bestDist = dist;
                best = zl;
            }
        }
        return best;
    }

    private bool HasZoneLineForDestination(string? zoneKey, string currentScene)
    {
        if (zoneKey == null)
            return false;
        foreach (var zl in _data.ZoneLines)
        {
            if (
                string.Equals(zl.Scene, currentScene, System.StringComparison.OrdinalIgnoreCase)
                && string.Equals(
                    zl.DestinationZoneKey,
                    zoneKey,
                    System.StringComparison.OrdinalIgnoreCase
                )
                && IsZoneLineAccessible(zl)
            )
                return true;
        }
        return false;
    }

    // ── Zone key resolution ────────────────────────────────────────

    private string? FindZoneKeyBySceneName(string sceneName)
    {
        return _data.ZoneLookup.TryGetValue(sceneName, out var info) ? info.StableKey : null;
    }

    private string? FindZoneKeyByDisplayName(string? displayName)
    {
        if (displayName == null)
            return null;
        foreach (var kvp in _data.ZoneLookup)
        {
            if (
                string.Equals(
                    kvp.Value.DisplayName,
                    displayName,
                    System.StringComparison.OrdinalIgnoreCase
                )
            )
                return kvp.Value.StableKey;
        }
        return null;
    }

    private Data.ItemSource? FindFirstSourceWithScene(List<Data.ItemSource> sources)
    {
        foreach (var src in sources)
        {
            if (!IsSourceAvailable(src))
                continue;
            if (src.Scene != null)
                return src;
            if (src.Children != null)
            {
                var child = FindFirstSourceWithScene(src.Children);
                if (child != null)
                    return child;
            }
        }
        return null;
    }

    // ── Reachability ────────────────────────────────────────────────────

    /// <summary>
    /// Classify a target's reachability: Complete (fully connected path),
    /// Partial (path exists but doesn't reach the exact point), or Invalid
    /// (no NavMesh connection at all). Both positions are snapped to the
    /// NavMesh surface before testing.
    /// </summary>
    private NavMeshPathStatus GetReachability(Vector3 from, Vector3 to)
    {
        if (!NavMesh.SamplePosition(from, out var fromHit, 5f, NavMesh.AllAreas))
            return NavMeshPathStatus.PathInvalid;
        if (!NavMesh.SamplePosition(to, out var toHit, 5f, NavMesh.AllAreas))
            return NavMeshPathStatus.PathInvalid;

        _scratchPath.ClearCorners();
        NavMesh.CalculatePath(fromHit.position, toHit.position, NavMesh.AllAreas, _scratchPath);
        return _scratchPath.status;
    }

    // ── Utilities ──────────────────────────────────────────────────

    private void UpdateDistanceAndDirection(Vector3 targetPos, Vector3 playerPos)
    {
        var delta = targetPos - playerPos;
        Distance = delta.magnitude;
        Direction = Distance > 0.1f ? delta.normalized : Vector3.zero;
    }

    private static Vector3? GetPlayerPosition()
    {
        var pc = GameData.PlayerControl;
        return pc != null ? pc.transform.position : null;
    }

    /// <summary>
    /// If a character has unmet quest unlock requirements, append a
    /// "Requires: Complete ..." line to the display name for the arrow.
    /// </summary>
    private string WithCharacterUnlockText(string displayName, string? targetKey)
    {
        if (targetKey == null)
            return displayName;
        if (!_data.CharacterQuestUnlocks.TryGetValue(targetKey, out var groups))
            return displayName;

        // Find smallest incomplete group
        List<string>? best = null;
        foreach (var group in groups)
        {
            var incomplete = group.FindAll(q => !_state.IsGameQuestCompleted(q));
            if (incomplete.Count == 0)
                return displayName; // group satisfied, NPC available
            if (best == null || incomplete.Count < best.Count)
                best = incomplete;
        }

        if (best == null)
            return displayName;

        var names = new System.Collections.Generic.List<string>();
        foreach (var dbName in best)
        {
            var entry = _data.GetByDBName(dbName);
            names.Add(entry?.DisplayName ?? dbName);
        }
        return $"{displayName}\nRequires: Complete \"{string.Join("\" and \"", names)}\"";
    }

    /// <summary>
    /// Fill the reusable item set for the resolved navigation step.
    /// </summary>
    private HashSet<string> BuildNeededItems(string questKey)
    {
        CorpsePriorityPolicy.FillItems(
            _resolvedStep,
            _data.GetByRuntimeKey(questKey),
            _countItem,
            _neededItems
        );
        return _neededItems;
    }

    private NavigationTarget MakeTarget(
        NavigationTarget.Kind kind,
        Vector3 position,
        string displayName,
        string scene,
        string questKey,
        int stepOrder,
        string? sourceId = null
    )
    {
        return new NavigationTarget(
            kind,
            position,
            displayName,
            scene,
            questKey,
            stepOrder,
            sourceId,
            _originQuestKey,
            _originStepOrder
        );
    }
}
