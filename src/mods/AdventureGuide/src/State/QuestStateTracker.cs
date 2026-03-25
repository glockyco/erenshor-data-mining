namespace AdventureGuide.State;

/// <summary>
/// Tracks player quest state from Harmony patch callbacks.
/// Caches inventory counts and step progress to avoid per-frame scans.
/// </summary>
public sealed class QuestStateTracker
{
    private readonly HashSet<string> _activeQuests = new(StringComparer.OrdinalIgnoreCase);
    private readonly HashSet<string> _completedQuests = new(StringComparer.OrdinalIgnoreCase);

    // Cached inventory counts, invalidated on OnInventoryChanged
    private readonly Dictionary<string, int> _inventoryCache = new(StringComparer.OrdinalIgnoreCase);
    private bool _inventoryDirty = true;

    /// <summary>
    /// Monotonically increasing version. Consumers compare against their
    /// own snapshot to detect whether quest state changed since their last
    /// check. Avoids the multi-consumer race of a bool that one reader clears.
    /// </summary>
    public int Version { get; private set; }
    public string CurrentZone { get; set; } = "";
    public string? SelectedQuestDBName { get; set; }

    private NavigationHistory? _history;

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

    public bool IsActive(string dbName) => _activeQuests.Contains(dbName);
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

        _inventoryDirty = true;
        Version++;
    }

    public void OnQuestAssigned(string dbName)
    {
        _activeQuests.Add(dbName);
        // Quest acceptance can give items (e.g., Kio's Papers gives a
        // leave order). Mark inventory dirty so collect-step progress
        // reflects the new item on the next check.
        _inventoryDirty = true;
        Version++;
    }

    public void OnQuestCompleted(string dbName)
    {
        _activeQuests.Remove(dbName);
        _completedQuests.Add(dbName);
        // Completion may consume items; refresh cache.
        _inventoryDirty = true;
        Version++;
    }

    public void OnInventoryChanged()
    {
        _inventoryDirty = true;
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
        if (_inventoryDirty)
            RebuildInventoryCache();

        return _inventoryCache.TryGetValue(itemStableKey, out int count) ? count : 0;
    }

    private void RebuildInventoryCache()
    {
        _inventoryCache.Clear();
        _inventoryDirty = false;

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
}
