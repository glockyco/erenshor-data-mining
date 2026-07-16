using AdventureGuide.UI;
using UnityEngine;

namespace AdventureGuide.Config;

/// <summary>
/// Loader-neutral Adventure Guide settings. This is the sole owner of keys and
/// defaults; native adapters only implement IGuideConfigBackend.
/// </summary>
public sealed class GuideConfig : IDisposable
{
    private readonly IGuideConfigBackend _backend;
    private readonly List<IDisposable> _entries = new();

    // ── Runtime state (not persisted) ─────────────────────────────────

    /// <summary>Current resolved UI scale factor. Set by Plugin.</summary>
    internal float ResolvedUiScale { get; set; } = 1f;

    /// <summary>
    /// When true, windows re-apply their default size on the next frame.
    /// Set by Plugin on layout reset or scale change; cleared after draw.
    /// </summary>
    internal bool LayoutResetRequested { get; set; }

    // ── User-facing: General ─────────────────────────────────────────

    public IConfigValue<KeyCode> ToggleKey { get; }
    public IConfigValue<bool> ReplaceQuestLog { get; }
    public IConfigValue<float> UiScale { get; }
    public IConfigValue<int> HistoryMaxSize { get; }
    public IConfigValue<bool> ResetWindowLayout { get; }

    // ── User-facing: Navigation ──────────────────────────────────────

    public IConfigValue<bool> ShowArrow { get; }
    public IConfigValue<bool> ShowGroundPath { get; }
    public IConfigValue<KeyCode> GroundPathToggleKey { get; }

    // ── User-facing: World Markers ───────────────────────────────────

    public IConfigValue<bool> ShowWorldMarkers { get; }
    public IConfigValue<float> MarkerScale { get; }
    public IConfigValue<float> IconSize { get; }
    public IConfigValue<float> SubTextSize { get; }
    public IConfigValue<float> SubTextYOffset { get; }
    public IConfigValue<float> IconYOffset { get; }

    // ── User-facing: Tracker ─────────────────────────────────────────

    public IConfigValue<bool> TrackerEnabled { get; }
    public IConfigValue<KeyCode> TrackerToggleKey { get; }
    public IConfigValue<bool> TrackerAutoTrack { get; }
    public IConfigValue<string> TrackerSortMode { get; }
    public IConfigValue<float> TrackerBackgroundOpacity { get; }

    // ── Internal: quest list state (auto-managed) ────────────────────

    public IConfigValue<QuestFilterMode> FilterMode { get; }
    public IConfigValue<QuestSortMode> SortMode { get; }
    public IConfigValue<string> ZoneFilter { get; }

    public GuideConfig(IGuideConfigBackend backend)
    {
        _backend = backend;

        // General
        ToggleKey = Bind(
            "General",
            "ToggleKey",
            KeyCode.L,
            "Key to toggle the Adventure Guide window"
        );
        ReplaceQuestLog = Bind(
            "General",
            "ReplaceQuestLog",
            false,
            "If true, pressing J opens Adventure Guide instead of the game's Quest Log"
        );
        UiScale = Bind(
            "General",
            "UiScale",
            -1f,
            "UI scale factor. Affects font size and element spacing. Set to -1 to auto-detect from screen resolution.",
            min: -1f,
            max: 4f
        );
        HistoryMaxSize = Bind(
            "General",
            "HistoryMaxSize",
            100,
            "Maximum number of pages in navigation history",
            min: 10f,
            max: 500f
        );
        ResetWindowLayout = Bind(
            "General",
            "ResetWindowLayout",
            false,
            "Toggle to reset all window positions and sizes to defaults."
        );

        // Navigation
        ShowArrow = Bind(
            "Navigation",
            "ShowArrow",
            true,
            "Show directional arrow pointing toward navigation target"
        );
        ShowGroundPath = Bind(
            "Navigation",
            "ShowGroundPath",
            false,
            "Show ground path from player to navigation target (uses NavMesh pathfinding)"
        );
        GroundPathToggleKey = Bind(
            "Navigation",
            "GroundPathToggleKey",
            KeyCode.P,
            "Key to toggle the ground path overlay"
        );

        // World Markers
        ShowWorldMarkers = Bind(
            "World Markers",
            "Enabled",
            true,
            "Show floating quest markers above NPCs (!, ?, objective icons). Replaces the game's built-in markers when enabled."
        );
        MarkerScale = Bind(
            "World Markers",
            "Scale",
            1.0f,
            "Overall scale of world markers",
            min: 0.05f,
            max: 2.0f
        );
        IconSize = Bind(
            "World Markers",
            "IconSize",
            7f,
            "Font size of the marker icon glyph",
            min: 1f,
            max: 20f
        );
        SubTextSize = Bind(
            "World Markers",
            "SubTextSize",
            3.5f,
            "Font size of the sub-text label",
            min: 1f,
            max: 10f
        );
        SubTextYOffset = Bind(
            "World Markers",
            "SubTextYOffset",
            -1f,
            "Y offset of sub-text relative to icon (negative = below)",
            min: -5f,
            max: 5f
        );
        IconYOffset = Bind(
            "World Markers",
            "IconYOffset",
            1f,
            "Y offset of icon relative to marker root",
            min: -5f,
            max: 5f
        );

        // Tracker
        TrackerEnabled = Bind(
            "Tracker",
            "Enabled",
            true,
            "Enable the quest tracker overlay. When disabled, auto-tracking and the tracker window are inactive."
        );
        TrackerToggleKey = Bind(
            "Tracker",
            "ToggleKey",
            KeyCode.K,
            "Key to toggle the quest tracker overlay"
        );
        TrackerAutoTrack = Bind(
            "Tracker",
            "AutoTrack",
            true,
            "Automatically track newly accepted quests"
        );
        TrackerSortMode = Bind(
            "Tracker",
            "SortMode",
            "Proximity",
            "Sort order: Proximity, Level, or Alphabetical"
        );
        TrackerBackgroundOpacity = Bind(
            "Tracker",
            "BackgroundOpacity",
            0.40f,
            "Opacity of the tracker background when not hovered (0 = fully transparent, 1 = opaque)",
            min: 0f,
            max: 1f
        );

        // Internal: quest list state
        FilterMode = Bind(
            "_State",
            "FilterMode",
            QuestFilterMode.Active,
            "Auto-managed by Adventure Guide",
            hidden: true
        );
        SortMode = Bind(
            "_State",
            "SortMode",
            QuestSortMode.ByLevel,
            "Auto-managed by Adventure Guide",
            hidden: true
        );
        ZoneFilter = Bind(
            "_State",
            "ZoneFilter",
            "",
            "Auto-managed by Adventure Guide",
            hidden: true
        );
    }

    /// <summary>
    /// Bind a hidden entry scoped to a character save slot.
    /// Used by subsystems that persist per-character state.
    /// </summary>
    public IConfigValue<T> BindPerCharacter<T>(int slotIndex, string key, T defaultValue) =>
        Bind(
            "_Character",
            $"{key}_Slot{slotIndex}",
            defaultValue,
            $"Per-character state for slot {slotIndex} (auto-managed)",
            hidden: true
        );

    public void Dispose()
    {
        foreach (var entry in _entries)
            entry.Dispose();
        _entries.Clear();
        _backend.Dispose();
    }

    private IConfigValue<T> Bind<T>(
        string section,
        string key,
        T defaultValue,
        string description,
        bool hidden = false,
        float? min = null,
        float? max = null
    )
    {
        var entry = _backend.Bind(section, key, defaultValue, description, hidden, min, max);
        _entries.Add(entry);
        return entry;
    }
}
