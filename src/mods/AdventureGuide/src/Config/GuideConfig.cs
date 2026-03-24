using AdventureGuide.UI;
using BepInEx.Configuration;
using UnityEngine;

namespace AdventureGuide.Config;

public sealed class GuideConfig
{
    public ConfigEntry<KeyCode> ToggleKey { get; }
    public ConfigEntry<bool> ReplaceQuestLog { get; }
    public ConfigEntry<bool> ShowArrow { get; }
    public ConfigEntry<bool> ShowGroundPath { get; }
    public ConfigEntry<bool> ShowWorldMarkers { get; }
    public ConfigEntry<float> UiScale { get; }
    public ConfigEntry<int> HistoryMaxSize { get; }

    // Persisted filter/sort state
    public ConfigEntry<QuestFilterMode> FilterMode { get; }
    public ConfigEntry<QuestSortMode> SortMode { get; }
    public ConfigEntry<string> ZoneFilter { get; }

    // Marker tuning — adjust via F1 config manager
    public ConfigEntry<float> MarkerScale { get; }
    public ConfigEntry<float> IconSize { get; }
    public ConfigEntry<float> SubTextSize { get; }
    public ConfigEntry<float> SubTextYOffset { get; }
    public ConfigEntry<float> IconYOffset { get; }

    // Tracker overlay
    public ConfigEntry<KeyCode> TrackerToggleKey { get; }
    public ConfigEntry<bool> TrackerAutoTrack { get; }
    public ConfigEntry<string> TrackerSortMode { get; }
    public ConfigEntry<string> TrackedQuests { get; }
    public ConfigEntry<float> TrackerIdleOpacity { get; }
    public ConfigEntry<float> TrackerHoverOpacity { get; }

    public GuideConfig(ConfigFile config)
    {
        ToggleKey = config.Bind("General", "ToggleKey", KeyCode.L,
            "Key to toggle the Adventure Guide window");
        ReplaceQuestLog = config.Bind("General", "ReplaceQuestLog", false,
            "If true, pressing J opens Adventure Guide instead of the game's Quest Log");
        UiScale = config.Bind("General", "UiScale", 1.0f,
            new ConfigDescription(
                "UI scale factor. Affects font size and element spacing. Requires game restart.",
                new AcceptableValueRange<float>(0.75f, 2.0f)));
        ShowArrow = config.Bind("Navigation", "ShowArrow", true,
            "Show directional arrow pointing toward navigation target");
        ShowGroundPath = config.Bind("Navigation", "ShowGroundPath", false,
            "Show ground path from player to navigation target (uses NavMesh pathfinding)");
        ShowWorldMarkers = config.Bind("WorldMarkers", "ShowWorldMarkers", false,
            "Show floating quest markers above NPCs (!, ?, objective icons). Replaces the game's built-in markers when enabled.");

        MarkerScale = config.Bind("WorldMarkers", "MarkerScale", 1.0f,
            new ConfigDescription("Overall scale of world markers",
                new AcceptableValueRange<float>(0.05f, 2.0f)));
        IconSize = config.Bind("WorldMarkers", "IconSize", 7f,
            new ConfigDescription("Font size of the marker icon glyph",
                new AcceptableValueRange<float>(1f, 20f)));
        SubTextSize = config.Bind("WorldMarkers", "SubTextSize", 3.5f,
            new ConfigDescription("Font size of the sub-text label",
                new AcceptableValueRange<float>(1f, 10f)));
        SubTextYOffset = config.Bind("WorldMarkers", "SubTextYOffset", -1f,
            new ConfigDescription("Y offset of sub-text relative to icon (negative = below)",
                new AcceptableValueRange<float>(-5f, 5f)));
        IconYOffset = config.Bind("WorldMarkers", "IconYOffset", 1f,
            new ConfigDescription("Y offset of icon relative to marker root",
                new AcceptableValueRange<float>(-5f, 5f)));

        FilterMode = config.Bind("QuestList", "FilterMode", QuestFilterMode.Active,
            "Last selected quest filter (Active, Available, Completed, All)");
        SortMode = config.Bind("QuestList", "SortMode", QuestSortMode.Alphabetical,
            "Last selected sort mode (Alphabetical, ByZone, ByLevel)");
        ZoneFilter = config.Bind("QuestList", "ZoneFilter", "",
            "Last selected zone filter (empty = all zones)");
        HistoryMaxSize = config.Bind("General", "HistoryMaxSize", 100,
            new ConfigDescription("Maximum number of pages in navigation history",
                new AcceptableValueRange<int>(10, 500)));

        TrackerToggleKey = config.Bind("Tracker", "ToggleKey", KeyCode.K,
            "Key to toggle the quest tracker overlay");
        TrackerAutoTrack = config.Bind("Tracker", "AutoTrack", true,
            "Automatically track newly accepted quests");
        TrackerSortMode = config.Bind("Tracker", "SortMode", "Proximity",
            "Sort order: Proximity, Level, or Alphabetical");
        TrackedQuests = config.Bind("Tracker", "TrackedQuests", "",
            "Semicolon-delimited list of tracked quest DB names (auto-managed)");
        TrackerIdleOpacity = config.Bind("Tracker", "IdleOpacity", 0.6f,
            new ConfigDescription("Background opacity when not hovering",
                new AcceptableValueRange<float>(0.1f, 1.0f)));
        TrackerHoverOpacity = config.Bind("Tracker", "HoverOpacity", 0.9f,
            new ConfigDescription("Background opacity when hovering",
                new AcceptableValueRange<float>(0.1f, 1.0f)));
    }
}
