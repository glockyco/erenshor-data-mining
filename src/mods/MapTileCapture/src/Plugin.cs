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
