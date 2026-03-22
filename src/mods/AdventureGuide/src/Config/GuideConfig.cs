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

    // Persisted filter/sort state
    public ConfigEntry<QuestFilterMode> FilterMode { get; }
    public ConfigEntry<QuestSortMode> SortMode { get; }
    public ConfigEntry<string> ZoneFilter { get; }

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

        FilterMode = config.Bind("QuestList", "FilterMode", QuestFilterMode.Active,
            "Last selected quest filter (Active, Available, Completed, All)");
        SortMode = config.Bind("QuestList", "SortMode", QuestSortMode.Alphabetical,
            "Last selected sort mode (Alphabetical, ByZone, ByLevel)");
        ZoneFilter = config.Bind("QuestList", "ZoneFilter", "",
            "Last selected zone filter (empty = all zones)");
    }
}