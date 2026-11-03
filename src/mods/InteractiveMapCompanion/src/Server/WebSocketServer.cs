using System.Collections.Concurrent;
using Fleck;
using InteractiveMapCompanion.Config;
using InteractiveMapCompanion.Protocol;

namespace InteractiveMapCompanion.Server;

/// <summary>
/// Fleck-based WebSocket server for the map on the same PC. It listens on loopback only.
/// Other devices connect through <see cref="WebRtc.WebRtcServer"/> while sharing is on.
/// </summary>
public sealed class WebSocketServer : IWebSocketServer
{
    private readonly IModConfig _config;
    private readonly IModLogger _logger;
    private readonly Func<bool, string> _handshake;
    private readonly Action<bool> _setSharing;
    private readonly ConcurrentDictionary<Guid, LocalClient> _clients = new();
    private readonly object _lifecycleGate = new();

    private Fleck.WebSocketServer? _server;
    private Action<Fleck.LogLevel, string, Exception>? _previousFleckLogAction;
    private Action<Fleck.LogLevel, string, Exception>? _fleckLogAction;
    private bool _stopped;
    private bool _disposed;

    public int ClientCount => _clients.Count;

    /// <summary>
    /// <paramref name="handshake"/> builds the handshake for a new client and receives
    /// whether that client is a trusted map (<see cref="MapOrigins"/>).
    /// <paramref name="setSharing"/> receives a trusted map's <c>setSharing</c> request on
    /// a Fleck thread.
    /// </summary>
    public WebSocketServer(
        IModConfig config,
        IModLogger logger,
        Func<bool, string> handshake,
        Action<bool> setSharing
    )
    {
        _config = config;
        _logger = logger;
        _handshake = handshake;
        _setSharing = setSharing;
        ConfigureFleckLogging();
    }

    public void Start()
    {
        var port = _config.Port;
        var location = $"ws://127.0.0.1:{port}";

        lock (_lifecycleGate)
        {
            if (_disposed || _server != null)
                return;

            try
            {
                var server = new Fleck.WebSocketServer(location);
                _stopped = false;
                _server = server;
                server.Start(ConfigureSocket);
                _logger.LogInfo($"WebSocket server started on {location}");
            }
            catch (Exception ex)
            {
                _server = null;
                _stopped = true;
                _logger.LogError($"Failed to start WebSocket server on port {port}: {ex.Message}");
                _logger.LogDebug(ex.ToString());
            }
        }
    }

    public void Stop()
    {
        Fleck.WebSocketServer? server;
        IWebSocketConnection[] clients;

        lock (_lifecycleGate)
        {
            if (_stopped && _server == null && _clients.IsEmpty)
                return;

            _stopped = true;
            server = _server;
            _server = null;
            clients = _clients.Values.Select(client => client.Socket).ToArray();
            _clients.Clear();
        }

        foreach (var client in clients)
        {
            try
            {
                client.Close();
            }
            catch
            {
                // Ignore errors during shutdown.
            }
        }

        try
        {
            server?.Dispose();
        }
        catch (Exception ex)
        {
            _logger.LogDebug($"WebSocket server disposal failed: {ex.Message}");
        }

        if (server != null)
            _logger.LogInfo("WebSocket server stopped");
    }

    public void Broadcast(string message) => Send(message, trustedOnly: false);

    public void BroadcastToTrusted(string message) => Send(message, trustedOnly: true);

    private void Send(string message, bool trustedOnly)
    {
        if (_disposed || _stopped)
            return;

        foreach (var (id, client) in _clients)
        {
            if (trustedOnly && !client.Trusted)
                continue;

            try
            {
                if (client.Socket.IsAvailable && !_stopped && !_disposed)
                {
                    client.Socket.Send(message);
                }
                else
                {
                    _clients.TryRemove(id, out _);
                }
            }
            catch (Exception ex)
            {
                _logger.LogWarning($"Failed to send to client {id}: {ex.Message}");
                _clients.TryRemove(id, out _);
            }
        }
    }

    public void Dispose()
    {
        lock (_lifecycleGate)
        {
            if (_disposed)
                return;

            _disposed = true;
        }

        Stop();
        RestoreFleckLogging();
    }

    private void ConfigureSocket(IWebSocketConnection socket)
    {
        socket.OnOpen = () => OnClientConnected(socket);
        socket.OnClose = () => OnClientDisconnected(socket);
        socket.OnError = ex => OnClientError(socket, ex);
        socket.OnMessage = message => OnClientMessage(socket, message);
    }

    private void OnClientConnected(IWebSocketConnection socket)
    {
        var client = new LocalClient(socket, MapOrigins.IsTrusted(socket.ConnectionInfo.Origin));
        bool reject;
        lock (_lifecycleGate)
        {
            reject = _disposed || _stopped;
            if (!reject)
                _clients[socket.ConnectionInfo.Id] = client;
        }

        if (reject)
        {
            try
            {
                socket.Close();
            }
            catch
            {
                // Ignore connections racing shutdown.
            }

            return;
        }

        _logger.LogInfo(
            $"Client connected: {socket.ConnectionInfo.ClientIpAddress} (total: {ClientCount})"
        );

        SendHandshake(client);
    }

    private void OnClientDisconnected(IWebSocketConnection socket)
    {
        _clients.TryRemove(socket.ConnectionInfo.Id, out _);
        if (!_disposed)
        {
            _logger.LogInfo(
                $"Client disconnected: {socket.ConnectionInfo.ClientIpAddress} (total: {ClientCount})"
            );
        }
    }

    private void OnClientError(IWebSocketConnection socket, Exception ex)
    {
        if (!_disposed)
            _logger.LogWarning(
                $"Client error ({socket.ConnectionInfo.ClientIpAddress}): {ex.Message}"
            );
        _clients.TryRemove(socket.ConnectionInfo.Id, out _);
    }

    private void OnClientMessage(IWebSocketConnection socket, string message)
    {
        if (_disposed || _stopped)
            return;

        if (
            _clients.TryGetValue(socket.ConnectionInfo.Id, out var client)
            && client.Trusted
            && ClientMessages.TryReadSetSharing(message, out bool enabled)
        )
        {
            _setSharing(enabled);
            return;
        }

        _logger.LogDebug(
            $"Ignored message from {socket.ConnectionInfo.ClientIpAddress} ({socket.ConnectionInfo.Origin}): {message}"
        );
    }

    private void SendHandshake(LocalClient client)
    {
        try
        {
            string json = _handshake(client.Trusted);
            if (!_disposed && !_stopped)
                client.Socket.Send(json);
        }
        catch (Exception ex)
        {
            _logger.LogWarning($"Failed to send handshake: {ex.Message}");
        }
    }

    private sealed class LocalClient(IWebSocketConnection socket, bool trusted)
    {
        public IWebSocketConnection Socket { get; } = socket;

        /// <summary>
        /// Whether the page is the map (<see cref="MapOrigins"/>), which may see and
        /// change sharing.
        /// </summary>
        public bool Trusted { get; } = trusted;
    }

    private void ConfigureFleckLogging()
    {
        _previousFleckLogAction = FleckLog.LogAction;
        _fleckLogAction = (level, message, ex) =>
        {
            var configuredLevel = _config.WebSocketLogLevel;
            bool shouldLog = level switch
            {
                Fleck.LogLevel.Debug => configuredLevel
                    == InteractiveMapCompanion.Config.LogLevel.Debug,
                Fleck.LogLevel.Info => configuredLevel
                    == InteractiveMapCompanion.Config.LogLevel.Debug
                    || configuredLevel == InteractiveMapCompanion.Config.LogLevel.Info,
                Fleck.LogLevel.Warn => configuredLevel
                    == InteractiveMapCompanion.Config.LogLevel.Debug
                    || configuredLevel == InteractiveMapCompanion.Config.LogLevel.Info
                    || configuredLevel == InteractiveMapCompanion.Config.LogLevel.Warning,
                Fleck.LogLevel.Error => true,
                _ => false,
            };

            if (!shouldLog)
                return;

            switch (level)
            {
                case Fleck.LogLevel.Debug:
                    _logger.LogDebug($"[Fleck] {message}");
                    break;
                case Fleck.LogLevel.Info:
                    _logger.LogInfo($"[Fleck] {message}");
                    break;
                case Fleck.LogLevel.Warn:
                    _logger.LogWarning($"[Fleck] {message}");
                    break;
                case Fleck.LogLevel.Error:
                    _logger.LogError($"[Fleck] {message}");
                    if (ex != null)
                        _logger.LogDebug(ex.ToString());
                    break;
            }
        };
        FleckLog.LogAction = _fleckLogAction;
    }

    private void RestoreFleckLogging()
    {
        if (_fleckLogAction != null && ReferenceEquals(FleckLog.LogAction, _fleckLogAction))
            FleckLog.LogAction = _previousFleckLogAction;

        _fleckLogAction = null;
        _previousFleckLogAction = null;
    }
}
