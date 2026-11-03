namespace InteractiveMapCompanion.Server;

/// <summary>
/// Sends each broadcast to every transport that carries the live map: the local
/// WebSocket for this PC and WebRTC for other devices.
/// </summary>
public sealed class BroadcastFanOut(params IWebSocketServer[] servers) : IWebSocketServer
{
    public int ClientCount => servers.Sum(server => server.ClientCount);

    public void Start()
    {
        foreach (var server in servers)
            server.Start();
    }

    public void Stop()
    {
        foreach (var server in servers)
            server.Stop();
    }

    public void Broadcast(string message)
    {
        foreach (var server in servers)
        {
            if (server.ClientCount > 0)
                server.Broadcast(message);
        }
    }

    public void Dispose()
    {
        foreach (var server in servers)
            server.Dispose();
    }
}
