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

    public bool IsDirty { get; set; }
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
        IsDirty = true;
    }

    public void OnQuestAssigned(string dbName)
    {
        _activeQuests.Add(dbName);
        // Quest acceptance can give items (e.g., Kio's Papers gives a
        // leave order). Mark inventory dirty so collect-step progress
        // reflects the new item on the next check.
        _inventoryDirty = true;
        IsDirty = true;
    }

    public void OnQuestCompleted(string dbName)
    {
        _activeQuests.Remove(dbName);
        _completedQuests.Add(dbName);
        // Completion may consume items; refresh cache.
        _inventoryDirty = true;
        IsDirty = true;
    }

    public void OnInventoryChanged()
    {
        _inventoryDirty = true;
        IsDirty = true;
    }

    public void OnSceneChanged(string sceneName)
    {
        CurrentZone = sceneName;
        SyncFromGameData();
    }

    /// <summary>Count items matching a display name in player inventory (cached).</summary>
    public int CountItemInInventory(string itemDisplayName)
    {
        if (_inventoryDirty)
            RebuildInventoryCache();

        return _inventoryCache.TryGetValue(itemDisplayName, out int count) ? count : 0;
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
                var name = slot.MyItem.ItemName;
                _inventoryCache[name] = _inventoryCache.TryGetValue(name, out int c) ? c + 1 : 1;
            }
        }
    }
}
