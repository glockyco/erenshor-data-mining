using AdventureGuide.Config;
using AdventureGuide.UI;
using UnityEngine;

namespace AdventureGuide.State;

/// <summary>
/// Manages which quests the player has pinned to the tracker overlay.
/// Separate from QuestStateTracker which tracks game truth — this tracks
/// the player's UI preference (which quests to show in the overlay).
/// Persists tracked quest list and preferences to BepInEx config.
/// </summary>
public sealed class TrackerState
{
    private readonly HashSet<string> _tracked = new(System.StringComparer.OrdinalIgnoreCase);
    private readonly List<string> _orderedList = new();
    private readonly Dictionary<string, EntryAnimation> _animations = new(System.StringComparer.OrdinalIgnoreCase);
    private GuideConfig? _config;
    private bool _dirty;

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

    public void Track(string dbName)
    {
        if (!_tracked.Add(dbName)) return;
        _orderedList.Add(dbName);
        _animations[dbName] = new EntryAnimation { AddedAt = Time.realtimeSinceStartup };
        _dirty = true;
    }

    public void Untrack(string dbName)
    {
        if (!_tracked.Contains(dbName)) return;
        var anim = GetOrDefaultAnim(dbName);
        anim.RemoveAt = Time.realtimeSinceStartup;
        anim.PendingRemoval = true;
        _animations[dbName] = anim;
        _dirty = true;
    }

    public void OnQuestCompleted(string dbName)
    {
        if (!_tracked.Contains(dbName)) return;
        var anim = GetOrDefaultAnim(dbName);
        anim.CompletedAt = Time.realtimeSinceStartup;
        _animations[dbName] = anim;
        _dirty = true;
    }

    public void OnStepAdvanced(string dbName)
    {
        if (!_tracked.Contains(dbName)) return;
        var anim = GetOrDefaultAnim(dbName);
        anim.StepAdvancedAt = Time.realtimeSinceStartup;
        _animations[dbName] = anim;
    }

    /// <summary>
    /// Remove entries whose fade-out animation has completed, and
    /// schedule removal for completed quests after the flash duration.
    /// Call once per frame from the tracker window.
    /// </summary>
    public void PruneCompleted()
    {
        float now = Time.realtimeSinceStartup;
        for (int i = _orderedList.Count - 1; i >= 0; i--)
        {
            var db = _orderedList[i];
            if (!_animations.TryGetValue(db, out var anim)) continue;

            // Schedule removal after 2s completion flash
            if (anim.CompletedAt > 0 && !anim.PendingRemoval && now - anim.CompletedAt > 2f)
            {
                anim.RemoveAt = now;
                anim.PendingRemoval = true;
                _animations[db] = anim;
            }

            // Actually remove after 0.3s fade-out
            if (anim.PendingRemoval && anim.RemoveAt > 0 && now - anim.RemoveAt > 0.3f)
            {
                _tracked.Remove(db);
                _orderedList.RemoveAt(i);
                _animations.Remove(db);
                _dirty = true;
            }
        }
    }

    public EntryAnimation GetAnimation(string dbName) =>
        _animations.TryGetValue(dbName, out var anim) ? anim : default;

    /// <summary>Remove tracked quests that are no longer active or completed.</summary>
    public void PruneInactive(QuestStateTracker state)
    {
        for (int i = _orderedList.Count - 1; i >= 0; i--)
        {
            var db = _orderedList[i];
            if (!state.IsActive(db) && !state.IsCompleted(db))
            {
                _tracked.Remove(db);
                _orderedList.RemoveAt(i);
                _animations.Remove(db);
            }
        }
    }

    public void LoadFromConfig(GuideConfig config)
    {
        _config = config;
        AutoTrackEnabled = config.TrackerAutoTrack.Value;
        if (System.Enum.TryParse<TrackerSortMode>(config.TrackerSortMode.Value, out var mode))
            SortMode = mode;

        _tracked.Clear();
        _orderedList.Clear();
        _animations.Clear();
        var raw = config.TrackedQuests.Value;
        if (!string.IsNullOrEmpty(raw))
        {
            foreach (var db in raw.Split(';'))
            {
                var trimmed = db.Trim();
                if (trimmed.Length > 0 && _tracked.Add(trimmed))
                    _orderedList.Add(trimmed);
            }
        }
    }

    public void SaveToConfig()
    {
        if (_config == null) return;
        _config.TrackerAutoTrack.Value = AutoTrackEnabled;
        _config.TrackerSortMode.Value = SortMode.ToString();
        _config.TrackedQuests.Value = string.Join(";", _orderedList);
    }

    private EntryAnimation GetOrDefaultAnim(string dbName) =>
        _animations.TryGetValue(dbName, out var anim) ? anim : default;

    public struct EntryAnimation
    {
        public float AddedAt;
        public float CompletedAt;
        public float StepAdvancedAt;
        public float RemoveAt;
        public bool PendingRemoval;
    }
}
