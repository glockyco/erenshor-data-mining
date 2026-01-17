using InteractiveMapCompanion.Config;
using InteractiveMapCompanion.Entities;
using InteractiveMapCompanion.Protocol;
using InteractiveMapCompanion.Server;

namespace InteractiveMapCompanion.State;

/// <summary>
/// Manages periodic state broadcasts to connected WebSocket clients.
/// Handles timing, state gathering, and zone change notifications.
/// </summary>
public sealed class BroadcastLoop : IBroadcastLoop
{
    private readonly IEntityTracker _entityTracker;
    private readonly IWebSocketServer _server;
    private readonly ModConfig _config;
    private readonly Action<string>? _log;

    private float _elapsed;
    private string _currentZone = "";

    /// <summary>
    /// Creates a new BroadcastLoop.
    /// </summary>
    /// <param name="entityTracker">Tracks entities in the current scene.</param>
    /// <param name="server">WebSocket server for broadcasting.</param>
    /// <param name="config">Configuration for update interval.</param>
    /// <param name="log">Optional logging callback.</param>
    public BroadcastLoop(
        IEntityTracker entityTracker,
        IWebSocketServer server,
        ModConfig config,
        Action<string>? log = null)
    {
        _entityTracker = entityTracker;
        _server = server;
        _config = config;
        _log = log;
    }

    /// <inheritdoc />
    public void Tick(float deltaTime)
    {
        _elapsed += deltaTime;

        // Convert interval from milliseconds to seconds
        var intervalSeconds = _config.UpdateInterval.Value / 1000f;
        if (_elapsed < intervalSeconds)
            return;

        _elapsed = 0f;
        BroadcastState();
    }

    /// <inheritdoc />
    public void OnSceneLoaded(string newZone)
    {
        var previousZone = _currentZone;
        _currentZone = newZone;

        // Only send zone change if we had a previous zone (not initial load)
        if (!string.IsNullOrEmpty(previousZone) && previousZone != newZone)
        {
            SendZoneChange(previousZone, newZone);
        }

        // Immediately broadcast state for the new zone
        BroadcastState();
    }

    private void BroadcastState()
    {
        // Skip if no clients connected
        if (_server.ClientCount == 0)
            return;

        try
        {
            var entities = _entityTracker.GetTrackedEntities();
            var message = StateUpdateMessage.Create(_currentZone, entities.ToArray());
            var json = MessageSerializer.Serialize(message);
            _server.Broadcast(json);
        }
        catch (Exception ex)
        {
            _log?.Invoke($"Error broadcasting state: {ex.Message}");
        }
    }

    private void SendZoneChange(string previousZone, string newZone)
    {
        // Skip if no clients connected
        if (_server.ClientCount == 0)
            return;

        try
        {
            var message = ZoneChangeMessage.Create(previousZone, newZone);
            var json = MessageSerializer.Serialize(message);
            _server.Broadcast(json);
            _log?.Invoke($"Zone changed: {previousZone} -> {newZone}");
        }
        catch (Exception ex)
        {
            _log?.Invoke($"Error sending zone change: {ex.Message}");
        }
    }
}
