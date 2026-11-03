using InteractiveMapCompanion.Server.WebRtc;
using Xunit;

namespace InteractiveMapCompanion.Tests.Server;

public class SharingIdentityTests
{
    [Fact]
    public void RestoresTheCredentialsAPairedDeviceUses()
    {
        var created = SharingIdentity.Create();

        var restored = SharingIdentity.Parse(created.Serialize());

        Assert.NotNull(restored);
        Assert.Equal(created.IceUfrag, restored.IceUfrag);
        Assert.Equal(created.IcePassword, restored.IcePassword);
        Assert.Equal(created.FingerprintHex, restored.FingerprintHex);
    }

    [Fact]
    public void StoresOneLineWithoutCharactersThatBreakTheLink()
    {
        string serialized = SharingIdentity.Create().Serialize();

        Assert.DoesNotContain('\n', serialized);
        Assert.Matches("^[0-9a-f]{64}$", SharingIdentity.Parse(serialized)!.FingerprintHex);
    }

    [Theory]
    [InlineData(null)]
    [InlineData("")]
    [InlineData("not an identity")]
    [InlineData("2.ufrag.password.AAAA.AAAA")]
    [InlineData("1.ufrag.password.AAAA.AAAA")]
    [InlineData("1.ufrag.password.!!!!.AAAA")]
    public void RejectsValuesItCannotUse(string? value)
    {
        Assert.Null(SharingIdentity.Parse(value));
    }

    [Fact]
    public void RejectsAKeyThatDoesNotBelongToTheCertificate()
    {
        string[] first = SharingIdentity.Create().Serialize().Split('.');
        string[] second = SharingIdentity.Create().Serialize().Split('.');
        first[4] = second[4];

        Assert.Null(SharingIdentity.Parse(string.Join(".", first)));
    }

    [Fact]
    public void RejectsCredentialsThatCouldNotAppearInALink()
    {
        string[] parts = SharingIdentity.Create().Serialize().Split('.');
        parts[2] = "pass#word";

        Assert.Null(SharingIdentity.Parse(string.Join(".", parts)));
    }
}
