namespace InteractiveMapCompanion.Server;

/// <summary>
/// WebSocket server for broadcasting game state to connected clients.
/// </summary>
public interface IWebSocketServer : IDisposable
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
    /// Broadcasts a message to all connected clients.
    /// </summary>
    void Broadcast(string message);

    /// <summary>
    /// Number of currently connected clients.
    /// </summary>
    int ClientCount { get; }
}
