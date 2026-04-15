
namespace AdventureGuide.Plan;

public sealed class QuestPhaseTracker
{
    private readonly CompiledGuide.CompiledGuide _guide;
    private readonly QuestPhase[] _phases;
    private readonly int[] _remainingPrereqs;
    private readonly int[] _itemCounts;
    private readonly bool[] _completed;
    private readonly Dictionary<string, int> _dbNameToQuestIndex;

    public QuestPhaseTracker(CompiledGuide.CompiledGuide guide)
    {
        _guide = guide;
        _phases = new QuestPhase[guide.QuestCount];
        _remainingPrereqs = new int[guide.QuestCount];
        _itemCounts = new int[guide.ItemCount];
        _completed = new bool[guide.QuestCount];
        _dbNameToQuestIndex = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);

        for (int questIndex = 0; questIndex < guide.QuestCount; questIndex++)
        {
            int nodeId = guide.QuestNodeId(questIndex);
            string? dbName = guide.GetDbName(nodeId);
            if (dbName == null)
            {
                continue;
            }

            if (!string.IsNullOrEmpty(dbName))
            {
                _dbNameToQuestIndex[dbName] = questIndex;
            }
        }
    }

    public void Initialize(
        IReadOnlyCollection<string> completedQuestDbNames,
        IReadOnlyCollection<string> activeQuestDbNames,
        IReadOnlyDictionary<string, int> inventory,
        IReadOnlyCollection<string> keyringItems)
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
                _phases[questIndex] = QuestPhase.ReadyToAccept;
            }
        }

        for (int itemIndex = 0; itemIndex < _guide.ItemCount; itemIndex++)
        {
            string itemKey = _guide.GetNodeKey(_guide.ItemNodeId(itemIndex));
            if (inventory.TryGetValue(itemKey, out int quantity))
            {
                _itemCounts[itemIndex] = quantity;
            }
        }

        foreach (int questIndex in _guide.TopologicalOrder)
        {
            int nodeId = _guide.QuestNodeId(questIndex);
            string? dbName = _guide.GetDbName(nodeId);
            if (!string.IsNullOrEmpty(dbName) && completedQuestDbNames.Contains(dbName))
            {
                ApplyCompleted(questIndex);
            }
        }

        foreach (string dbName in activeQuestDbNames)
        {
            if (_dbNameToQuestIndex.TryGetValue(dbName, out int questIndex)
                && _phases[questIndex] != QuestPhase.Completed)
            {
                _phases[questIndex] = QuestPhase.Accepted;
            }
        }

        _ = keyringItems;
    }

    public QuestPhase GetPhase(int questIndex) => _phases[questIndex];

    public bool IsCompleted(int questIndex) => _completed[questIndex];

    public int GetItemCount(int itemIndex) => _itemCounts[itemIndex];

    public void OnQuestAssigned(int questIndex)
    {
        if (_phases[questIndex] == QuestPhase.ReadyToAccept)
        {
            _phases[questIndex] = QuestPhase.Accepted;
        }
    }

    public void OnQuestCompleted(int questIndex)
    {
        if (_completed[questIndex])
        {
            return;
        }

        ApplyCompleted(questIndex);
    }

    public void OnInventoryChanged(int itemIndex, int newCount)
    {
        if (itemIndex >= 0 && itemIndex < _itemCounts.Length)
        {
            _itemCounts[itemIndex] = newCount;
        }
    }

    private void ApplyCompleted(int questIndex)
    {
        _completed[questIndex] = true;
        _phases[questIndex] = QuestPhase.Completed;

        foreach (int dependentQuestIndex in _guide.QuestsDependingOnQuest(questIndex))
        {
            if (_phases[dependentQuestIndex] is QuestPhase.Completed or QuestPhase.Infeasible)
            {
                continue;
            }

            _remainingPrereqs[dependentQuestIndex] = Math.Max(0, _remainingPrereqs[dependentQuestIndex] - 1);
            if (_remainingPrereqs[dependentQuestIndex] == 0 && _phases[dependentQuestIndex] == QuestPhase.NotReady)
            {
                _phases[dependentQuestIndex] = QuestPhase.ReadyToAccept;
            }
        }

        foreach (int chainedQuestId in _guide.ChainsToIds(questIndex))
        {
            int chainedQuestIndex = _guide.FindQuestIndex(chainedQuestId);
            if (chainedQuestIndex >= 0 && _phases[chainedQuestIndex] == QuestPhase.ReadyToAccept)
            {
                _phases[chainedQuestIndex] = QuestPhase.Accepted;
            }
        }
    }
}
