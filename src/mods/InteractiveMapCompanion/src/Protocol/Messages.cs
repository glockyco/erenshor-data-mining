using InteractiveMapCompanion.Entities;

namespace InteractiveMapCompanion.Protocol;

/// <summary>
/// Message sent to clients immediately upon WebSocket connection.
/// </summary>
public sealed class HandshakeMessage
{
    public string Type { get; }
    public string ProtocolVersion { get; }
    public string ModVersion { get; }
    public string Zone { get; }
    public string[] Capabilities { get; }

    public HandshakeMessage(
        string Type,
        string ProtocolVersion,
        string ModVersion,
        string Zone,
        string[] Capabilities
    )
    {
        this.Type = Type;
        this.ProtocolVersion = ProtocolVersion;
        this.ModVersion = ModVersion;
        this.Zone = Zone;
        this.Capabilities = Capabilities;
    }

    public static HandshakeMessage Create(string zone, string[] capabilities) =>
        new HandshakeMessage(
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
public sealed class StateUpdateMessage
{
    public string Type { get; }
    public string Zone { get; }
    public long Timestamp { get; }
    public EntityData[] Entities { get; }

    public StateUpdateMessage(string Type, string Zone, long Timestamp, EntityData[] Entities)
    {
        this.Type = Type;
        this.Zone = Zone;
        this.Timestamp = Timestamp;
        this.Entities = Entities;
    }

    public static StateUpdateMessage Create(string zone, EntityData[] entities) =>
        new StateUpdateMessage(
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
public sealed class ZoneChangeMessage
{
    public string Type { get; }
    public string PreviousZone { get; }
    public string Zone { get; }
    public long Timestamp { get; }

    public ZoneChangeMessage(string Type, string PreviousZone, string Zone, long Timestamp)
    {
        this.Type = Type;
        this.PreviousZone = PreviousZone;
        this.Zone = Zone;
        this.Timestamp = Timestamp;
    }

    public static ZoneChangeMessage Create(string previousZone, string zone) =>
        new ZoneChangeMessage(
            Type: "zoneChange",
            PreviousZone: previousZone,
            Zone: zone,
            Timestamp: DateTimeOffset.UtcNow.ToUnixTimeMilliseconds()
        );
}
