using InteractiveMapCompanion.Protocol;
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

        Assert.Contains("\"type\":", json);
        Assert.Contains("\"protocolVersion\":", json);
        Assert.Contains("\"modVersion\":", json);
        Assert.Contains("\"zone\":", json);
        Assert.Contains("\"capabilities\":", json);
    }

    [Fact]
    public void Serialize_HandshakeMessage_ContainsCorrectValues()
    {
        var message = HandshakeMessage.Create(
            zone: "TestZone",
            capabilities: ["entities", "markers"]
        );

        var json = MessageSerializer.Serialize(message);

        Assert.Contains("\"type\":\"handshake\"", json);
        Assert.Contains("\"zone\":\"TestZone\"", json);
        Assert.Contains($"\"protocolVersion\":\"{ProtocolVersion.Current}\"", json);
        Assert.Contains("\"entities\"", json);
        Assert.Contains("\"markers\"", json);
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
