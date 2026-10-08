using AdventureGuide.Config;
using AdventureGuide.Data;
using AdventureGuide.UI;

namespace AdventureGuide.State;

/// <summary>
/// Manages which quests the player has pinned to the tracker overlay.
/// Pure logical state — no animation concerns. Visual effects (fade-in,
/// fade-out, completion flash) are owned by TrackerWindow which subscribes
/// to events.
///
/// Tracked quests are stored per character (keyed by save slot index) and
/// written whenever they change, so a crash loses nothing. Global preferences
/// (auto-track, sort mode) live in their config entries, which settings UIs
/// can change at any time.
/// </summary>
public sealed class TrackerState
{
    private readonly HashSet<string> _tracked = new(StringComparer.OrdinalIgnoreCase);
    private readonly List<string> _orderedList = new();
    private GuideConfig? _config;
    private IConfigValue<string>? _trackedEntry;
    private int _boundSlotIndex = -1;
    private bool _dirty;
    private TrackerSortMode _sortMode = TrackerSortMode.Proximity;

    public bool Enabled { get; set; } = true;

    /// <summary>Tracker.AutoTrack, read live so a settings change applies at once.</summary>
    public bool AutoTrackEnabled => _config?.TrackerAutoTrack.Value ?? true;

    /// <summary>Tracker.SortMode, kept in step with its config entry both ways.</summary>
    public TrackerSortMode SortMode
    {
        get => _sortMode;
        set
        {
            if (_sortMode == value)
                return;
            _sortMode = value;
            if (_config != null)
                _config.TrackerSortMode.Value = value.ToString();
        }
    }

    /// <summary>
    /// Returns true if state changed since last check, then clears the flag.
    /// Designed for single-consumer polling (the tracker window).
    /// </summary>
    public bool IsDirty
    {
        get
        {
            var d = _dirty;
            _dirty = false;
            return d;
        }
    }

    /// <summary>Current tracked quest DB names in insertion order.</summary>
    public IReadOnlyList<string> TrackedQuests => _orderedList;

    public bool IsTracked(string dbName) => _tracked.Contains(dbName);

    // ── Events ───────────────────────────────────────────────────────

    /// <summary>Fired after a quest is added to the tracked set.</summary>
    public event Action<string>? Tracked;

    /// <summary>Fired after a quest is removed from the tracked set.</summary>
    public event Action<string>? Untracked;

    /// <summary>Fired when a tracked quest is completed by the game.</summary>
    public event Action<string>? QuestCompleted;

    /// <summary>Fired when a tracked quest advances to the next step.</summary>
    public event Action<string>? StepAdvanced;

    // ── Mutations ────────────────────────────────────────────────────

    public void Track(string dbName)
    {
        if (!_tracked.Add(dbName))
            return;
        _orderedList.Add(dbName);
        _dirty = true;
        PersistTracked();
        Tracked?.Invoke(dbName);
    }

    public void Untrack(string dbName)
    {
        if (!_tracked.Remove(dbName))
            return;
        _orderedList.Remove(dbName);
        _dirty = true;
        PersistTracked();
        Untracked?.Invoke(dbName);
    }

    public void OnQuestCompleted(string dbName)
    {
        if (!_tracked.Contains(dbName))
            return;
        QuestCompleted?.Invoke(dbName);
    }

    public void OnStepAdvanced(string dbName)
    {
        if (!_tracked.Contains(dbName))
            return;
        StepAdvanced?.Invoke(dbName);
    }

    /// <summary>Remove missing identities and completed non-repeatable quests.</summary>
    public void PruneCompleted(QuestStateTracker state, GuideData data)
    {
        for (int i = _orderedList.Count - 1; i >= 0; i--)
        {
            var key = _orderedList[i];
            var quest = data.GetByRuntimeKey(key);
            bool questExists = quest != null;
            bool isCompleted = questExists && state.IsCompleted(quest!);
            bool isRepeatable = questExists && quest!.Flags is { Repeatable: true };
            if (TrackerPruningPolicy.ShouldPrune(questExists, isCompleted, isRepeatable))
                Untrack(key);
        }
    }

    // ── Config persistence ───────────────────────────────────────────

    public void LoadFromConfig(GuideConfig config)
    {
        if (_config != null)
            _config.TrackerSortMode.SettingChanged -= OnSortModeSettingChanged;
        _config = config;
        Enabled = config.TrackerEnabled.Value;
        ReadSortMode();
        config.TrackerSortMode.SettingChanged += OnSortModeSettingChanged;
    }

    private void OnSortModeSettingChanged(object sender, EventArgs e) => ReadSortMode();

    private void ReadSortMode()
    {
        if (Enum.TryParse<TrackerSortMode>(_config!.TrackerSortMode.Value, out var mode))
            _sortMode = mode;
    }

    /// <summary>
    /// Bind and load tracked quests for the current character's save slot.
    /// On the first call (or after a character switch), reads from config.
    /// On subsequent calls for the same character (zone transitions),
    /// the in-memory state is authoritative and no reload occurs.
    /// </summary>
    public void OnCharacterLoaded()
    {
        if (_config == null)
            return;
        var slot = GameData.CurrentCharacterSlot;
        if (slot == null)
            return;

        // Same character — in-memory state is authoritative
        if (slot.index == _boundSlotIndex)
            return;

        _boundSlotIndex = slot.index;
        _trackedEntry = _config.BindPerCharacter(slot.index, "TrackedQuests", "");

        _tracked.Clear();
        _orderedList.Clear();
        var raw = _trackedEntry.Value;
        if (!string.IsNullOrEmpty(raw))
        {
            foreach (var db in raw.Split(';'))
            {
                var trimmed = db.Trim();
                if (trimmed.Length > 0 && _tracked.Add(trimmed))
                    _orderedList.Add(trimmed);
            }
        }
        _dirty = true;
    }

    private void PersistTracked()
    {
        if (_trackedEntry != null)
            _trackedEntry.Value = string.Join(";", _orderedList);
    }
}
