using System.Collections.Concurrent;
using Fleck;
using InteractiveMapCompanion.Config;
using InteractiveMapCompanion.Protocol;
using UnityEngine.SceneManagement;

namespace InteractiveMapCompanion.Server;

/// <summary>
/// Fleck-based WebSocket server implementation.
/// Handles client connections and broadcasts messages to all connected clients.
/// </summary>
public sealed class WebSocketServer : IWebSocketServer
{
    private readonly IModConfig _config;
    private readonly IModLogger _logger;
    private readonly ConcurrentDictionary<Guid, IWebSocketConnection> _clients = new();
    private readonly object _lifecycleGate = new();

    private Fleck.WebSocketServer? _server;
    private Action<Fleck.LogLevel, string, Exception>? _previousFleckLogAction;
    private Action<Fleck.LogLevel, string, Exception>? _fleckLogAction;
    private bool _stopped;
    private bool _disposed;

    public int ClientCount => _clients.Count;

    public WebSocketServer(IModConfig config, IModLogger logger)
    {
        _config = config;
        _logger = logger;
        ConfigureFleckLogging();
    }

    public void Start()
    {
        var port = _config.Port;
        var location = $"ws://0.0.0.0:{port}";

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
            clients = _clients.Values.ToArray();
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

    public void Broadcast(string message)
    {
        if (_disposed || _stopped)
            return;

        foreach (var (id, client) in _clients)
        {
            try
            {
                if (client.IsAvailable && !_stopped && !_disposed)
                {
                    client.Send(message);
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
        bool reject;
        lock (_lifecycleGate)
        {
            reject = _disposed || _stopped;
            if (!reject)
                _clients[socket.ConnectionInfo.Id] = socket;
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

        SendHandshake(socket);
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

        _logger.LogDebug(
            $"Received message from {socket.ConnectionInfo.ClientIpAddress}: {message}"
        );
    }

    private void SendHandshake(IWebSocketConnection socket)
    {
        var zone = GetCurrentZone();
        var capabilities = _config.GetCapabilities();
        var handshake = HandshakeMessage.Create(zone, capabilities);
        var json = MessageSerializer.Serialize(handshake);

        try
        {
            if (!_disposed && !_stopped)
                socket.Send(json);
        }
        catch (Exception ex)
        {
            _logger.LogWarning($"Failed to send handshake: {ex.Message}");
        }
    }

    private static string GetCurrentZone()
    {
        try
        {
            return SceneManager.GetActiveScene().name;
        }
        catch
        {
            return "";
        }
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
