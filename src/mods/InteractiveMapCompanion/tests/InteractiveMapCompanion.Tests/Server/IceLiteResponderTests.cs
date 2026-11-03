using System.Net;
using System.Security.Cryptography;
using System.Text;
using InteractiveMapCompanion.Server.WebRtc;
using Xunit;

namespace InteractiveMapCompanion.Tests.Server;

public class IceLiteResponderTests
{
    // RFC 5769 section 2.1: a binding request from "evtj:h6vY", signed with
    // MESSAGE-INTEGRITY and FINGERPRINT. The password is the RFC's published test value.
    private static readonly byte[] SampleRequest = Convert.FromHexString(
        "000100582112a442b7e7a701bc34d686fa87dfae802200105354554e20746573"
            + "7420636c69656e74002400046e0001ff80290008932ff9b151263b3600060009"
            + "6576746a3a68367659202020000800149aeaa70cbfd8cb56781ef2b5b2d3f249"
            + "c1b571a280280004e57a3bcf"
    );

    private const string SampleUfrag = "evtj";
    private const string SamplePassword = "VOkJxbRl1RmTxUk/WvJxBt"; // gitleaks:allow
    private static readonly IPEndPoint Browser = new(IPAddress.Parse("192.0.2.1"), 32853);

    [Fact]
    public void AnswersACheckSignedWithTheLocalCredentials()
    {
        var responder = new IceLiteResponder(SampleUfrag, SamplePassword);

        byte[]? response = responder.Respond(SampleRequest, SampleRequest.Length, Browser);

        Assert.NotNull(response);
        Assert.Equal(0x0101, ReadUInt16(response, 0));
        Assert.Equal(SampleRequest[8..20], response[8..20]);
        Assert.Equal(20 + ReadUInt16(response, 2), response.Length);
    }

    [Fact]
    public void ResponseTellsTheBrowserItsAddressAndIsSigned()
    {
        var responder = new IceLiteResponder(SampleUfrag, SamplePassword);

        byte[] response = responder.Respond(SampleRequest, SampleRequest.Length, Browser)!;

        var attributes = ReadAttributes(response);
        byte[] mapped = response.AsSpan(attributes[0x0020], 8).ToArray();
        Assert.Equal(0x01, mapped[1]);
        Assert.Equal(Browser.Port, ReadUInt16(mapped, 2) ^ 0x2112);
        byte[] cookie = [0x21, 0x12, 0xA4, 0x42];
        var address = new IPAddress(mapped[4..8].Select((b, i) => (byte)(b ^ cookie[i])).ToArray());
        Assert.Equal(Browser.Address, address);

        int integrity = attributes[0x0008] - 4;
        byte[] signed = response[..integrity];
        signed[2] = 0;
        signed[3] = (byte)(integrity + 24 - 20);
        byte[] mac = HMACSHA1.HashData(Encoding.UTF8.GetBytes(SamplePassword), signed);
        Assert.Equal(mac, response.AsSpan(integrity + 4, 20).ToArray());

        int fingerprint = attributes[0x8028] - 4;
        uint expected = Checksums.Crc32(response, 0, fingerprint) ^ 0x5354554E;
        Assert.Equal(expected, ReadUInt32(response, fingerprint + 4));
    }

    [Fact]
    public void IgnoresACheckForAnotherUsernameFragment()
    {
        var responder = new IceLiteResponder("evtX", SamplePassword);

        Assert.Null(responder.Respond(SampleRequest, SampleRequest.Length, Browser));
    }

    [Fact]
    public void IgnoresACheckSignedWithAnotherPassword()
    {
        var responder = new IceLiteResponder(SampleUfrag, "VOkJxbRl1RmTxUk/WvJxBu");

        Assert.Null(responder.Respond(SampleRequest, SampleRequest.Length, Browser));
    }

    [Fact]
    public void IgnoresACheckAlteredAfterSigning()
    {
        var responder = new IceLiteResponder(SampleUfrag, SamplePassword);
        byte[] tampered = (byte[])SampleRequest.Clone();
        tampered[47] ^= 0x01; // Last byte of the PRIORITY value.

        Assert.Null(responder.Respond(tampered, tampered.Length, Browser));
    }

    [Fact]
    public void Crc32MatchesTheSampleRequestFingerprint()
    {
        int fingerprint = SampleRequest.Length - 8;

        uint value = Checksums.Crc32(SampleRequest, 0, fingerprint) ^ 0x5354554E;

        Assert.Equal(ReadUInt32(SampleRequest, fingerprint + 4), value);
    }

    [Fact]
    public void Crc32cMatchesTheStandardCheckValue()
    {
        byte[] data = Encoding.ASCII.GetBytes("123456789");

        Assert.Equal(0xE3069283u, Checksums.Crc32c(data, 0, data.Length));
    }

    /// <summary>
    /// Maps each attribute type to the offset of its value.
    /// </summary>
    private static Dictionary<int, int> ReadAttributes(byte[] message)
    {
        var attributes = new Dictionary<int, int>();
        int position = 20;
        while (position + 4 <= message.Length)
        {
            int length = ReadUInt16(message, position + 2);
            attributes[ReadUInt16(message, position)] = position + 4;
            position += 4 + ((length + 3) & ~3);
        }
        return attributes;
    }

    private static int ReadUInt16(byte[] b, int o) => (b[o] << 8) | b[o + 1];

    private static uint ReadUInt32(byte[] b, int o) =>
        ((uint)b[o] << 24) | ((uint)b[o + 1] << 16) | ((uint)b[o + 2] << 8) | b[o + 3];
}
