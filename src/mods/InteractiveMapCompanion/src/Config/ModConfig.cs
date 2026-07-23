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
public interface IModConfig : IBroadcastConfig
{
    int Port { get; }
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
    public abstract LogLevel WebSocketLogLevel { get; }
    public abstract LogLevel ModLogLevel { get; }
    public abstract bool EnableOverlay { get; }
    public abstract KeyCode ToggleKey { get; }
    public abstract float AnchorX { get; set; }
    public abstract float AnchorY { get; set; }
    public abstract int OverlayWidth { get; set; }
    public abstract int OverlayHeight { get; set; }
    public abstract bool ResetToDefaults { get; set; }

    public string[] GetCapabilities() => ["entities"];
}
