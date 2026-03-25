using AdventureGuide.Config;
using AdventureGuide.UI;
using BepInEx.Configuration;

namespace AdventureGuide.State;

/// <summary>
/// Manages which quests the player has pinned to the tracker overlay.
/// Pure logical state — no animation concerns. Visual effects (fade-in,
/// fade-out, completion flash) are owned by TrackerWindow which subscribes
/// to events.
///
/// Tracked quests are stored per character (keyed by save slot index).
/// Global preferences (auto-track, sort mode) are shared.
/// </summary>
public sealed class TrackerState
{
    private readonly HashSet<string> _tracked = new(StringComparer.OrdinalIgnoreCase);
    private readonly List<string> _orderedList = new();
    private GuideConfig? _config;
    private ConfigEntry<string>? _trackedEntry;  // per-character
    private bool _dirty;

    public bool Enabled { get; set; } = true;
    public bool AutoTrackEnabled { get; set; } = true;
    public TrackerSortMode SortMode { get; set; } = TrackerSortMode.Proximity;

    /// <summary>
    /// Returns true if state changed since last check, then clears the flag.
    /// Designed for single-consumer polling (the tracker window).
    /// </summary>
    public bool IsDirty { get { var d = _dirty; _dirty = false; return d; } }

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
        if (!_tracked.Add(dbName)) return;
        _orderedList.Add(dbName);
        _dirty = true;
        Tracked?.Invoke(dbName);
    }

    public void Untrack(string dbName)
    {
        if (!_tracked.Remove(dbName)) return;
        _orderedList.Remove(dbName);
        _dirty = true;
        Untracked?.Invoke(dbName);
    }

    public void OnQuestCompleted(string dbName)
    {
        if (!_tracked.Contains(dbName)) return;
        QuestCompleted?.Invoke(dbName);
    }

    public void OnStepAdvanced(string dbName)
    {
        if (!_tracked.Contains(dbName)) return;
        StepAdvanced?.Invoke(dbName);
    }

    /// <summary>Remove tracked quests that are completed.</summary>
    public void PruneCompleted(QuestStateTracker state)
    {
        for (int i = _orderedList.Count - 1; i >= 0; i--)
        {
            var db = _orderedList[i];
            if (state.IsCompleted(db))
            {
                _tracked.Remove(db);
                _orderedList.RemoveAt(i);
                _dirty = true;
            }
        }
    }

    // ── Config persistence ───────────────────────────────────────────

    public void LoadFromConfig(GuideConfig config)
    {
        _config = config;
        Enabled = config.TrackerEnabled.Value;
        AutoTrackEnabled = config.TrackerAutoTrack.Value;
        if (Enum.TryParse<TrackerSortMode>(config.TrackerSortMode.Value, out var mode))
            SortMode = mode;
    }

    /// <summary>
    /// Load tracked quests for the current character's save slot.
    /// Call after character login when GameData.CurrentCharacterSlot is available.
    /// </summary>
    public void OnCharacterLoaded()
    {
        if (_config == null) return;
        var slot = GameData.CurrentCharacterSlot;
        if (slot == null) return;

        _trackedEntry = _config.File.Bind(
            "_Character", $"TrackedQuests_Slot{slot.index}", "",
            new ConfigDescription(
                $"Tracked quests for slot {slot.index} (auto-managed)", null,
                new { Browsable = false }));

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

    public void SaveToConfig()
    {
        if (_config == null) return;
        _config.TrackerEnabled.Value = Enabled;
        _config.TrackerAutoTrack.Value = AutoTrackEnabled;
        _config.TrackerSortMode.Value = SortMode.ToString();
        if (_trackedEntry != null)
            _trackedEntry.Value = string.Join(";", _orderedList);
    }
}
