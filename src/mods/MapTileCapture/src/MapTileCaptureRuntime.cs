using UnityEngine;

namespace MapTileCapture;

/// <summary>
/// Loader-neutral lifecycle owner for the map tile capture server and controller.
/// </summary>
internal sealed class MapTileCaptureRuntime
{
    private readonly IModLogger _logger;
    private readonly MonoBehaviour _coroutineHost;

    private Server.CaptureWebSocketServer? _server;
    private Capture.CaptureController? _controller;
    private bool _started;

    public MapTileCaptureRuntime(IModLogger logger, MonoBehaviour coroutineHost)
    {
        _logger = logger;
        _coroutineHost = coroutineHost;
    }

    public void Start()
    {
        if (_started)
            return;

        _started = true;
        _server = new Server.CaptureWebSocketServer(_logger);
        _controller = new Capture.CaptureController(_server, _coroutineHost, _logger);
        _server.Start();
        _logger.LogInfo($"{PluginInfo.PluginName} v{PluginInfo.Version} loaded");
    }

    public void Tick()
    {
        if (!_started)
            return;

        _controller?.Tick();
    }

    public void NotifyApplicationQuitting()
    {
        Stop();
    }

    public void Stop()
    {
        if (!_started)
            return;

        _started = false;
        _controller?.Dispose();
        _controller = null;
        _server?.Dispose();
        _server = null;
    }
}
