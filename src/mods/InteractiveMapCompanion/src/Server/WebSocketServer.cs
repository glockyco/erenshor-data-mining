using System.Collections.Concurrent;
using BepInEx.Logging;
using Fleck;
using InteractiveMapCompanion.Config;
using InteractiveMapCompanion.Protocol;
using UnityEngine.SceneManagement;

namespace InteractiveMapCompanion.Server;

/// <summary>
/// Fleck-based WebSocket server implementation.
/// Handles client connections and broadcasts messages to all connected clients.
/// </summary>
public class WebSocketServer : IWebSocketServer
{
    private readonly ModConfig _config;
    private readonly ManualLogSource _logger;
    private readonly ConcurrentDictionary<Guid, IWebSocketConnection> _clients = new();

    private Fleck.WebSocketServer? _server;
    private bool _disposed;

    public int ClientCount => _clients.Count;

    public WebSocketServer(ModConfig config, ManualLogSource logger)
    {
        _config = config;
        _logger = logger;

        ConfigureFleckLogging();
    }

    public void Start()
    {
        var port = _config.Port.Value;
        var location = $"ws://0.0.0.0:{port}";

        try
        {
            _server = new Fleck.WebSocketServer(location);
            _server.Start(ConfigureSocket);
            _logger.LogInfo($"WebSocket server started on {location}");
        }
        catch (Exception ex)
        {
            _logger.LogError($"Failed to start WebSocket server on port {port}: {ex.Message}");
            _logger.LogDebug(ex.ToString());
        }
    }

    public void Stop()
    {
        if (_server == null)
            return;

        foreach (var client in _clients.Values)
        {
            try
            {
                client.Close();
            }
            catch
            {
                // Ignore errors during shutdown
            }
        }

        _clients.Clear();
        _server.Dispose();
        _server = null;

        _logger.LogInfo("WebSocket server stopped");
    }

    public void Broadcast(string message)
    {
        foreach (var (id, client) in _clients)
        {
            try
            {
                if (client.IsAvailable)
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
        if (_disposed)
            return;

        Stop();
        _disposed = true;
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
        _clients[socket.ConnectionInfo.Id] = socket;
        _logger.LogInfo(
            $"Client connected: {socket.ConnectionInfo.ClientIpAddress} (total: {ClientCount})"
        );

        SendHandshake(socket);
    }

    private void OnClientDisconnected(IWebSocketConnection socket)
    {
        _clients.TryRemove(socket.ConnectionInfo.Id, out _);
        _logger.LogInfo(
            $"Client disconnected: {socket.ConnectionInfo.ClientIpAddress} (total: {ClientCount})"
        );
    }

    private void OnClientError(IWebSocketConnection socket, Exception ex)
    {
        _logger.LogWarning($"Client error ({socket.ConnectionInfo.ClientIpAddress}): {ex.Message}");
        _clients.TryRemove(socket.ConnectionInfo.Id, out _);
    }

    private void OnClientMessage(IWebSocketConnection socket, string message)
    {
        // Inbound message handling will be implemented in the bidirectional milestone.
        // For now, just log that we received something.
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
        FleckLog.LogAction = (level, message, ex) =>
        {
            // Convert Fleck log level to our config level and check if we should log
            var configuredLevel = _config.WebSocketLogLevel.Value;

            bool shouldLog = level switch
            {
                Fleck.LogLevel.Debug => configuredLevel == InteractiveMapCompanion.Config.LogLevel.Debug,
                Fleck.LogLevel.Info =>
                    configuredLevel == InteractiveMapCompanion.Config.LogLevel.Debug
                    || configuredLevel == InteractiveMapCompanion.Config.LogLevel.Info,
                Fleck.LogLevel.Warn =>
                    configuredLevel == InteractiveMapCompanion.Config.LogLevel.Debug
                    || configuredLevel == InteractiveMapCompanion.Config.LogLevel.Info
                    || configuredLevel == InteractiveMapCompanion.Config.LogLevel.Warning,
                Fleck.LogLevel.Error => true, // Always log errors
                _ => false
            };

            if (!shouldLog)
                return;

            // Log to appropriate BepInEx level
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
    }
}
