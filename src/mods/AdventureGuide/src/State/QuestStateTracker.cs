using AdventureGuide.Config;
using AdventureGuide.Data;
using AdventureGuide.Navigation;

namespace AdventureGuide.State;

/// <summary>
/// Single status boundary for game-backed and guide-only quest entries.
/// Ordinary quests mirror GameData; guide-only workflows delegate exclusively
/// to GuideWorkflowState and never read or mutate game quest collections.
/// </summary>
public sealed class QuestStateTracker
{
    private readonly GuideData _data;
    private readonly IQuestGameState _gameState;
    private readonly HashSet<string> _activeQuests = new(StringComparer.OrdinalIgnoreCase);
    private readonly HashSet<string> _completedQuests = new(StringComparer.OrdinalIgnoreCase);
    private readonly List<ImplicitQuest> _implicitQuests = new();
    private readonly HashSet<string> _implicitlyActiveQuests = new(
        StringComparer.OrdinalIgnoreCase
    );
    private readonly Dictionary<string, int> _inventoryCache = new(
        StringComparer.OrdinalIgnoreCase
    );
    private bool _dirty = true;
    private NavigationHistory? _history;

    public int Version { get; private set; }
    public string CurrentZone { get; private set; } = "";
    public string? SelectedQuestKey { get; set; }
    public GuideWorkflowState Workflows { get; }

    public event Action<QuestEntry>? WorkflowChanged;
    public event Action<QuestEntry>? WorkflowCycleReset;

    public QuestStateTracker(GuideData data, EntityRegistry entities)
        : this(data, entities, LiveQuestGameState.Instance) { }

    internal QuestStateTracker(GuideData data, EntityRegistry entities, IQuestGameState gameState)
    {
        _data = data;
        _gameState = gameState;
        Workflows = new GuideWorkflowState(data, entities);
        Workflows.Changed += OnWorkflowChanged;
        Workflows.CycleReset += OnWorkflowCycleReset;

        foreach (var quest in data.All)
        {
            if (quest.IsGuideOnly || !quest.IsImplicit || quest.Steps is not { Count: > 0 })
                continue;
            var lastStep = quest.Steps[^1];
            string? scene = StepSceneResolver.ResolveScene(quest, lastStep, data);
            _implicitQuests.Add(new ImplicitQuest(quest.DBName, scene));
        }
    }

    public void LoadFromConfig(GuideConfig config) => Workflows.LoadFromConfig(config);

    public void OnCharacterLoaded() => Workflows.OnCharacterLoaded(CountItem);

    public void SaveToConfig() => Workflows.SaveToConfig();

    public void SetHistory(NavigationHistory history) => _history = history;

    public void SelectQuest(QuestEntry quest)
    {
        if (string.Equals(quest.RuntimeKey, SelectedQuestKey, StringComparison.OrdinalIgnoreCase))
            return;
        _history?.Navigate(
            new NavigationHistory.PageRef(NavigationHistory.PageType.Quest, quest.RuntimeKey)
        );
        SelectedQuestKey = quest.RuntimeKey;
    }

    public IReadOnlyCollection<string> ActiveQuests => _activeQuests;
    public IReadOnlyCollection<string> CompletedQuests => _completedQuests;

    public QuestRuntimeStatus GetStatus(QuestEntry quest)
    {
        if (quest.IsGuideOnly)
            return QuestStatusPolicy.GetGuideOnlyStatus(
                Workflows.IsInCurrentScene(quest),
                Workflows.IsInProgress(quest)
            );

        if (_activeQuests.Contains(quest.DBName))
            return QuestRuntimeStatus.Active;
        if (_completedQuests.Contains(quest.DBName))
            return QuestRuntimeStatus.Completed;
        EnsureCacheCurrent();
        return _implicitlyActiveQuests.Contains(quest.DBName)
            ? QuestRuntimeStatus.ImplicitlyActive
            : QuestRuntimeStatus.Available;
    }

    public bool IsActive(QuestEntry quest) => GetStatus(quest) == QuestRuntimeStatus.Active;

    public bool IsActionable(QuestEntry quest)
    {
        var status = GetStatus(quest);
        return status is QuestRuntimeStatus.Active or QuestRuntimeStatus.ImplicitlyActive;
    }

    public bool IsImplicitlyActive(QuestEntry quest) =>
        GetStatus(quest) == QuestRuntimeStatus.ImplicitlyActive;

    public bool IsCompleted(QuestEntry quest) => GetStatus(quest) == QuestRuntimeStatus.Completed;

    public bool IsGameQuestCompleted(string dbName) => _completedQuests.Contains(dbName);

    public bool IsGameQuestActive(string dbName) => _activeQuests.Contains(dbName);

    public void SyncFromGameData()
    {
        _activeQuests.Clear();
        _completedQuests.Clear();
        _gameState.CopyActiveQuestsTo(_activeQuests);
        _gameState.CopyCompletedQuestsTo(_completedQuests);

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
        Workflows.OnInventoryChanged(CurrentZone, _gameState.PlayerPosition, CountItem);
        Version++;
    }

    public void OnCharacterStarted(Character character) =>
        Workflows.ObserveCharacterStarted(character);

    public void OnCharacterDeath(Character character) =>
        Workflows.ObserveCharacterDeath(character, CountItem);

    public void OnRewardContainerConsumed(Character character) =>
        Workflows.ObserveRewardContainerConsumed(character, CountItem);

    public void Update(float deltaTime) => Workflows.Update(deltaTime, CountItem);

    public void OnSceneChanged(string sceneName)
    {
        CurrentZone = sceneName;
        SyncFromGameData();
        Workflows.OnSceneChanged(sceneName, CountItem);
    }

    public int CountItem(string itemStableKey)
    {
        EnsureCacheCurrent();
        return _inventoryCache.TryGetValue(itemStableKey, out int count) ? count : 0;
    }

    private void EnsureCacheCurrent()
    {
        if (!_dirty)
            return;
        RebuildInventoryCache();
        RebuildImplicitQuests();
    }

    private void RebuildInventoryCache()
    {
        _inventoryCache.Clear();
        _dirty = false;
        _gameState.CopyInventoryCountsTo(_inventoryCache);
    }

    private void RebuildImplicitQuests()
    {
        _implicitlyActiveQuests.Clear();
        foreach (var implicitQuest in _implicitQuests)
        {
            if (
                _activeQuests.Contains(implicitQuest.DBName)
                || _completedQuests.Contains(implicitQuest.DBName)
                || implicitQuest.ActivationScene == null
                || !string.Equals(
                    implicitQuest.ActivationScene,
                    CurrentZone,
                    StringComparison.OrdinalIgnoreCase
                )
            )
                continue;
            _implicitlyActiveQuests.Add(implicitQuest.DBName);
        }
    }

    private void OnWorkflowChanged(QuestEntry quest)
    {
        Version++;
        WorkflowChanged?.Invoke(quest);
    }

    private void OnWorkflowCycleReset(QuestEntry quest)
    {
        WorkflowCycleReset?.Invoke(quest);
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
