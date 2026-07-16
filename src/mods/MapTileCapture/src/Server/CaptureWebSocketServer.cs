using System.Collections.Concurrent;
using Fleck;

namespace MapTileCapture.Server;

/// <summary>
/// Single-client WebSocket server for the tile capture pipeline.
/// Python sends capture commands inbound; the mod sends progress/results outbound.
/// </summary>
internal sealed class CaptureWebSocketServer : IDisposable
{
    private const string Location = "ws://0.0.0.0:18586";

    private readonly IModLogger _logger;
    private readonly ConcurrentQueue<string> _inbound = new();

    private Fleck.WebSocketServer? _server;
    private IWebSocketConnection? _client;
    private volatile bool _disposed;

    public CaptureWebSocketServer(IModLogger logger)
    {
        _logger = logger;
    }

    public void Start()
    {
        if (_disposed || _server != null)
            return;

        try
        {
            _server = new Fleck.WebSocketServer(Location);
            _server.Start(ConfigureSocket);
            _logger.LogInfo($"Capture WebSocket server started on {Location}");
        }
        catch (Exception ex)
        {
            _server = null;
            _logger.LogError($"Failed to start capture WebSocket server: {ex.Message}");
            _logger.LogDebug(ex.ToString());
        }
    }

    public string? TryDequeue()
    {
        return _disposed || !_inbound.TryDequeue(out var message) ? null : message;
    }

    public void Send(string json)
    {
        if (_disposed)
            return;

        var client = _client;
        if (client == null || !client.IsAvailable)
            return;

        try
        {
            client.Send(json);
        }
        catch (Exception ex)
        {
            _logger.LogWarning($"Failed to send to capture client: {ex.Message}");
        }
    }

    public void Dispose()
    {
        if (_disposed)
            return;

        _disposed = true;
        _inbound.Clear();

        var client = _client;
        _client = null;

        try
        {
            client?.Close();
        }
        catch
        {
            // Ignore errors during shutdown
        }

        _server?.Dispose();
        _server = null;
        _logger.LogInfo("Capture WebSocket server stopped");
    }

    private void ConfigureSocket(IWebSocketConnection socket)
    {
        socket.OnOpen = () =>
        {
            if (_disposed)
            {
                try
                {
                    socket.Close();
                }
                catch
                { /* best-effort */
                }
                return;
            }

            // Single-client: replace any existing connection
            var previous = _client;
            _client = socket;
            _logger.LogInfo($"Capture client connected: {socket.ConnectionInfo.ClientIpAddress}");

            if (previous != null && previous != socket)
            {
                try
                {
                    previous.Close();
                }
                catch
                { /* best-effort */
                }
            }
        };

        socket.OnClose = () =>
        {
            if (_client == socket)
                _client = null;
            if (!_disposed)
                _logger.LogInfo(
                    $"Capture client disconnected: {socket.ConnectionInfo.ClientIpAddress}"
                );
        };

        socket.OnError = ex =>
        {
            if (!_disposed)
                _logger.LogWarning(
                    $"Capture client error ({socket.ConnectionInfo.ClientIpAddress}): {ex.Message}"
                );
            if (_client == socket)
                _client = null;
        };

        socket.OnMessage = message =>
        {
            if (!_disposed)
                _inbound.Enqueue(message);
        };
    }
}
