using BepInEx.Configuration;
using UnityEngine;

namespace AdventureGuide.Config;

public sealed class GuideConfig
{
    public ConfigEntry<KeyCode> ToggleKey { get; }
    public ConfigEntry<bool> ReplaceQuestLog { get; }

    public GuideConfig(ConfigFile config)
    {
        ToggleKey = config.Bind("General", "ToggleKey", KeyCode.G,
            "Key to toggle the Adventure Guide window");
        ReplaceQuestLog = config.Bind("General", "ReplaceQuestLog", false,
            "If true, pressing J opens Adventure Guide instead of the game's Quest Log");
    }
}
