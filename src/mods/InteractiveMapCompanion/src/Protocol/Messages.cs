using InteractiveMapCompanion.Entities;

namespace InteractiveMapCompanion.Protocol;

/// <summary>
/// Message sent to clients immediately upon connection.
/// </summary>
public sealed class HandshakeMessage
{
    public string Type { get; }
    public string ProtocolVersion { get; }
    public string ModVersion { get; }
    public string Zone { get; }
    public string[] Capabilities { get; }

    /// <summary>
    /// Present only for a trusted map on this PC.
    /// </summary>
    public SharingStatus? Sharing { get; }

    public HandshakeMessage(
        string Type,
        string ProtocolVersion,
        string ModVersion,
        string Zone,
        string[] Capabilities,
        SharingStatus? Sharing = null
    )
    {
        this.Type = Type;
        this.ProtocolVersion = ProtocolVersion;
        this.ModVersion = ModVersion;
        this.Zone = Zone;
        this.Capabilities = Capabilities;
        this.Sharing = Sharing;
    }

    public static HandshakeMessage Create(
        string zone,
        string[] capabilities,
        SharingStatus? sharing = null
    ) =>
        new HandshakeMessage(
            Type: "handshake",
            ProtocolVersion: Protocol.ProtocolVersion.Current,
            ModVersion: PluginInfo.Version,
            Zone: zone,
            Capabilities: capabilities,
            Sharing: sharing
        );
}

/// <summary>
/// Whether phones and other PCs on the network can show the live map. Only a trusted
/// map on this PC receives it, because the link pairs any device that opens it.
/// </summary>
public sealed class SharingStatus
{
    public bool Enabled { get; }

    /// <summary>
    /// Devices showing the live map now.
    /// </summary>
    public int Viewers { get; }

    /// <summary>
    /// The UDP and TCP port other devices connect to.
    /// </summary>
    public int Port { get; }

    /// <summary>
    /// The address and port to type on another device, or null when sharing is off or
    /// the PC has no network address.
    /// </summary>
    public string? Address { get; }

    /// <summary>
    /// The pairing link for <see cref="Address"/>, or null with it.
    /// </summary>
    public string? Link { get; }

    /// <summary>
    /// Why sharing could not start, <c>portUnavailable</c>, or null.
    /// </summary>
    public string? Error { get; }

    public SharingStatus(
        bool Enabled,
        int Viewers,
        int Port,
        string? Address,
        string? Link,
        string? Error
    )
    {
        this.Enabled = Enabled;
        this.Viewers = Viewers;
        this.Port = Port;
        this.Address = Address;
        this.Link = Link;
        this.Error = Error;
    }
}

/// <summary>
/// Sent to trusted maps on this PC when sharing starts, stops or fails, and when a
/// device connects or leaves.
/// </summary>
public sealed class SharingChangedMessage
{
    public string Type { get; }
    public SharingStatus Sharing { get; }

    public SharingChangedMessage(string Type, SharingStatus Sharing)
    {
        this.Type = Type;
        this.Sharing = Sharing;
    }

    public static SharingChangedMessage Create(SharingStatus sharing) =>
        new SharingChangedMessage(Type: "sharingChanged", Sharing: sharing);
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
