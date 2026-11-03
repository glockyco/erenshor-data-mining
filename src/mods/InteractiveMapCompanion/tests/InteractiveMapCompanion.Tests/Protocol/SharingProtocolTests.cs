using InteractiveMapCompanion.Protocol;
using InteractiveMapCompanion.Server;
using Newtonsoft.Json.Linq;
using Xunit;

namespace InteractiveMapCompanion.Tests.Protocol;

public class SharingProtocolTests
{
    private static readonly SharingStatus Sharing = new(
        Enabled: true,
        Viewers: 2,
        Port: 18586,
        Address: "192.168.0.10:18586",
        Link: "https://erenshor.compendiums.org/map#live=192.168.0.10:18586.u.p.ff",
        Error: null
    );

    [Fact]
    public void TrustedHandshakeCarriesTheSharingStatus()
    {
        var payload = JObject.Parse(
            MessageSerializer.Serialize(HandshakeMessage.Create("Zone", ["entities"], Sharing))
        );

        var sharing = Assert.IsType<JObject>(payload["sharing"]);
        Assert.True(sharing["enabled"]!.Value<bool>());
        Assert.Equal(2, sharing["viewers"]!.Value<int>());
        Assert.Equal(18586, sharing["port"]!.Value<int>());
        Assert.Equal("192.168.0.10:18586", sharing["address"]!.Value<string>());
        Assert.Equal(Sharing.Link, sharing["link"]!.Value<string>());
        Assert.False(sharing.ContainsKey("error"));
    }

    [Fact]
    public void HandshakeWithoutSharingLeavesTheFieldOut()
    {
        var payload = JObject.Parse(
            MessageSerializer.Serialize(HandshakeMessage.Create("Zone", ["entities"]))
        );

        Assert.False(payload.ContainsKey("sharing"));
    }

    [Fact]
    public void SharingChangedCarriesAFailedStart()
    {
        var failed = new SharingStatus(false, 0, 18586, null, null, "portUnavailable");

        var payload = JObject.Parse(
            MessageSerializer.Serialize(SharingChangedMessage.Create(failed))
        );

        Assert.Equal("sharingChanged", payload["type"]!.Value<string>());
        var sharing = Assert.IsType<JObject>(payload["sharing"]);
        Assert.False(sharing["enabled"]!.Value<bool>());
        Assert.Equal("portUnavailable", sharing["error"]!.Value<string>());
        Assert.False(sharing.ContainsKey("link"));
        Assert.False(sharing.ContainsKey("address"));
    }

    [Theory]
    [InlineData("""{"type":"setSharing","enabled":true}""", true)]
    [InlineData("""{"enabled":false,"type":"setSharing"}""", false)]
    public void ReadsASetSharingRequest(string json, bool expected)
    {
        Assert.True(ClientMessages.TryReadSetSharing(json, out bool enabled));
        Assert.Equal(expected, enabled);
    }

    [Theory]
    [InlineData("""{"type":"setSharing","enabled":"true"}""")]
    [InlineData("""{"type":"setSharing","enabled":1}""")]
    [InlineData("""{"type":"setSharing"}""")]
    [InlineData("""{"type":"setsharing","enabled":true}""")]
    [InlineData("""{"type":"stateUpdate","enabled":true}""")]
    [InlineData("""["setSharing",true]""")]
    [InlineData("not json")]
    [InlineData("")]
    public void IgnoresAnythingElse(string json)
    {
        Assert.False(ClientMessages.TryReadSetSharing(json, out _));
    }

    [Theory]
    [InlineData("https://erenshor.compendiums.org", true)]
    [InlineData("http://localhost:5173", true)]
    [InlineData("http://127.0.0.1:4173", true)]
    [InlineData("http://erenshor.compendiums.org", false)]
    [InlineData("https://erenshor.compendiums.org:8443", false)]
    [InlineData("https://erenshor.compendiums.org.example.com", false)]
    [InlineData("https://example.com", false)]
    [InlineData("http://localhost.example.com", false)]
    [InlineData("https://localhost:5173", false)]
    [InlineData("null", false)]
    [InlineData("", false)]
    [InlineData(null, false)]
    public void OnlyTheMapMaySeeAndChangeSharing(string? origin, bool trusted)
    {
        Assert.Equal(trusted, MapOrigins.IsTrusted(origin));
    }
}
