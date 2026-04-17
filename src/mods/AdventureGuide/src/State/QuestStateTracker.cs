using AdventureGuide.Graph;
using CompiledGuideModel = AdventureGuide.CompiledGuide.CompiledGuide;

namespace AdventureGuide.State;

/// <summary>
/// Central mutable runtime guide state.
/// Tracks quest journal state, inventory counts, keyring-backed unlock possession,
/// current scene, selected quest, and emits structured deltas so downstream
/// systems can invalidate maintained views from precise fact changes rather than
/// broad version bumps.
/// </summary>
public sealed class QuestStateTracker
{
    private readonly CompiledGuideModel _guide;
    private readonly GuideDependencyEngine _dependencies;

    private readonly HashSet<string> _activeQuests = new(StringComparer.OrdinalIgnoreCase);
    private readonly HashSet<string> _completedQuests = new(StringComparer.OrdinalIgnoreCase);
    private readonly Dictionary<string, int> _inventoryCounts = new(StringComparer.Ordinal);
    private readonly HashSet<string> _keyringItemKeys = new(StringComparer.Ordinal);
    private readonly List<ImplicitQuest> _implicitQuests;
    private readonly HashSet<string> _implicitlyAvailableQuests = new(
        StringComparer.OrdinalIgnoreCase
    );

    private NavigationHistory? _history;
    private string _currentZone = string.Empty;

    public int Version { get; private set; }
    public int QuestLogVersion { get; private set; }
    public int InventoryVersion { get; private set; }
    public int SceneVersion { get; private set; }

    public string CurrentZone
    {
        get
        {
            _dependencies.RecordFact(new GuideFactKey(GuideFactKind.Scene, "current"));
            return _currentZone;
        }
        private set => _currentZone = value ?? string.Empty;
    }

    public string? SelectedQuestDBName { get; set; }
    public GuideChangeSet LastChangeSet { get; private set; } = GuideChangeSet.None;

    public IReadOnlyCollection<string> ActiveQuests => _activeQuests;
    public IReadOnlyCollection<string> CompletedQuests => _completedQuests;
    public IReadOnlyDictionary<string, int> InventoryCounts => _inventoryCounts;
    public IReadOnlyCollection<string> KeyringItems => _keyringItemKeys;

    public QuestStateTracker(CompiledGuideModel guide, GuideDependencyEngine dependencies)
    {
        _guide = guide;
        _dependencies = dependencies;
        _implicitQuests = BuildImplicitQuestIndex(guide);
    }

    /// <summary>
    /// Replaces the tracked quest, inventory, and scene state from a deterministic
    /// snapshot without reading live <c>GameData</c>. Used by snapshot replay and
    /// test harnesses.
    /// </summary>
    internal void LoadState(
        string? currentZone,
        IReadOnlyCollection<string>? activeQuests,
        IReadOnlyCollection<string>? completedQuests,
        IReadOnlyDictionary<string, int>? inventoryCounts,
        IReadOnlyCollection<string>? keyringItemKeys
    )
    {
        CurrentZone = currentZone ?? string.Empty;
        ReplaceSet(_activeQuests, activeQuests ?? Array.Empty<string>());
        ReplaceSet(_completedQuests, completedQuests ?? Array.Empty<string>());
        ReplaceInventoryCounts(
            inventoryCounts ?? new Dictionary<string, int>(StringComparer.Ordinal)
        );
        ReplaceKeyringItemKeys(keyringItemKeys ?? Array.Empty<string>());
        RebuildImplicitlyAvailableQuests();

        SelectedQuestDBName = null;
        LastChangeSet = GuideChangeSet.None;
        Version = 0;
        QuestLogVersion = 0;
        InventoryVersion = 0;
        SceneVersion = 0;
    }

    public void SetHistory(NavigationHistory history) => _history = history;

    public void SelectQuest(string dbName)
    {
        if (dbName == SelectedQuestDBName)
            return;

        _history?.Navigate(new NavigationHistory.PageRef(NavigationHistory.PageType.Quest, dbName));
        SelectedQuestDBName = dbName;
    }

    public bool IsActive(string dbName)
    {
        _dependencies.RecordFact(new GuideFactKey(GuideFactKind.QuestActive, dbName));
        return _activeQuests.Contains(dbName);
    }

    public bool IsImplicitlyAvailable(string dbName)
    {
        _dependencies.RecordFact(new GuideFactKey(GuideFactKind.Scene, "current"));
        return !_activeQuests.Contains(dbName) && _implicitlyAvailableQuests.Contains(dbName);
    }

    public bool IsActionable(string dbName) => IsActive(dbName);

    public bool IsCompleted(string dbName)
    {
        _dependencies.RecordFact(new GuideFactKey(GuideFactKind.QuestCompleted, dbName));
        return _completedQuests.Contains(dbName);
    }

    public int CountItem(string itemStableKey)
    {
        _dependencies.RecordFact(new GuideFactKey(GuideFactKind.InventoryItemCount, itemStableKey));
        return _inventoryCounts.TryGetValue(itemStableKey, out var count) ? count : 0;
    }

    public bool HasUnlockItem(string itemStableKey)
    {
        _dependencies.RecordFact(
            new GuideFactKey(GuideFactKind.UnlockItemPossessed, itemStableKey)
        );
        return (_inventoryCounts.TryGetValue(itemStableKey, out var count) && count > 0)
            || _keyringItemKeys.Contains(itemStableKey);
    }

    public IEnumerable<string> GetActionableQuestDbNames()
    {
        foreach (var quest in _activeQuests)
            yield return quest;
    }

    public IEnumerable<string> GetImplicitlyAvailableQuestDbNames() => _implicitlyAvailableQuests;

    public GuideChangeSet SyncFromGameData() => FinalizeChange(BuildSyncChangeSet());

    public GuideChangeSet OnQuestAssigned(string dbName)
    {
        bool changed = _activeQuests.Add(dbName);
        if (!changed)
            return GuideChangeSet.None;

        RebuildImplicitlyAvailableQuests();

        return FinalizeChange(
            new GuideChangeSet(
                inventoryChanged: false,
                questLogChanged: true,
                sceneChanged: false,
                liveWorldChanged: false,
                changedItemKeys: Array.Empty<string>(),
                changedQuestDbNames: new[] { dbName },
                affectedQuestKeys: CollectAffectedQuestKeysForQuestDbNames(new[] { dbName }),
                changedFacts: new[]
                {
                    new GuideFactKey(GuideFactKind.QuestActive, dbName),
                    new GuideFactKey(GuideFactKind.QuestCompleted, dbName),
                }
            )
        );
    }

    public GuideChangeSet OnQuestCompleted(string dbName)
    {
        bool removed = _activeQuests.Remove(dbName);
        bool added = _completedQuests.Add(dbName);
        if (!removed && !added)
            return GuideChangeSet.None;

        RebuildImplicitlyAvailableQuests();

        return FinalizeChange(
            new GuideChangeSet(
                inventoryChanged: false,
                questLogChanged: true,
                sceneChanged: false,
                liveWorldChanged: false,
                changedItemKeys: Array.Empty<string>(),
                changedQuestDbNames: new[] { dbName },
                affectedQuestKeys: CollectAffectedQuestKeysForQuestDbNames(new[] { dbName }),
                changedFacts: new[]
                {
                    new GuideFactKey(GuideFactKind.QuestActive, dbName),
                    new GuideFactKey(GuideFactKind.QuestCompleted, dbName),
                }
            )
        );
    }

    public GuideChangeSet OnInventoryChanged()
    {
        if (!TryBuildInventorySnapshot(out var snapshot))
            return GuideChangeSet.None;

        var changedItemKeys = CollectChangedItemKeys(snapshot.Counts);
        var changedUnlockItemKeys = CollectChangedUnlockItemKeys(
            snapshot.Counts,
            snapshot.KeyringItemKeys
        );
        if (changedItemKeys.Count == 0 && changedUnlockItemKeys.Count == 0)
            return GuideChangeSet.None;

        ReplaceInventoryCounts(snapshot.Counts);
        ReplaceKeyringItemKeys(snapshot.KeyringItemKeys);

        var changedFacts = new List<GuideFactKey>(
            changedItemKeys.Count + changedUnlockItemKeys.Count
        );
        foreach (var itemKey in changedItemKeys)
            changedFacts.Add(new GuideFactKey(GuideFactKind.InventoryItemCount, itemKey));
        foreach (var itemKey in changedUnlockItemKeys)
            changedFacts.Add(new GuideFactKey(GuideFactKind.UnlockItemPossessed, itemKey));

        return FinalizeChange(
            new GuideChangeSet(
                inventoryChanged: true,
                questLogChanged: false,
                sceneChanged: false,
                liveWorldChanged: false,
                changedItemKeys: changedItemKeys,
                changedQuestDbNames: Array.Empty<string>(),
                affectedQuestKeys: CollectAffectedQuestKeysForItems(changedItemKeys),
                changedFacts: changedFacts
            )
        );
    }

    public GuideChangeSet OnSceneChanged(string sceneName)
    {
        bool sceneChanged = !string.Equals(
            CurrentZone,
            sceneName,
            StringComparison.OrdinalIgnoreCase
        );
        CurrentZone = sceneName ?? string.Empty;

        var sync = BuildSyncChangeSet();
        if (!sceneChanged)
            return FinalizeChange(sync);

        var sceneChange = new GuideChangeSet(
            sync.InventoryChanged,
            sync.QuestLogChanged,
            sceneChanged: true,
            liveWorldChanged: false,
            sync.ChangedItemKeys,
            sync.ChangedQuestDbNames,
            sync.AffectedQuestKeys,
            sync.ChangedFacts.Concat(new[] { new GuideFactKey(GuideFactKind.Scene, "current") })
        );

        return FinalizeChange(sceneChange);
    }

    private GuideChangeSet BuildSyncChangeSet()
    {
        var nextActive = SnapshotQuestSet(GameData.HasQuest);
        var nextCompleted = SnapshotQuestSet(GameData.CompletedQuests);
        var changedQuestDbNames = CollectChangedQuestDbNames(nextActive, nextCompleted);
        bool questLogChanged = changedQuestDbNames.Count > 0;

        ReplaceSet(_activeQuests, nextActive);
        ReplaceSet(_completedQuests, nextCompleted);

        bool inventoryChanged = false;
        HashSet<string> changedItemKeys = new(StringComparer.Ordinal);
        HashSet<string> changedUnlockItemKeys = new(StringComparer.Ordinal);
        if (TryBuildInventorySnapshot(out var inventorySnapshot))
        {
            changedItemKeys = CollectChangedItemKeys(inventorySnapshot.Counts);
            changedUnlockItemKeys = CollectChangedUnlockItemKeys(
                inventorySnapshot.Counts,
                inventorySnapshot.KeyringItemKeys
            );
            inventoryChanged = changedItemKeys.Count > 0 || changedUnlockItemKeys.Count > 0;
            ReplaceInventoryCounts(inventorySnapshot.Counts);
            ReplaceKeyringItemKeys(inventorySnapshot.KeyringItemKeys);
        }

        RebuildImplicitlyAvailableQuests();

        var affectedQuestKeys = new HashSet<string>(StringComparer.Ordinal);
        affectedQuestKeys.UnionWith(CollectAffectedQuestKeysForQuestDbNames(changedQuestDbNames));
        affectedQuestKeys.UnionWith(CollectAffectedQuestKeysForItems(changedItemKeys));

        var changedFacts = new List<GuideFactKey>(
            changedQuestDbNames.Count * 2 + changedItemKeys.Count + changedUnlockItemKeys.Count
        );
        foreach (var dbName in changedQuestDbNames)
        {
            changedFacts.Add(new GuideFactKey(GuideFactKind.QuestActive, dbName));
            changedFacts.Add(new GuideFactKey(GuideFactKind.QuestCompleted, dbName));
        }

        foreach (var itemKey in changedItemKeys)
            changedFacts.Add(new GuideFactKey(GuideFactKind.InventoryItemCount, itemKey));
        foreach (var itemKey in changedUnlockItemKeys)
            changedFacts.Add(new GuideFactKey(GuideFactKind.UnlockItemPossessed, itemKey));

        return new GuideChangeSet(
            inventoryChanged,
            questLogChanged,
            sceneChanged: false,
            liveWorldChanged: false,
            changedItemKeys,
            changedQuestDbNames,
            affectedQuestKeys,
            changedFacts
        );
    }

    private GuideChangeSet FinalizeChange(GuideChangeSet changeSet)
    {
        if (changeSet == null || !changeSet.HasMeaningfulChanges)
            return GuideChangeSet.None;

        if (changeSet.QuestLogChanged)
            QuestLogVersion++;
        if (changeSet.InventoryChanged)
            InventoryVersion++;
        if (changeSet.SceneChanged)
            SceneVersion++;

        Version++;
        LastChangeSet = changeSet;
        return changeSet;
    }

    private static HashSet<string> SnapshotQuestSet(IEnumerable<string>? values)
    {
        var result = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        if (values == null)
            return result;

        foreach (var value in values)
        {
            if (!string.IsNullOrWhiteSpace(value))
                result.Add(value);
        }

        return result;
    }

    private HashSet<string> CollectChangedQuestDbNames(
        HashSet<string> nextActive,
        HashSet<string> nextCompleted
    )
    {
        var changed = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

        foreach (var quest in _activeQuests)
        {
            if (!nextActive.Contains(quest))
                changed.Add(quest);
        }

        foreach (var quest in nextActive)
        {
            if (!_activeQuests.Contains(quest))
                changed.Add(quest);
        }

        foreach (var quest in _completedQuests)
        {
            if (!nextCompleted.Contains(quest))
                changed.Add(quest);
        }

        foreach (var quest in nextCompleted)
        {
            if (!_completedQuests.Contains(quest))
                changed.Add(quest);
        }

        return changed;
    }

    private static List<ImplicitQuest> BuildImplicitQuestIndex(CompiledGuideModel guide)
    {
        var implicitQuests = new List<ImplicitQuest>();
        foreach (var quest in guide.NodesOfType(NodeType.Quest))
        {
            if (!quest.Implicit || string.IsNullOrEmpty(quest.DbName))
                continue;

            implicitQuests.Add(
                new ImplicitQuest(
                    quest.Key,
                    quest.DbName,
                    CollectImplicitActivationScenes(guide, quest.Key)
                )
            );
        }

        return implicitQuests;
    }

    private static HashSet<string> CollectImplicitActivationScenes(
        CompiledGuideModel guide,
        string questKey
    )
    {
        var scenes = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var completedByEdges = guide.OutEdges(questKey, EdgeType.CompletedBy);
        for (int i = 0; i < completedByEdges.Count; i++)
        {
            var targetNode = guide.GetNode(completedByEdges[i].Target);
            if (targetNode == null)
                continue;

            if (!string.IsNullOrEmpty(targetNode.Scene))
                scenes.Add(targetNode.Scene);

            if (targetNode.Type != NodeType.Character)
                continue;

            var spawnEdges = guide.OutEdges(targetNode.Key, EdgeType.HasSpawn);
            for (int j = 0; j < spawnEdges.Count; j++)
            {
                var spawnNode = guide.GetNode(spawnEdges[j].Target);
                if (!string.IsNullOrEmpty(spawnNode?.Scene))
                    scenes.Add(spawnNode.Scene);
            }
        }

        return scenes;
    }

    private void RebuildImplicitlyAvailableQuests()
    {
        _implicitlyAvailableQuests.Clear();
        foreach (var implicitQuest in _implicitQuests)
        {
            if (
                _activeQuests.Contains(implicitQuest.DbName)
                || _completedQuests.Contains(implicitQuest.DbName)
            )
                continue;

            foreach (var scene in implicitQuest.ActivationScenes)
            {
                if (!string.Equals(scene, CurrentZone, StringComparison.OrdinalIgnoreCase))
                    continue;

                _implicitlyAvailableQuests.Add(implicitQuest.DbName);
                break;
            }
        }
    }

    private bool TryBuildInventorySnapshot(out InventorySnapshot snapshot)
    {
        var slots = GameData.PlayerInv?.StoredSlots;
        if (slots == null)
        {
            snapshot = default;
            return false;
        }

        var counts = new Dictionary<string, int>(StringComparer.Ordinal);
        for (int i = 0; i < slots.Count; i++)
        {
            var slot = slots[i];
            var item = slot?.MyItem;
            if (item == null)
                continue;

            var itemKey = BuildItemStableKey(item.name);
            int quantity = slot!.Quantity > 0 ? slot.Quantity : 1;
            counts[itemKey] = counts.TryGetValue(itemKey, out var current)
                ? current + quantity
                : quantity;
        }

        var keyringItemKeys = new HashSet<string>(StringComparer.Ordinal);
        if (GameData.Keyring != null && GameData.ItemDB != null)
        {
            for (int i = 0; i < GameData.Keyring.Count; i++)
            {
                string itemId = GameData.Keyring[i];
                if (string.IsNullOrWhiteSpace(itemId))
                    continue;

                var item = GameData.ItemDB.GetItemByID(itemId);
                if (item == null)
                    continue;

                keyringItemKeys.Add(BuildItemStableKey(item.name));
            }
        }

        snapshot = new InventorySnapshot(counts, keyringItemKeys);
        return true;
    }

    private HashSet<string> CollectChangedItemKeys(IReadOnlyDictionary<string, int> nextCounts)
    {
        var changed = new HashSet<string>(StringComparer.Ordinal);

        foreach (var (itemKey, count) in _inventoryCounts)
        {
            if (!nextCounts.TryGetValue(itemKey, out var nextCount) || nextCount != count)
                changed.Add(itemKey);
        }

        foreach (var (itemKey, count) in nextCounts)
        {
            if (!_inventoryCounts.TryGetValue(itemKey, out var current) || current != count)
                changed.Add(itemKey);
        }

        return changed;
    }

    private HashSet<string> CollectAffectedQuestKeysForItems(IEnumerable<string> changedItemKeys)
    {
        var seeds = new HashSet<string>(StringComparer.Ordinal);
        foreach (var itemKey in changedItemKeys)
        {
            foreach (var questKey in _guide.GetQuestsDependingOnItem(itemKey))
                seeds.Add(questKey);
        }

        return ExpandDependentQuestClosure(seeds);
    }

    private HashSet<string> CollectAffectedQuestKeysForQuestDbNames(
        IEnumerable<string> changedQuestDbNames
    )
    {
        var seeds = new HashSet<string>(StringComparer.Ordinal);
        foreach (var dbName in changedQuestDbNames)
        {
            var quest = _guide.GetQuestByDbName(dbName);
            if (quest != null)
                seeds.Add(quest.Key);
        }

        return ExpandDependentQuestClosure(seeds);
    }

    private HashSet<string> ExpandDependentQuestClosure(IEnumerable<string> seedQuestKeys)
    {
        var closure = new HashSet<string>(StringComparer.Ordinal);
        var queue = new Queue<string>();

        foreach (var questKey in seedQuestKeys)
        {
            if (closure.Add(questKey))
                queue.Enqueue(questKey);
        }

        while (queue.Count > 0)
        {
            var current = queue.Dequeue();
            foreach (var dependent in _guide.GetQuestsDependingOnQuest(current))
            {
                if (closure.Add(dependent))
                    queue.Enqueue(dependent);
            }
        }

        return closure;
    }

    private HashSet<string> CollectChangedUnlockItemKeys(
        IReadOnlyDictionary<string, int> nextCounts,
        IReadOnlyCollection<string> nextKeyringItemKeys
    )
    {
        var changed = new HashSet<string>(StringComparer.Ordinal);
        var candidates = new HashSet<string>(StringComparer.Ordinal);

        foreach (var itemKey in _inventoryCounts.Keys)
            candidates.Add(itemKey);
        foreach (var itemKey in _keyringItemKeys)
            candidates.Add(itemKey);
        foreach (var itemKey in nextCounts.Keys)
            candidates.Add(itemKey);
        foreach (var itemKey in nextKeyringItemKeys)
            candidates.Add(itemKey);

        foreach (var itemKey in candidates)
        {
            bool currentPossessed = IsUnlockItemPossessed(
                _inventoryCounts,
                _keyringItemKeys,
                itemKey
            );
            bool nextPossessed = IsUnlockItemPossessed(nextCounts, nextKeyringItemKeys, itemKey);
            if (currentPossessed != nextPossessed)
                changed.Add(itemKey);
        }

        return changed;
    }

    private static bool IsUnlockItemPossessed(
        IReadOnlyDictionary<string, int> counts,
        IReadOnlyCollection<string> keyringItemKeys,
        string itemKey
    )
    {
        return (counts.TryGetValue(itemKey, out var count) && count > 0)
            || keyringItemKeys.Contains(itemKey);
    }

    private static void ReplaceSet(HashSet<string> target, IReadOnlyCollection<string> values)
    {
        target.Clear();
        foreach (var value in values)
            target.Add(value);
    }

    private void ReplaceInventoryCounts(IReadOnlyDictionary<string, int> nextCounts)
    {
        _inventoryCounts.Clear();
        foreach (var (itemKey, count) in nextCounts)
            _inventoryCounts[itemKey] = count;
    }

    private void ReplaceKeyringItemKeys(IReadOnlyCollection<string> nextKeyringItemKeys)
    {
        _keyringItemKeys.Clear();
        foreach (var itemKey in nextKeyringItemKeys)
            _keyringItemKeys.Add(itemKey);
    }

    private static string BuildItemStableKey(string itemName) =>
        "item:" + itemName.Trim().ToLowerInvariant();

    private readonly struct InventorySnapshot
    {
        public readonly IReadOnlyDictionary<string, int> Counts;
        public readonly IReadOnlyCollection<string> KeyringItemKeys;

        public InventorySnapshot(
            IReadOnlyDictionary<string, int> counts,
            IReadOnlyCollection<string> keyringItemKeys
        )
        {
            Counts = counts;
            KeyringItemKeys = keyringItemKeys;
        }
    }

    private readonly struct ImplicitQuest
    {
        public readonly string QuestKey;
        public readonly string DbName;
        public readonly HashSet<string> ActivationScenes;

        public ImplicitQuest(string questKey, string dbName, HashSet<string> activationScenes)
        {
            QuestKey = questKey;
            DbName = dbName;
            ActivationScenes = activationScenes;
        }
    }
}
