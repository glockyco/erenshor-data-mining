namespace InteractiveMapCompanion.Server;

/// <summary>
/// Something the broadcast loop sends protocol messages to: the local WebSocket server,
/// sharing with other devices, or both.
/// </summary>
public interface IBroadcastTarget
{
    /// <summary>
    /// Number of clients currently receiving broadcasts.
    /// </summary>
    int ClientCount { get; }

    /// <summary>
    /// Sends a message to every connected client.
    /// </summary>
    void Broadcast(string message);
}
