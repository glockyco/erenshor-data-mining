using BepInEx;
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

    // ── Indoor lighting ──────────────────────────────────────────────────────
    // Applied only when usingSun=false. Tune via HotRepl before running captures:
    //   MapTileCapture.Plugin.IndoorDirectionalIntensity = 0.7f;
    public static float IndoorDirectionalIntensity = 0.7f;
    public static float IndoorAmbientIntensity     = 0.45f;
    public static float IndoorDirectionalPitch     = 50f;   // euler X
    public static float IndoorDirectionalYaw       = -30f;  // euler Y

    // ── Camera background ────────────────────────────────────────────────────
    // Fill colour for empty areas of the capture (outside terrain bounds).
    // Default is a dark olive-green matching the Erenshor world map background.
    public static float BackgroundR = 0.39f;
    public static float BackgroundG = 0.41f;
    public static float BackgroundB = 0.27f;

    // ── Capture defaults ─────────────────────────────────────────────────────
    // Used when the Python request does not specify a value (i.e. field is 0).
    public static int   DefaultStabilityFrames      = 10;
    public static float DefaultSceneLoadTimeoutSecs = 30f;

    private CaptureWebSocketServer? _server;
    private CaptureController? _controller;

    private void Awake()
    {
        Log = Logger;

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
