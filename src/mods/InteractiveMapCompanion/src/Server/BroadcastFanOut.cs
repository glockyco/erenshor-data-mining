namespace InteractiveMapCompanion.Server;

/// <summary>
/// Sends each broadcast to every target that carries the live map: the WebSocket for
/// this PC and sharing for other devices.
/// </summary>
public sealed class BroadcastFanOut(params IBroadcastTarget[] targets) : IBroadcastTarget
{
    public int ClientCount => targets.Sum(target => target.ClientCount);

    public void Broadcast(string message)
    {
        foreach (var target in targets)
        {
            if (target.ClientCount > 0)
                target.Broadcast(message);
        }
    }
}
