namespace InteractiveMapCompanion.Protocol;

/// <summary>
/// Message sent to clients immediately upon WebSocket connection.
/// </summary>
public record HandshakeMessage(
    string Type,
    string ProtocolVersion,
    string ModVersion,
    string Zone,
    string[] Capabilities
)
{
    public static HandshakeMessage Create(string zone, string[] capabilities) =>
        new(
            Type: "handshake",
            ProtocolVersion: Protocol.ProtocolVersion.Current,
            ModVersion: PluginInfo.Version,
            Zone: zone,
            Capabilities: capabilities
        );
}
