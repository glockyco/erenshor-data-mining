using BepInEx.Configuration;
using UnityEngine;

namespace AdventureGuide.Config;

/// <summary>
/// All BepInEx config entries for the AdventureGuide mod.
///
/// Organized into user-facing settings (visible in ConfigurationManager F1)
/// and internal state (hidden, auto-managed by the mod). The anonymous
/// <c>{ Browsable = false }</c> tag is read by ConfigurationManager via
/// reflection to hide entries from the F1 UI.
/// </summary>
public sealed class GuideConfig
{
    private static readonly object Hidden = new { Browsable = false };

    // ── Runtime state (not persisted) ─────────────────────────────────

    /// <summary>Current resolved UI scale factor. Set by Plugin.</summary>
    internal float ResolvedUiScale { get; set; } = 1f;

    /// <summary>
    /// When true, windows re-apply their default size on the next frame.
    /// Set by Plugin on layout reset or scale change; cleared after draw.
    /// </summary>
    internal bool LayoutResetRequested { get; set; }

    // ── User-facing: General ─────────────────────────────────────────

    public ConfigEntry<KeyCode> ToggleKey { get; }
    public ConfigEntry<bool> ReplaceQuestLog { get; }
    public ConfigEntry<float> UiScale { get; }
    public ConfigEntry<int> HistoryMaxSize { get; }
    public ConfigEntry<bool> ResetWindowLayout { get; }

    // ── User-facing: Navigation ──────────────────────────────────────

    public ConfigEntry<bool> ShowArrow { get; }
    public ConfigEntry<bool> ShowGroundPath { get; }
    public ConfigEntry<KeyCode> GroundPathToggleKey { get; }

    // ── User-facing: World Markers ───────────────────────────────────

    public ConfigEntry<bool> ShowWorldMarkers { get; }
    public ConfigEntry<float> MarkerScale { get; }
    public ConfigEntry<float> IconSize { get; }
    public ConfigEntry<float> SubTextSize { get; }
    public ConfigEntry<float> SubTextYOffset { get; }
    public ConfigEntry<float> IconYOffset { get; }

    // ── User-facing: Tracker ─────────────────────────────────────────

    public ConfigEntry<bool> TrackerEnabled { get; }
    public ConfigEntry<KeyCode> TrackerToggleKey { get; }
    public ConfigEntry<bool> TrackerAutoTrack { get; }
    public ConfigEntry<string> TrackerSortMode { get; }
    public ConfigEntry<float> TrackerBackgroundOpacity { get; }
    public ConfigEntry<bool> TrackerUntrackOnComplete { get; }

    // ── User-facing: Debug ──────────────────────────────────────────

    public ConfigEntry<bool> DiagnosticOverlay { get; }
    public ConfigEntry<bool> IncidentPanel { get; }

    // ── Internal: quest list state (auto-managed) ────────────────────

    public ConfigEntry<QuestFilterMode> FilterMode { get; }
    public ConfigEntry<QuestSortMode> SortMode { get; }
    public ConfigEntry<string> ZoneFilter { get; }

    // ── ConfigFile reference for dynamic per-character entries ────────

    /// <summary>
    /// Raw ConfigFile handle. Used by TrackerState to bind per-character
    /// entries at runtime (keyed by save slot index).
    /// </summary>
    public ConfigFile File { get; }

    // ─────────────────────────────────────────────────────────────────

    public GuideConfig(ConfigFile config)
    {
        File = config;

        // General
        ToggleKey = config.Bind(
            "General",
            "ToggleKey",
            KeyCode.L,
            "Key to toggle the Adventure Guide window"
        );
        ReplaceQuestLog = config.Bind(
            "General",
            "ReplaceQuestLog",
            false,
            "If true, pressing J opens Adventure Guide instead of the game's Quest Log"
        );
        UiScale = config.Bind(
            "General",
            "UiScale",
            -1f,
            new ConfigDescription(
                "UI scale factor. Affects font size and element spacing. "
                    + "Set to -1 to auto-detect from screen resolution.",
                new AcceptableValueRange<float>(-1f, 4f)
            )
        );
        HistoryMaxSize = config.Bind(
            "General",
            "HistoryMaxSize",
            100,
            new ConfigDescription(
                "Maximum number of pages in navigation history",
                new AcceptableValueRange<int>(10, 500)
            )
        );

        ResetWindowLayout = config.Bind(
            "General",
            "ResetWindowLayout",
            false,
            "Toggle to reset all window positions and sizes to defaults."
        );
        // Navigation
        ShowArrow = config.Bind(
            "Navigation",
            "ShowArrow",
            true,
            "Show directional arrow pointing toward navigation target"
        );
        ShowGroundPath = config.Bind(
            "Navigation",
            "ShowGroundPath",
            false,
            "Show ground path from player to navigation target (uses NavMesh pathfinding)"
        );
        GroundPathToggleKey = config.Bind(
            "Navigation",
            "GroundPathToggleKey",
            KeyCode.P,
            "Key to toggle the ground path overlay"
        );

        // World Markers
        ShowWorldMarkers = config.Bind(
            "World Markers",
            "Enabled",
            true,
            "Show floating quest markers above NPCs (!, ?, objective icons). Replaces the game's built-in markers when enabled."
        );
        MarkerScale = config.Bind(
            "World Markers",
            "Scale",
            1.0f,
            new ConfigDescription(
                "Overall scale of world markers",
                new AcceptableValueRange<float>(0.05f, 2.0f)
            )
        );
        IconSize = config.Bind(
            "World Markers",
            "IconSize",
            7f,
            new ConfigDescription(
                "Font size of the marker icon glyph",
                new AcceptableValueRange<float>(1f, 20f)
            )
        );
        SubTextSize = config.Bind(
            "World Markers",
            "SubTextSize",
            3.5f,
            new ConfigDescription(
                "Font size of the sub-text label",
                new AcceptableValueRange<float>(1f, 10f)
            )
        );
        SubTextYOffset = config.Bind(
            "World Markers",
            "SubTextYOffset",
            -1f,
            new ConfigDescription(
                "Y offset of sub-text relative to icon (negative = below)",
                new AcceptableValueRange<float>(-5f, 5f)
            )
        );
        IconYOffset = config.Bind(
            "World Markers",
            "IconYOffset",
            1f,
            new ConfigDescription(
                "Y offset of icon relative to marker root",
                new AcceptableValueRange<float>(-5f, 5f)
            )
        );

        // Tracker
        TrackerEnabled = config.Bind(
            "Tracker",
            "Enabled",
            true,
            "Enable the quest tracker overlay. When disabled, auto-tracking and the tracker window are inactive."
        );
        TrackerToggleKey = config.Bind(
            "Tracker",
            "ToggleKey",
            KeyCode.K,
            "Key to toggle the quest tracker overlay"
        );
        TrackerAutoTrack = config.Bind(
            "Tracker",
            "AutoTrack",
            true,
            "Automatically track newly accepted quests"
        );
        TrackerSortMode = config.Bind(
            "Tracker",
            "SortMode",
            "Proximity",
            "Sort order: Proximity, Level, or Alphabetical"
        );
        TrackerBackgroundOpacity = config.Bind(
            "Tracker",
            "BackgroundOpacity",
            0.40f,
            new ConfigDescription(
                "Opacity of the tracker background when not hovered (0 = fully transparent, 1 = opaque)",
                new AcceptableValueRange<float>(0f, 1f)
            )
        );
        TrackerUntrackOnComplete = config.Bind(
            "Tracker",
            "UntrackOnComplete",
            true,
            "Automatically untrack quests when they are completed"
        );

        // Debug
        DiagnosticOverlay = config.Bind(
            "Debug",
            "DiagnosticOverlay",
            false,
            "Show a diagnostic overlay with active quest count, marker count, NAV targets, and frame cost"
        );
        IncidentPanel = config.Bind(
            "Debug",
            "IncidentPanel",
            false,
            "Show the incident diagnostics panel with last-capture details and manual capture controls"
        );

        // Internal: quest list state (hidden from F1)
        FilterMode = Bind(config, "_State", "FilterMode", QuestFilterMode.Active);
        SortMode = Bind(config, "_State", "SortMode", QuestSortMode.ByLevel);
        ZoneFilter = Bind(config, "_State", "ZoneFilter", "");
    }

    /// <summary>Bind a hidden config entry (not shown in ConfigurationManager).</summary>
    private static ConfigEntry<T> Bind<T>(
        ConfigFile config,
        string section,
        string key,
        T defaultValue
    ) =>
        config.Bind(
            section,
            key,
            defaultValue,
            new ConfigDescription("Auto-managed by Adventure Guide", null, Hidden)
        );

    /// <summary>
    /// Bind a hidden config entry scoped to a character save slot.
    /// Used by subsystems that persist per-character state (tracked quests,
    /// navigation target, etc.).
    /// </summary>
    public ConfigEntry<T> BindPerCharacter<T>(int slotIndex, string key, T defaultValue) =>
        File.Bind(
            "_Character",
            $"{key}_Slot{slotIndex}",
            defaultValue,
            new ConfigDescription(
                $"Per-character state for slot {slotIndex} (auto-managed)",
                null,
                Hidden
            )
        );
}
