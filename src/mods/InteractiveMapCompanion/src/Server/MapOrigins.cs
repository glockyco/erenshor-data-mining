namespace InteractiveMapCompanion.Server;

/// <summary>
/// Decides which pages on this PC may see and change sharing. Any web page the player
/// opens can connect to the loopback WebSocket, so only the map itself, or a map dev
/// server on this PC, receives the pairing link and may turn sharing on.
/// </summary>
public static class MapOrigins
{
    private static readonly Uri Map = new(MapSite.MapUrl);

    /// <summary>
    /// True for the WebSocket <c>Origin</c> of the published map or of an http dev
    /// server on localhost or 127.0.0.1.
    /// </summary>
    public static bool IsTrusted(string? origin)
    {
        if (string.IsNullOrEmpty(origin) || !Uri.TryCreate(origin, UriKind.Absolute, out var uri))
            return false;

        if (uri.Scheme == Uri.UriSchemeHttps)
            return uri.Host == Map.Host && uri.Port == Map.Port;

        return uri.Scheme == Uri.UriSchemeHttp
            && (uri.Host == "localhost" || uri.Host == "127.0.0.1");
    }
}
