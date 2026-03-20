using BepInEx;
using BepInEx.Configuration;
using BepInEx.Logging;
using MapTileCapture.Capture;
using MapTileCapture.Server;

namespace MapTileCapture;

/// <summary>
/// Main plugin entry point for Map Tile Capture.
/// Accepts capture commands from the Python pipeline via WebSocket and renders
/// orthographic screenshots of each map chunk.
/// </summary>
[BepInPlugin(PluginInfo.PluginGuid, PluginInfo.PluginName, PluginInfo.Version)]
public sealed class Plugin : BaseUnityPlugin
{
    internal static ManualLogSource Log { get; private set; } = null!;

    // Section "IndoorLighting" — only applied when usingSun=false
    public static ConfigEntry<float> IndoorDirectionalIntensity = null!;
    public static ConfigEntry<float> IndoorAmbientIntensity = null!;
    public static ConfigEntry<float> IndoorDirectionalPitch = null!;
    public static ConfigEntry<float> IndoorDirectionalYaw = null!;

    // Section "Capture" — fallback defaults when request doesn't specify (>0)
    public static ConfigEntry<int>   DefaultStabilityFrames = null!;
    public static ConfigEntry<float> DefaultSceneLoadTimeoutSecs = null!;

    private CaptureWebSocketServer? _server;
    private CaptureController? _controller;

    private void Awake()
    {
        Log = Logger;

        IndoorDirectionalIntensity = Config.Bind("IndoorLighting", "DirectionalIntensity", 1.0f,
            "Intensity of the temporary directional light added during indoor/no-sun zone captures.");
        IndoorAmbientIntensity = Config.Bind("IndoorLighting", "AmbientIntensity", 0.6f,
            "Flat ambient light multiplier (applied to white) during indoor/no-sun zone captures.");
        IndoorDirectionalPitch = Config.Bind("IndoorLighting", "DirectionalPitch", 50f,
            "Euler X angle (pitch) of the capture directional light. 90 = straight down.");
        IndoorDirectionalYaw = Config.Bind("IndoorLighting", "DirectionalYaw", -30f,
            "Euler Y angle (yaw) of the capture directional light.");
        DefaultStabilityFrames = Config.Bind("Capture", "DefaultStabilityFrames", 10,
            "Frames to wait after scene load before capturing. Overridden per-zone by the Python request.");
        DefaultSceneLoadTimeoutSecs = Config.Bind("Capture", "DefaultSceneLoadTimeoutSecs", 30f,
            "Scene load timeout in seconds. Overridden per-zone by the Python request.");

        _server = new CaptureWebSocketServer(Log);
        _controller = new CaptureController(_server, this, Log);
        _server.Start();

        Log.LogInfo($"{PluginInfo.PluginName} v{PluginInfo.Version} loaded");
    }

    private void Update()
    {
        _controller?.Tick();
    }

    private void OnDestroy()
    {
        _server?.Dispose();
    }
}
