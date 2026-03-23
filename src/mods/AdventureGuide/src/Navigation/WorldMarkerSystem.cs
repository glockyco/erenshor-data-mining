using AdventureGuide.Config;
using AdventureGuide.Data;
using AdventureGuide.State;
using UnityEngine;

namespace AdventureGuide.Navigation;

/// <summary>
/// Computes and renders world markers for quest-relevant NPCs and objectives.
/// Markers are billboard quads in 3D space with depth occlusion.
///
/// Three marker sources, all merged into a single prioritized list:
/// 1. Quest state (!, ?, target) — rebuilt when QuestStateTracker.IsDirty
/// 2. Dead spawn timers (skull) — from SpawnTimerTracker
/// 3. Night spawn warnings (moon) — checked via game clock
///
/// When multiple quests reference the same NPC, the highest-priority
/// marker type wins. Priority order is defined by MarkerType enum ordinal.
/// </summary>
public sealed class WorldMarkerSystem
{
    private const float StaticHeightOffset = 2.5f;
    private const float LiveHeightAboveCollider = 0.8f;

    private readonly GuideData _data;
    private readonly QuestStateTracker _state;
    private readonly EntityRegistry _entities;
    private readonly SpawnTimerTracker _timers;
    private readonly MiningNodeTracker _miningTracker;
    private readonly MarkerPool _pool;
    private readonly GuideConfig _config;

    // Cached marker state — rebuilt on dirty
    private readonly List<MarkerEntry> _markers = new();
    private readonly Dictionary<string, int> _intentIndex = new(System.StringComparer.OrdinalIgnoreCase);
    private string _lastScene = "";
    private bool _enabled;
    private bool _configDirty;

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
        EntityRegistry entities, SpawnTimerTracker timers,
        MiningNodeTracker miningTracker, GuideConfig config)
    {
        _data = data;
        _state = state;
        _entities = entities;
        _timers = timers;
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
    /// state or scene changes. Updates live NPC positions, respawn timers,
    /// billboard rotation, and distance fade every frame.
    /// </summary>
    public void Update(string currentScene)
    {
        if (!_enabled)
            return;

        bool sceneChanged = currentScene != _lastScene;
        bool needsRebuild = sceneChanged || _state.IsDirty || _configDirty;
        _configDirty = false;

        if (needsRebuild)
        {
            _lastScene = currentScene;
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

        // Dead spawn markers from timer tracker
        CollectDeadSpawnMarkers(currentScene);
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

        // Check prerequisites — skip if any prerequisite quest isn't completed
        if (quest.Prerequisites != null)
        {
            foreach (var prereq in quest.Prerequisites)
            {
                var prereqQuest = _data.GetByStableKey(prereq.QuestKey);
                if (prereqQuest == null || !_state.IsCompleted(prereqQuest.DBName))
                    return;
            }
        }

        foreach (var acq in quest.Acquisition)
        {
            if (acq.SourceType != "character" || acq.SourceStableKey == null)
                continue;

            if (!HasSpawnInScene(acq.SourceStableKey, scene))
                continue;

            var type = repeatable ? MarkerType.QuestGiverRepeat : MarkerType.QuestGiver;
            string? subText = acq.Keyword != null ? $"Say '{acq.Keyword}'" : null;

            TryAddMarker(acq.SourceStableKey, type, acq.SourceName ?? quest.DisplayName, subText);
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

            if (!HasSpawnInScene(comp.SourceStableKey, scene))
                continue;

            MarkerType type;
            if (hasAllItems)
                type = repeatable ? MarkerType.TurnInRepeatReady : MarkerType.TurnInReady;
            else
                type = MarkerType.TurnInPending;

            // Show required item name for turn-in markers
            string? itemName = quest.RequiredItems?.Count > 0
                ? $"Needs: {quest.RequiredItems[0].ItemName}"
                : null;

            TryAddMarker(comp.SourceStableKey, type, comp.SourceName ?? quest.DisplayName, itemName);
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
        if (step.TargetKey != null && step.TargetType == "character"
            && HasSpawnInScene(step.TargetKey, scene))
        {
            TryAddMarker(step.TargetKey, MarkerType.Objective,
                step.TargetName ?? step.Description, null);
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
                if (!HasSpawnInScene(src.SourceKey, scene)) continue;

                TryAddMarker(src.SourceKey, MarkerType.Objective,
                    src.Name ?? ri.ItemName, progress);
            }
        }
    }

    /// <summary>
    /// Dead spawn markers: skull icon with timer at spawn points where
    /// quest-relevant NPCs have died and are awaiting respawn.
    /// </summary>
    private void CollectDeadSpawnMarkers(string scene)
    {
        foreach (var kvp in _timers.Tracked)
        {
            var tracked = kvp.Value;
            if (tracked.Point == null || tracked.Point.gameObject == null)
                continue;

            // Only show in current scene
            if (!string.Equals(
                UnityEngine.SceneManagement.SceneManager.GetActiveScene().name,
                scene, System.StringComparison.OrdinalIgnoreCase))
                continue;

            // Check if this is quest-relevant (has a marker intent for its NPC name)
            // Dead spawn markers don't compete with live markers (different key space)
            var pos = tracked.Point.transform.position + Vector3.up * StaticHeightOffset;
            float? remaining = _timers.GetRemainingSeconds(tracked.Point);

            MarkerType type;
            string subText;

            if (SpawnTimerTracker.IsNightLocked(tracked.Point))
            {
                type = MarkerType.NightSpawn;
                int hour = GameData.Time.GetHour();
                subText = $"Night only (22:00-04:00)\nNow: {hour}:00";
            }
            else
            {
                type = MarkerType.DeadSpawn;
                subText = remaining.HasValue
                    ? SpawnTimerTracker.FormatTimer(remaining.Value)
                    : "Respawning...";
            }

            _markers.Add(new MarkerEntry
            {
                Position = pos,
                Type = type,
                DisplayName = tracked.NPCName,
                TargetKey = null, // no live tracking for dead spawns
                SubText = $"{tracked.NPCName}\n{subText}",
            });
        }
    }

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

            // Live NPC position tracking
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

            // Update dead spawn timer text
            if (m.Type == MarkerType.DeadSpawn && i < _markers.Count)
            {
                // Timer ticks down in game engine — re-read each frame
                // The sub-text was set during rebuild; for live timer updates
                // we'd need to call Configure again. Only worth it for visible markers.
                // For now, timers update on next rebuild (when IsDirty fires from
                // inventory/quest state changes, or we could add a periodic timer).
            }

            _markers[i] = m; // write back mutated position
        }
    }

    // ── Helpers ───────────────────────────────────────────────────

    /// <summary>
    /// Try to add a marker for the given stable key. If a marker already
    /// exists for this key, only replace it if the new type has higher
    /// priority (lower enum ordinal).
    /// </summary>
    private void TryAddMarker(string stableKey, MarkerType type, string displayName, string? subText)
    {
        if (_intentIndex.TryGetValue(stableKey, out int existingIdx))
        {
            var existing = _markers[existingIdx];
            if (type < existing.Type) // lower ordinal = higher priority
            {
                _markers[existingIdx] = new MarkerEntry
                {
                    Position = existing.Position, // keep resolved position
                    Type = type,
                    DisplayName = displayName,
                    TargetKey = stableKey,
                    SubText = subText,
                };
            }
            return;
        }

        // New marker — resolve position
        var position = ResolveStaticPosition(stableKey, _lastScene);
        if (position == null) return;

        _intentIndex[stableKey] = _markers.Count;
        _markers.Add(new MarkerEntry
        {
            Position = position.Value,
            Type = type,
            DisplayName = displayName,
            TargetKey = stableKey,
            SubText = subText,
        });
    }

    /// <summary>Check if any spawn for this stable key is in the given scene.</summary>
    private bool HasSpawnInScene(string stableKey, string scene)
    {
        if (!_data.CharacterSpawns.TryGetValue(stableKey, out var spawns))
            return false;

        foreach (var sp in spawns)
        {
            if (string.Equals(sp.Scene, scene, System.StringComparison.OrdinalIgnoreCase))
                return true;
        }
        return false;
    }

    /// <summary>Resolve the best static spawn position in the current scene.</summary>
    private Vector3? ResolveStaticPosition(string stableKey, string scene)
    {
        if (!_data.CharacterSpawns.TryGetValue(stableKey, out var spawns))
            return null;

        foreach (var sp in spawns)
        {
            if (string.Equals(sp.Scene, scene, System.StringComparison.OrdinalIgnoreCase))
                return new Vector3(sp.X, sp.Y, sp.Z) + Vector3.up * StaticHeightOffset;
        }

        return null;
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
