using InteractiveMapCompanion.Entities;
using InteractiveMapCompanion.Protocol;
using Newtonsoft.Json.Linq;
using Xunit;

namespace InteractiveMapCompanion.Tests.Protocol;

public class MessageSerializerTests
{
    [Fact]
    public void Serialize_HandshakeMessage_UsesCamelCase()
    {
        var message = HandshakeMessage.Create(
            zone: "StowawayStrand",
            capabilities: ["entities", "spawns"]
        );

        var json = MessageSerializer.Serialize(message);

        var payload = JObject.Parse(json);

        Assert.NotNull(payload["type"]);
        Assert.NotNull(payload["protocolVersion"]);
        Assert.NotNull(payload["modVersion"]);
        Assert.NotNull(payload["zone"]);
        Assert.NotNull(payload["capabilities"]);
        Assert.Null(payload["Type"]);
    }

    [Fact]
    public void Serialize_HandshakeMessage_ContainsCorrectValues()
    {
        var message = HandshakeMessage.Create(
            zone: "TestZone",
            capabilities: ["entities", "markers"]
        );

        var json = MessageSerializer.Serialize(message);

        var payload = JObject.Parse(json);
        var capabilities = Assert.IsType<JArray>(payload["capabilities"]);

        Assert.Equal("handshake", payload["type"]?.Value<string>());
        Assert.Equal("TestZone", payload["zone"]?.Value<string>());
        Assert.Equal(ProtocolVersion.Current, payload["protocolVersion"]?.Value<string>());
        Assert.Equal(new[] { "entities", "markers" }, capabilities.Values<string>());
    }

    [Fact]
    public void Serialize_StateUpdateMessage_OmitsNullOptionalEntityFields()
    {
        var entity = new EntityData(
            Id: 7,
            EntityType: "npc",
            Name: "Test NPC",
            Position: [1f, 2f, 3f],
            Rotation: 90f
        );
        var message = new StateUpdateMessage(
            Type: "stateUpdate",
            Zone: "TestZone",
            Timestamp: 123L,
            Entities: [entity]
        );

        var payload = JObject.Parse(MessageSerializer.Serialize(message));
        var entities = Assert.IsType<JArray>(payload["entities"]);
        var serializedEntity = Assert.IsType<JObject>(entities[0]);

        Assert.False(serializedEntity.ContainsKey("level"));
        Assert.False(serializedEntity.ContainsKey("rarity"));
        Assert.False(serializedEntity.ContainsKey("characterClass"));
        Assert.False(serializedEntity.ContainsKey("owner"));
        Assert.Equal("npc", serializedEntity["entityType"]?.Value<string>());
    }

    [Fact]
    public void Serialize_HandshakeMessage_IsCompact()
    {
        var message = HandshakeMessage.Create(zone: "Zone", capabilities: ["entities"]);

        var json = MessageSerializer.Serialize(message);

        // Should not contain newlines (not indented)
        Assert.DoesNotContain("\n", json);
    }

    [Fact]
    public void Serialize_HandshakeMessage_RoundTrips()
    {
        var original = HandshakeMessage.Create(
            zone: "TestZone",
            capabilities: ["entities", "spawns", "bidirectional"]
        );

        var json = MessageSerializer.Serialize(original);
        var deserialized = MessageSerializer.Deserialize<HandshakeMessage>(json);

        Assert.NotNull(deserialized);
        Assert.Equal(original.Type, deserialized.Type);
        Assert.Equal(original.ProtocolVersion, deserialized.ProtocolVersion);
        Assert.Equal(original.Zone, deserialized.Zone);
        Assert.Equal(original.Capabilities, deserialized.Capabilities);
    }
}
