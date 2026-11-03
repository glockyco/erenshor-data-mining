namespace InteractiveMapCompanion.Server;

/// <summary>
/// WebSocket server for broadcasting game state to the map on the same PC.
/// </summary>
public interface IWebSocketServer : IBroadcastTarget, IDisposable
{
    /// <summary>
    /// Starts the WebSocket server and begins accepting connections.
    /// </summary>
    void Start();

    /// <summary>
    /// Stops the server and disconnects all clients.
    /// </summary>
    void Stop();

    /// <summary>
    /// Sends a message only to clients whose page is the map (<see cref="MapOrigins"/>).
    /// </summary>
    void BroadcastToTrusted(string message);
}
