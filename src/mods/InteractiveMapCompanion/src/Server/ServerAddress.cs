namespace InteractiveMapCompanion.Server;

internal static class ServerAddress
{
    internal static string GetLocation(int port, bool allowLanConnections)
    {
        var address = allowLanConnections ? "0.0.0.0" : "127.0.0.1";
        return $"ws://{address}:{port}";
    }
}
