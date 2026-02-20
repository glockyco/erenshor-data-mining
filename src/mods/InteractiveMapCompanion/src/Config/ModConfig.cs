using BepInEx.Configuration;
using UnityEngine;

namespace InteractiveMapCompanion.Config;

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
/// BepInEx configuration for the Interactive Map Companion mod.
/// </summary>
public class ModConfig
{
    public ConfigEntry<int> Port { get; }
    public ConfigEntry<int> UpdateInterval { get; }
    public ConfigEntry<bool> EnableSpawnTracking { get; }
    public ConfigEntry<bool> EnableThirdPartyMarkers { get; }
    public ConfigEntry<bool> EnableBidirectional { get; }
    public ConfigEntry<LogLevel> WebSocketLogLevel { get; }
    public ConfigEntry<LogLevel> ModLogLevel { get; }

    // Overlay settings
    public ConfigEntry<bool> EnableOverlay { get; }
    public ConfigEntry<KeyCode> ToggleKey { get; }
    public ConfigEntry<float> AnchorX { get; }
    public ConfigEntry<float> AnchorY { get; }
    public ConfigEntry<int> OverlayWidth { get; }
    public ConfigEntry<int> OverlayHeight { get; }
    public ConfigEntry<bool> ResetToDefaults { get; }

    public ModConfig(ConfigFile config)
    {
        Port = config.Bind(
            "Server",
            "Port",
            18585,
            "WebSocket server port. Clients connect to ws://localhost:{port}"
        );

        UpdateInterval = config.Bind(
            "Server",
            "UpdateInterval",
            100,
            "Interval in milliseconds between state broadcasts to clients"
        );

        EnableSpawnTracking = config.Bind(
            "Features",
            "EnableSpawnTracking",
            true,
            "Track enemy deaths and broadcast respawn timers"
        );

        EnableThirdPartyMarkers = config.Bind(
            "Features",
            "EnableThirdPartyMarkers",
            true,
            "Allow other mods to register custom markers via the API"
        );

        EnableBidirectional = config.Bind(
            "Features",
            "EnableBidirectional",
            true,
            "Accept messages from clients (waypoints, pings, commands)"
        );

        WebSocketLogLevel = config.Bind(
            "Logging",
            "WebSocketLogLevel",
            LogLevel.Warning,
            "Log level for WebSocket library. Debug shows all messages (verbose), Warning shows only issues (recommended)."
        );

        ModLogLevel = config.Bind(
            "Logging",
            "ModLogLevel",
            LogLevel.Info,
            "Log level for the mod itself. Debug shows detailed diagnostics, Info shows important events (recommended)."
        );

        EnableOverlay = config.Bind(
            "Overlay",
            "EnableOverlay",
            true,
            "Show the interactive map as an in-game overlay panel (requires Steam)"
        );

        ToggleKey = config.Bind(
            "Overlay",
            "ToggleKey",
            KeyCode.M,
            "Key to show/hide the in-game map overlay"
        );

        AnchorX = config.Bind(
            "Overlay",
            "AnchorX",
            -1f,
            "Normalized horizontal anchor for the overlay panel (0 = left edge, 1 = right edge). -1 = auto (centred, computed on first run)"
        );

        AnchorY = config.Bind(
            "Overlay",
            "AnchorY",
            -1f,
            "Normalized vertical anchor for the overlay panel (0 = bottom, 1 = top). -1 = auto (centred, computed on first run)"
        );

        OverlayWidth = config.Bind(
            "Overlay",
            "Width",
            0,
            "Width of the in-game map overlay in pixels. 0 = auto (80% of screen width, computed on first run)"
        );

        OverlayHeight = config.Bind(
            "Overlay",
            "Height",
            0,
            "Height of the in-game map overlay in pixels. 0 = auto (80% of screen height, computed on first run)"
        );

        ResetToDefaults = config.Bind(
            "Overlay",
            "ResetToDefaults",
            false,
            "Set to true to reset size and position to auto-computed defaults on next game launch. Resets itself to false automatically."
        );
    }

    /// <summary>
    /// Returns the list of enabled capabilities based on current configuration.
    /// </summary>
    public string[] GetCapabilities()
    {
        var capabilities = new List<string> { "entities" };

        if (EnableSpawnTracking.Value)
            capabilities.Add("spawns");

        if (EnableThirdPartyMarkers.Value)
            capabilities.Add("markers");

        if (EnableBidirectional.Value)
            capabilities.Add("bidirectional");

        return capabilities.ToArray();
    }
}
