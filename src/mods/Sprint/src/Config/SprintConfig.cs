using BepInEx.Configuration;
using UnityEngine;

namespace Sprint.Config;

/// <summary>
/// Log level for controlling verbosity of log output.
/// </summary>
public enum LogLevel
{
    Debug,
    Info,
    Warning,
    Error,
}

/// <summary>
/// BepInEx configuration for the Sprint mod.
/// </summary>
public class SprintConfig
{
    public ConfigEntry<KeyCode> SprintKey { get; }
    public ConfigEntry<bool> ToggleMode { get; }
    public ConfigEntry<float> SprintMultiplier { get; }
    public ConfigEntry<LogLevel> ModLogLevel { get; }

    public SprintConfig(ConfigFile config)
    {
        SprintKey = config.Bind(
            "Controls",
            "SprintKey",
            KeyCode.LeftShift,
            "Key to activate sprint. See Unity KeyCode documentation for valid values (e.g., LeftShift, RightShift, Space, LeftControl)."
        );

        ToggleMode = config.Bind(
            "Controls",
            "ToggleMode",
            false,
            "If true, tap sprint key to toggle sprint on/off. If false, hold sprint key to sprint."
        );

        SprintMultiplier = config.Bind(
            "Speed",
            "SprintMultiplier",
            1.5f,
            new ConfigDescription(
                "Speed multiplier when sprinting. 1.0 = normal speed, 1.5 = 50% faster, 2.0 = double speed, 10.0 = ludicrous speed!",
                new AcceptableValueRange<float>(1.0f, 10.0f)
            )
        );

        ModLogLevel = config.Bind(
            "Logging",
            "LogLevel",
            LogLevel.Info,
            "Log level for the mod. Debug shows detailed diagnostics, Info shows important events (recommended)."
        );
    }
}
