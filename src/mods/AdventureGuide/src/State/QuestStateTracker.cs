using AdventureGuide.Graph;

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

    // Quests without acquisition sources — pre-computed once from graph.
    // Each entry stores the completion scene. The quest activates
    // implicitly when the player enters that scene.
    private readonly List<ImplicitQuest> _implicitQuests;
    private readonly HashSet<string> _implicitlyActiveQuests = new(StringComparer.OrdinalIgnoreCase);

    // Cached inventory counts, invalidated on inventory/zone/quest changes.
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

    public QuestStateTracker(EntityGraph graph)
    {
        // Pre-compute implicit quests from the graph. A quest is implicit
        // when it has no acquisition source (Node.Implicit == true). The
        // activation scene comes from the COMPLETED_BY edge target's scene.
        _implicitQuests = new List<ImplicitQuest>();
        foreach (var quest in graph.NodesOfType(NodeType.Quest))
        {
            if (!quest.Implicit) continue;
            if (quest.DbName == null) continue;

            // Find the completion scene from the COMPLETED_BY edge target
            string? scene = null;
            var completedByEdges = graph.OutEdges(quest.Key, EdgeType.CompletedBy);
            if (completedByEdges.Count > 0)
            {
                var targetNode = graph.GetNode(completedByEdges[0].Target);
                scene = targetNode?.Scene;
            }

            _implicitQuests.Add(new ImplicitQuest(quest.DbName, scene));
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
    /// True when the quest is game-assigned (in the player's quest journal).
    /// Does NOT include implicitly active quests.
    /// </summary>
    public bool IsActive(string dbName) => _activeQuests.Contains(dbName);

    /// <summary>
    /// True when the quest is actionable — either game-assigned or implicitly
    /// active (no acquisition source, player is in the completion zone).
    /// Use for marker eligibility, step progress, and navigation.
    /// </summary>
    public bool IsActionable(string dbName)
    {
        if (_activeQuests.Contains(dbName)) return true;
        EnsureCacheCurrent();
        return _implicitlyActiveQuests.Contains(dbName);
    }

    /// <summary>
    /// True when the quest is implicitly active (no acquisition source,
    /// player is in the completion zone) but not game-assigned.
    /// </summary>
    public bool IsImplicitlyActive(string dbName)
    {
        if (_activeQuests.Contains(dbName)) return false;
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
        _dirty = true;
        Version++;
    }

    public void OnQuestCompleted(string dbName)
    {
        _activeQuests.Remove(dbName);
        _completedQuests.Add(dbName);
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
                var key = "item:" + slot.MyItem.name.Trim().ToLowerInvariant();
                _inventoryCache[key] = _inventoryCache.TryGetValue(key, out int c) ? c + 1 : 1;
            }
        }
    }

    /// <summary>
    /// Rebuild the set of implicitly active quests. A quest activates
    /// implicitly when it has no acquisition source and the player is
    /// in the quest's completion zone.
    /// </summary>
    private void RebuildImplicitQuests()
    {
        _implicitlyActiveQuests.Clear();

        foreach (var iq in _implicitQuests)
        {
            if (_activeQuests.Contains(iq.DBName) || _completedQuests.Contains(iq.DBName))
                continue;

            if (iq.ActivationScene == null) continue;
            if (!string.Equals(iq.ActivationScene, CurrentZone, System.StringComparison.OrdinalIgnoreCase))
                continue;

            _implicitlyActiveQuests.Add(iq.DBName);
        }
    }

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
