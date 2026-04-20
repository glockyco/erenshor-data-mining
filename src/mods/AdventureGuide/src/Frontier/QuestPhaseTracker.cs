using AdventureGuide.State;

namespace AdventureGuide.Frontier;

public sealed class QuestPhaseTracker : IDisposable
{
    private readonly CompiledGuide.CompiledGuide _guide;
    private readonly QuestStateTracker _state;
    private readonly QuestPhase[] _phases;
    private readonly int[] _remainingPrereqs;
    private readonly int[] _itemCounts;
    private readonly bool[] _completed;
    private readonly Dictionary<string, int> _dbNameToQuestIndex;
    private bool _disposed;

    public int Version { get; private set; }

    internal CompiledGuide.CompiledGuide Guide => _guide;
    internal QuestStateTracker State => _state;

    public QuestPhaseTracker(CompiledGuide.CompiledGuide guide, QuestStateTracker state)
    {
        _guide = guide;
        _state = state;
        _phases = new QuestPhase[guide.QuestCount];
        _remainingPrereqs = new int[guide.QuestCount];
        _itemCounts = new int[guide.ItemCount];
        _completed = new bool[guide.QuestCount];
        _dbNameToQuestIndex = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);

        for (int questIndex = 0; questIndex < guide.QuestCount; questIndex++)
        {
            int nodeId = guide.QuestNodeId(questIndex);
            string? dbName = guide.GetDbName(nodeId);
            if (string.IsNullOrEmpty(dbName))
                continue;

            _dbNameToQuestIndex[dbName] = questIndex;
        }

        state.LoadedEvent += OnStateLoaded;
        state.QuestLogChangedEvent += OnQuestLogChanged;
        state.InventoryChangedEvent += OnInventoryChanged;
        OnStateLoaded(state.LastChangeSet);
    }

    public QuestPhaseTracker(CompiledGuide.CompiledGuide guide)
        : this(guide, CreateDetachedState(guide)) { }

    public QuestPhase GetPhase(int questIndex)
    {
        RecordQuestFacts(questIndex);
        return _phases[questIndex];
    }

    public bool IsCompleted(int questIndex)
    {
        RecordQuestCompletedFact(questIndex);
        return _completed[questIndex];
    }

    public int GetItemCount(int itemIndex)
    {
        RecordItemCountFact(itemIndex);
        return _itemCounts[itemIndex];
    }

    internal QuestPhase[] SnapshotPhases() => (QuestPhase[])_phases.Clone();

    internal int[] SnapshotItemCounts() => (int[])_itemCounts.Clone();

    public void Dispose()
    {
        if (_disposed)
            return;

        _disposed = true;
        _state.LoadedEvent -= OnStateLoaded;
        _state.QuestLogChangedEvent -= OnQuestLogChanged;
        _state.InventoryChangedEvent -= OnInventoryChanged;
    }

    private void OnStateLoaded(ChangeSet _)
    {
        Array.Fill(_phases, QuestPhase.NotReady);
        Array.Clear(_completed, 0, _completed.Length);
        Array.Clear(_itemCounts, 0, _itemCounts.Length);

        for (int questIndex = 0; questIndex < _guide.QuestCount; questIndex++)
        {
            _remainingPrereqs[questIndex] = _guide.PrereqQuestIds(questIndex).Length;
            if (_guide.IsInfeasibleNode(_guide.QuestNodeId(questIndex)))
            {
                _phases[questIndex] = QuestPhase.Infeasible;
            }
            else if (_remainingPrereqs[questIndex] == 0)
            {
                _phases[questIndex] = _guide.IsImplicit(questIndex)
                    ? QuestPhase.Accepted
                    : QuestPhase.ReadyToAccept;
            }
        }

        for (int itemIndex = 0; itemIndex < _guide.ItemCount; itemIndex++)
        {
            string itemKey = _guide.GetNodeKey(_guide.ItemNodeId(itemIndex));
            if (_state.InventoryCounts.TryGetValue(itemKey, out int quantity))
                _itemCounts[itemIndex] = quantity;
        }

        foreach (int questIndex in _guide.TopologicalOrder)
        {
            int nodeId = _guide.QuestNodeId(questIndex);
            string? dbName = _guide.GetDbName(nodeId);
            if (!string.IsNullOrEmpty(dbName) && _state.CompletedQuests.Contains(dbName))
                ApplyCompleted(questIndex);
        }

        foreach (string dbName in _state.ActiveQuests)
        {
            if (
                _dbNameToQuestIndex.TryGetValue(dbName, out int questIndex)
                && _phases[questIndex] != QuestPhase.Completed
            )
            {
                _phases[questIndex] = QuestPhase.Accepted;
            }
        }

        Version++;
    }

    private void OnQuestLogChanged(ChangeSet changeSet)
    {
        bool changed = false;
        foreach (var dbName in changeSet.ChangedQuestDbNames)
        {
            if (!_dbNameToQuestIndex.TryGetValue(dbName, out int questIndex))
                continue;

            if (_state.CompletedQuests.Contains(dbName))
            {
                if (_completed[questIndex])
                    continue;

                ApplyCompleted(questIndex);
                changed = true;
                continue;
            }

            if (_state.ActiveQuests.Contains(dbName) && _phases[questIndex] == QuestPhase.ReadyToAccept)
            {
                _phases[questIndex] = QuestPhase.Accepted;
                changed = true;
            }
        }

        if (changed)
            Version++;
    }

    private void OnInventoryChanged(ChangeSet changeSet)
    {
        bool changed = false;
        foreach (var itemKey in changeSet.ChangedItemKeys)
        {
            if (!_guide.TryGetNodeId(itemKey, out int itemNodeId))
                continue;

            int itemIndex = _guide.FindItemIndex(itemNodeId);
            if (itemIndex < 0 || itemIndex >= _itemCounts.Length)
                continue;

            int newCount = _state.InventoryCounts.TryGetValue(itemKey, out int quantity) ? quantity : 0;
            if (_itemCounts[itemIndex] == newCount)
                continue;

            _itemCounts[itemIndex] = newCount;
            changed = true;
        }

        if (changed)
            Version++;
    }

    private void ApplyCompleted(int questIndex)
    {
        _completed[questIndex] = true;
        _phases[questIndex] = QuestPhase.Completed;

        foreach (int dependentQuestIndex in _guide.QuestsDependingOnQuest(questIndex))
        {
            if (_phases[dependentQuestIndex] is QuestPhase.Completed or QuestPhase.Infeasible)
                continue;

            _remainingPrereqs[dependentQuestIndex] = Math.Max(
                0,
                _remainingPrereqs[dependentQuestIndex] - 1
            );
            if (
                _remainingPrereqs[dependentQuestIndex] == 0
                && _phases[dependentQuestIndex] == QuestPhase.NotReady
            )
            {
                _phases[dependentQuestIndex] = _guide.IsImplicit(dependentQuestIndex)
                    ? QuestPhase.Accepted
                    : QuestPhase.ReadyToAccept;
            }
        }

        foreach (int chainedQuestId in _guide.ChainsToIds(questIndex))
        {
            int chainedQuestIndex = _guide.FindQuestIndex(chainedQuestId);
            if (chainedQuestIndex >= 0 && _phases[chainedQuestIndex] == QuestPhase.ReadyToAccept)
                _phases[chainedQuestIndex] = QuestPhase.Accepted;
        }
    }

    private void RecordQuestFacts(int questIndex)
    {
        RecordQuestActiveFact(questIndex);
        RecordQuestCompletedFact(questIndex);
    }

    private void RecordQuestActiveFact(int questIndex)
    {
        string? dbName = _guide.GetDbName(_guide.QuestNodeId(questIndex));
        if (!string.IsNullOrEmpty(dbName))
            _ = _state.IsActive(dbName);
    }

    private void RecordQuestCompletedFact(int questIndex)
    {
        string? dbName = _guide.GetDbName(_guide.QuestNodeId(questIndex));
        if (!string.IsNullOrEmpty(dbName))
            _ = _state.IsCompleted(dbName);
    }

    private void RecordItemCountFact(int itemIndex)
    {
        string itemKey = _guide.GetNodeKey(_guide.ItemNodeId(itemIndex));
        _ = _state.CountItem(itemKey);
    }

    private static QuestStateTracker CreateDetachedState(
        CompiledGuide.CompiledGuide guide)
    {
        var state = new QuestStateTracker(guide);

        state.LoadState(
            currentZone: string.Empty,
            activeQuests: Array.Empty<string>(),
            completedQuests: Array.Empty<string>(),
            inventoryCounts: new Dictionary<string, int>(StringComparer.Ordinal),
            keyringItemKeys: Array.Empty<string>()
        );
        return state;
    }
}
