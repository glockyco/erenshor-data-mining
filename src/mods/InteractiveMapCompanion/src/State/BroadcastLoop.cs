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
    private readonly IBroadcastConfig _config;
    private readonly Action<string>? _log;

    private float _elapsed;
    private string _currentZone = "";
    private bool _stopped;

    public BroadcastLoop(
        IEntityTracker entityTracker,
        IWebSocketServer server,
        IBroadcastConfig config,
        Action<string>? log = null
    )
    {
        _entityTracker = entityTracker;
        _server = server;
        _config = config;
        _log = log;
    }

    public void Tick(float deltaTime)
    {
        if (_stopped)
            return;

        _elapsed += deltaTime;

        var intervalSeconds = _config.UpdateInterval / 1000f;
        if (_elapsed < intervalSeconds)
            return;

        _elapsed = 0f;
        BroadcastState();
    }

    public void OnSceneLoaded(string newZone)
    {
        if (_stopped)
            return;

        var previousZone = _currentZone;
        _currentZone = newZone;

        if (!string.IsNullOrEmpty(previousZone) && previousZone != newZone)
            SendZoneChange(previousZone, newZone);

        BroadcastState();
    }

    public void Stop()
    {
        if (_stopped)
            return;

        _stopped = true;
        _elapsed = 0f;
        _currentZone = "";
    }

    private void BroadcastState()
    {
        if (_stopped || _server.ClientCount == 0)
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
        if (_stopped || _server.ClientCount == 0)
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
