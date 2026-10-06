using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using UnityEngine;

namespace MapTileCapture;

/// <summary>
/// Loader-neutral lifecycle owner for the capture server and its two capture
/// modes: map tiles of a zone and portraits of single characters. It routes
/// each inbound message to its mode and runs one capture at a time.
/// </summary>
internal sealed class MapTileCaptureRuntime
{
    private readonly IModLogger _logger;
    private readonly MonoBehaviour _coroutineHost;

    private Server.CaptureWebSocketServer? _server;
    private Capture.CaptureController? _zones;
    private Capture.PortraitController? _portraits;
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
        _zones = new Capture.CaptureController(_server, _coroutineHost, _logger);
        _portraits = new Capture.PortraitController(_server, _coroutineHost, _logger);
        _server.Start();
        _logger.LogInfo($"{PluginInfo.PluginName} v{PluginInfo.Version} loaded");
    }

    /// <summary>Called every frame. Drains inbound messages and routes each to its capture mode.</summary>
    public void Tick()
    {
        if (!_started || _server == null)
            return;

        while (_server.TryDequeue() is { } json)
            Route(json);
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
        _zones?.Dispose();
        _zones = null;
        _portraits?.Dispose();
        _portraits = null;
        _server?.Dispose();
        _server = null;
    }

    private void Route(string json)
    {
        string? type;
        try
        {
            type = JObject.Parse(json)["type"]?.ToString();
        }
        catch (JsonException ex)
        {
            _logger.LogError($"Failed to parse inbound message: {ex.Message}");
            return;
        }

        var zones = _zones!;
        var portraits = _portraits!;
        switch (type)
        {
            case "capture_zone":
                if (portraits.IsBusy)
                    zones.Reject(json, "A portrait capture is running.");
                else
                    zones.HandleCaptureZone(json);
                break;
            case "capture_portrait":
                if (zones.IsBusy)
                    portraits.Reject("A zone capture is running.");
                else
                    portraits.HandleCapture(json);
                break;
            case "end_portraits":
                if (zones.IsBusy)
                    portraits.Reject("A zone capture is running.");
                else
                    portraits.HandleEnd();
                break;
            case "cancel_capture":
                zones.Cancel();
                portraits.Cancel();
                break;
            case null:
                _logger.LogWarning("Received message without 'type' field");
                break;
            default:
                _logger.LogWarning($"Unknown message type: {type}");
                break;
        }
    }
}
