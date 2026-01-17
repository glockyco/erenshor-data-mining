using InteractiveMapCompanion.Entities;

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

/// <summary>
/// Periodic state update containing all tracked entities.
/// </summary>
public record StateUpdateMessage(
    string Type,
    string Zone,
    long Timestamp,
    EntityData[] Entities
)
{
    public static StateUpdateMessage Create(string zone, EntityData[] entities) =>
        new(
            Type: "stateUpdate",
            Zone: zone,
            Timestamp: DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(),
            Entities: entities
        );
}

/// <summary>
/// Notification sent when the player changes zones.
/// Clients should clear entities from the previous zone.
/// </summary>
public record ZoneChangeMessage(
    string Type,
    string PreviousZone,
    string Zone,
    long Timestamp
)
{
    public static ZoneChangeMessage Create(string previousZone, string zone) =>
        new(
            Type: "zoneChange",
            PreviousZone: previousZone,
            Zone: zone,
            Timestamp: DateTimeOffset.UtcNow.ToUnixTimeMilliseconds()
        );
}
