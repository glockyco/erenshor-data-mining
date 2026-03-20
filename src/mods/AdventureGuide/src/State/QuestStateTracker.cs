namespace AdventureGuide.State;

/// <summary>
/// Tracks player quest state from Harmony patch callbacks.
/// Provides dirty flag for lazy UI updates.
/// </summary>
public sealed class QuestStateTracker
{
    private readonly HashSet<string> _activeQuests = new(StringComparer.OrdinalIgnoreCase);
    private readonly HashSet<string> _completedQuests = new(StringComparer.OrdinalIgnoreCase);

    public bool IsDirty { get; set; }
    public string CurrentZone { get; set; } = "";
    public string? SelectedQuestDBName { get; set; }

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

        IsDirty = true;
    }

    public void OnQuestAssigned(string dbName)
    {
        _activeQuests.Add(dbName);
        IsDirty = true;
    }

    public void OnQuestCompleted(string dbName)
    {
        _activeQuests.Remove(dbName);
        _completedQuests.Add(dbName);
        IsDirty = true;
    }

    public void OnInventoryChanged() => IsDirty = true;

    public void OnSceneChanged(string sceneName)
    {
        CurrentZone = sceneName;
        SyncFromGameData();
    }

    /// <summary>Count items matching a display name in player inventory.</summary>
    public int CountItemInInventory(string itemDisplayName)
    {
        if (GameData.PlayerInv?.StoredSlots == null) return 0;

        int count = 0;
        foreach (var slot in GameData.PlayerInv.StoredSlots)
        {
            if (slot?.MyItem != null &&
                string.Equals(slot.MyItem.ItemName, itemDisplayName, StringComparison.OrdinalIgnoreCase))
            {
                count++;
            }
        }
        return count;
    }
}
