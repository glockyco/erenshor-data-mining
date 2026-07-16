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
/// Loader-neutral configuration consumed by the map companion runtime.
/// Adapters own persistence and binding for their loader.
/// </summary>
public interface IModConfig
{
    int Port { get; }
    int UpdateInterval { get; }
    bool EnableSpawnTracking { get; }
    bool EnableThirdPartyMarkers { get; }
    bool EnableBidirectional { get; }
    LogLevel WebSocketLogLevel { get; }
    LogLevel ModLogLevel { get; }
    bool EnableOverlay { get; }
    KeyCode ToggleKey { get; }
    float AnchorX { get; set; }
    float AnchorY { get; set; }
    int OverlayWidth { get; set; }
    int OverlayHeight { get; set; }
    bool ResetToDefaults { get; set; }

    string[] GetCapabilities();
}

/// <summary>
/// Shared capability calculation used by both native loader adapters.
/// </summary>
public abstract class ModConfigBase : IModConfig
{
    public abstract int Port { get; }
    public abstract int UpdateInterval { get; }
    public abstract bool EnableSpawnTracking { get; }
    public abstract bool EnableThirdPartyMarkers { get; }
    public abstract bool EnableBidirectional { get; }
    public abstract LogLevel WebSocketLogLevel { get; }
    public abstract LogLevel ModLogLevel { get; }
    public abstract bool EnableOverlay { get; }
    public abstract KeyCode ToggleKey { get; }
    public abstract float AnchorX { get; set; }
    public abstract float AnchorY { get; set; }
    public abstract int OverlayWidth { get; set; }
    public abstract int OverlayHeight { get; set; }
    public abstract bool ResetToDefaults { get; set; }

    public string[] GetCapabilities()
    {
        var capabilities = new List<string> { "entities" };

        if (EnableSpawnTracking)
            capabilities.Add("spawns");

        if (EnableThirdPartyMarkers)
            capabilities.Add("markers");

        if (EnableBidirectional)
            capabilities.Add("bidirectional");

        return capabilities.ToArray();
    }
}
