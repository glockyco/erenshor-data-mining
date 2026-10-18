using AdventureGuide.Data;

namespace AdventureGuide.State;

/// <summary>
/// Tracks native quest state and projects completion through common encounter bindings.
/// </summary>
public sealed class QuestStateTracker
{
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
    private int _keyringCount;
    private bool _accountClaimed;
    private string? _returnZone;
    private UnityEngine.Vector3? _returnLanding;
    private int _playerLevel;

    public int Version { get; private set; }
    public string CurrentZone { get; private set; } = "";
    public string? SelectedQuestKey { get; set; }

    /// <summary>The Reliquary rooms' furniture, which decides where furnishings stand.</summary>
    public ReliquaryFurnishings Furnishings { get; }
    public GateConditions Gates { get; }

    internal TreasureHunt TreasureHunt { get; } = new();
    internal event Action<TreasureHuntChange>? TreasureHuntChanged;

    /// <summary>
    /// <see cref="CountItem"/> as a delegate created once. Converting the
    /// method group at each call allocates, and Update runs every frame.
    /// </summary>
    internal Func<string, int> CountItemDelegate { get; }

    /// <summary>Raised after the planning table's rooms change, once Version moved.</summary>
    public event Action? FurnishingsChanged;

    /// <summary>A key joined or left the keyring, which can open or close door gates.</summary>
    public event Action? KeyringChanged;

    /// <summary>Supported account or character primitives changed after Version moved.</summary>
    public event Action? PrimitiveStateChanged;

    public QuestStateTracker(GuideData data)
        : this(data, LiveQuestGameState.Instance) { }

    internal QuestStateTracker(GuideData data, IQuestGameState gameState)
    {
        CountItemDelegate = CountItem;
        _gameState = gameState;
        Furnishings = new ReliquaryFurnishings();
        Gates = new GateConditions(data, new GameGateFacts(this));
        _keyringCount = GameData.Keyring?.Count ?? 0;
        CapturePrimitiveState();

        foreach (var quest in data.All)
        {
            if (!quest.IsImplicit || quest.Steps is not { Count: > 0 })
                continue;
            var lastStep = quest.Steps[^1];
            string? scene = StepSceneResolver.ResolveScene(quest, lastStep, data);
            _implicitQuests.Add(new ImplicitQuest(quest.DBName, scene));
        }
    }

    public void OnCharacterLoaded() => SyncFromGameData();

    public void SetHistory(NavigationHistory history) => _history = history;

    public void SelectQuest(QuestEntry quest)
    {
        if (string.Equals(quest.DBName, SelectedQuestKey, StringComparison.OrdinalIgnoreCase))
            return;
        _history?.Navigate(
            new NavigationHistory.PageRef(NavigationHistory.PageType.Quest, quest.DBName)
        );
        SelectedQuestKey = quest.DBName;
    }

    public IReadOnlyCollection<string> ActiveQuests => _activeQuests;
    public IReadOnlyCollection<string> CompletedQuests => _completedQuests;

    public QuestRuntimeStatus GetStatus(QuestEntry quest)
    {
        if (Gates.IsProjectedQuestCompleted(quest))
            return QuestRuntimeStatus.Completed;
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

    public bool ReadAccountState(string key) => _gameState.ReadAccountState(key);

    public string? ReadCharacterZoneState(string key) => _gameState.ReadCharacterZoneState(key);

    public UnityEngine.Vector3? ReadCharacterPositionState(string key) =>
        _gameState.ReadCharacterPositionState(key);

    public int PlayerLevel => _gameState.PlayerLevel;

    public void SyncFromGameData()
    {
        _activeQuests.Clear();
        _completedQuests.Clear();
        _gameState.CopyActiveQuestsTo(_activeQuests);
        _gameState.CopyCompletedQuestsTo(_completedQuests);

        _dirty = true;
        Version++;
        if (CapturePrimitiveState())
            PrimitiveStateChanged?.Invoke();
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

    public void Update()
    {
        if (CapturePrimitiveState())
        {
            Version++;
            PrimitiveStateChanged?.Invoke();
        }
        int keyringCount = GameData.Keyring?.Count ?? 0;
        if (keyringCount != _keyringCount)
        {
            _keyringCount = keyringCount;
            Version++;
            KeyringChanged?.Invoke();
        }
        // A furnishing appears or vanishes with its room's set, which changes
        // which sources, targets and markers exist.
        if (Furnishings.Poll())
        {
            Version++;
            FurnishingsChanged?.Invoke();
        }
        var huntChange = TreasureHunt.Poll(CurrentZone);
        if (huntChange != TreasureHuntChange.None)
        {
            Version++;
            TreasureHuntChanged?.Invoke(huntChange);
        }
    }

    public void OnSceneChanged(string sceneName)
    {
        CurrentZone = sceneName;
        SyncFromGameData();
    }

    public int CountItem(string itemStableKey)
    {
        EnsureCacheCurrent();
        return _inventoryCache.TryGetValue(itemStableKey, out int count) ? count : 0;
    }

    private bool CapturePrimitiveState()
    {
        bool claimed = ReadAccountState(EncounterStateKeys.ReliquaryClaimed);
        string? zone = ReadCharacterZoneState(EncounterStateKeys.ReturnZone);
        var landing = ReadCharacterPositionState(EncounterStateKeys.ReturnLanding);
        int level = PlayerLevel;
        bool changed =
            claimed != _accountClaimed
            || level != _playerLevel
            || !string.Equals(zone, _returnZone, StringComparison.Ordinal)
            || !SamePosition(landing, _returnLanding);
        _accountClaimed = claimed;
        _returnZone = zone;
        _returnLanding = landing;
        _playerLevel = level;
        return changed;
    }

    private static bool SamePosition(UnityEngine.Vector3? left, UnityEngine.Vector3? right) =>
        left.HasValue == right.HasValue
        && (
            !left.HasValue
            || (
                left.Value.x.Equals(right!.Value.x)
                && left.Value.y.Equals(right.Value.y)
                && left.Value.z.Equals(right.Value.z)
            )
        );

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
