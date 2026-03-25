using AdventureGuide.Data;

namespace AdventureGuide.State;

/// <summary>
/// Tracks player quest state from Harmony patch callbacks.
/// Caches inventory counts and detects implicitly active quests
/// (those without acquisition sources that become active when the
/// player enters the quest's completion zone).
/// </summary>
public sealed class QuestStateTracker
{
    private readonly HashSet<string> _activeQuests = new(StringComparer.OrdinalIgnoreCase);
    private readonly HashSet<string> _completedQuests = new(StringComparer.OrdinalIgnoreCase);

    // Quests without acquisition sources — pre-computed once from guide data.
    // Each entry stores the completion scene (last step's zone). The quest
    // activates implicitly when the player enters that scene.
    private readonly List<ImplicitQuest> _implicitQuests;
    private readonly HashSet<string> _implicitlyActiveQuests = new(StringComparer.OrdinalIgnoreCase);

    // Cached inventory counts, invalidated on inventory/zone/quest changes.
    // The implicit quest set is rebuilt from the same trigger.
    private readonly Dictionary<string, int> _inventoryCache = new(StringComparer.OrdinalIgnoreCase);
    private bool _dirty = true;

    /// <summary>
    /// Monotonically increasing version. Consumers compare against their
    /// own snapshot to detect whether quest state changed since their last
    /// check. Avoids the multi-consumer race of a bool that one reader clears.
    /// </summary>
    public int Version { get; private set; }
    public string CurrentZone { get; set; } = "";
    public string? SelectedQuestDBName { get; set; }

    private NavigationHistory? _history;

    public QuestStateTracker(GuideData data)
    {
        // Pre-compute the list of quests without acquisition sources and
        // the scene where they can be completed. Quests without steps are
        // excluded — there's nothing to show markers for.
        _implicitQuests = new List<ImplicitQuest>();
        foreach (var quest in data.All)
        {
            if (!quest.HasNoAcquisition) continue;
            if (quest.Steps == null || quest.Steps.Count == 0) continue;

            // Activation scene: the zone of the last step (turn-in/completion).
            var lastStep = quest.Steps[quest.Steps.Count - 1];
            string? scene = StepSceneResolver.ResolveScene(quest, lastStep, data);

            _implicitQuests.Add(new ImplicitQuest(quest.DBName, scene));
        }
    }

    /// <summary>Wire navigation history. Call from Plugin.Awake after construction.</summary>
    public void SetHistory(NavigationHistory history) => _history = history;

    /// <summary>
    /// Select a quest via user action. Pushes onto navigation history.
    /// Use for list clicks, prerequisite links, sub-tree quest links.
    /// </summary>
    public void SelectQuest(string dbName)
    {
        if (dbName == SelectedQuestDBName) return;
        _history?.Navigate(new NavigationHistory.PageRef(
            NavigationHistory.PageType.Quest, dbName));
        SelectedQuestDBName = dbName;
    }

    public IReadOnlyCollection<string> ActiveQuests => _activeQuests;
    public IReadOnlyCollection<string> CompletedQuests => _completedQuests;

    /// <summary>
    /// A quest is active if the game has assigned it, or if it has no
    /// acquisition source and the player is in the completion zone.
    /// </summary>
    public bool IsActive(string dbName)
    {
        if (_activeQuests.Contains(dbName)) return true;
        EnsureCacheCurrent();
        return _implicitlyActiveQuests.Contains(dbName);
    }

    public bool IsCompleted(string dbName) => _completedQuests.Contains(dbName);

    /// <summary>Sync from live GameData state. Called on scene load and periodically.</summary>
    public void SyncFromGameData()
    {
        _activeQuests.Clear();
        _completedQuests.Clear();

        if (GameData.HasQuest != null)
            foreach (var q in GameData.HasQuest)
                _activeQuests.Add(q);

        if (GameData.CompletedQuests != null)
            foreach (var q in GameData.CompletedQuests)
                _completedQuests.Add(q);

        _dirty = true;
        Version++;
    }

    public void OnQuestAssigned(string dbName)
    {
        _activeQuests.Add(dbName);
        // Quest acceptance can give items (e.g., Kio's Papers gives a
        // leave order). Mark dirty so collect-step progress reflects
        // the new item on the next check.
        _dirty = true;
        Version++;
    }

    public void OnQuestCompleted(string dbName)
    {
        _activeQuests.Remove(dbName);
        _completedQuests.Add(dbName);
        // Completion may consume items; refresh cache.
        _dirty = true;
        Version++;
    }

    public void OnInventoryChanged()
    {
        _dirty = true;
        Version++;
    }

    public void OnSceneChanged(string sceneName)
    {
        CurrentZone = sceneName;
        SyncFromGameData();
    }

    /// <summary>
    /// Count items matching a stable key in the player inventory.
    /// Stable keys are derived from the Unity object name:
    /// "item:" + objectName.Trim().ToLowerInvariant().
    /// </summary>
    public int CountItem(string itemStableKey)
    {
        EnsureCacheCurrent();
        return _inventoryCache.TryGetValue(itemStableKey, out int count) ? count : 0;
    }

    // ── Cache rebuild ───────────────────────────────────────────────────

    private void EnsureCacheCurrent()
    {
        if (!_dirty) return;
        RebuildInventoryCache();
        RebuildImplicitQuests();
    }

    private void RebuildInventoryCache()
    {
        _inventoryCache.Clear();
        _dirty = false;

        if (GameData.PlayerInv?.StoredSlots == null) return;

        foreach (var slot in GameData.PlayerInv.StoredSlots)
        {
            if (slot?.MyItem != null)
            {
                // Key by stable key format matching the export pipeline.
                // Uses Unity object name (MyItem.name), not display name
                // (MyItem.ItemName), because display names are ambiguous
                // (e.g. multiple "Soul Gem" items for different quests).
                var key = "item:" + slot.MyItem.name.Trim().ToLowerInvariant();
                _inventoryCache[key] = _inventoryCache.TryGetValue(key, out int c) ? c + 1 : 1;
            }
        }
    }

    /// <summary>
    /// Rebuild the set of implicitly active quests. A quest activates
    /// implicitly when it has no acquisition source and the player is
    /// in the quest's completion zone. Items are not checked — the quest
    /// activates to show markers for all relevant NPCs and objectives.
    /// </summary>
    private void RebuildImplicitQuests()
    {
        _implicitlyActiveQuests.Clear();

        foreach (var iq in _implicitQuests)
        {
            if (_activeQuests.Contains(iq.DBName) || _completedQuests.Contains(iq.DBName))
                continue;

            // Zone gate: must be in the completion scene.
            // Quests with unresolvable scenes never activate implicitly.
            if (iq.ActivationScene == null) continue;
            if (!string.Equals(iq.ActivationScene, CurrentZone, System.StringComparison.OrdinalIgnoreCase))
                continue;

            _implicitlyActiveQuests.Add(iq.DBName);
        }
    }

    /// <summary>
    /// Pre-computed data for an implicit quest: no acquisition source,
    /// activates when the player enters the completion zone.
    /// </summary>
    private readonly struct ImplicitQuest
    {
        public readonly string DBName;
        public readonly string? ActivationScene;

        public ImplicitQuest(string dbName, string? activationScene)
        {
            DBName = dbName;
            ActivationScene = activationScene;
        }
    }
}