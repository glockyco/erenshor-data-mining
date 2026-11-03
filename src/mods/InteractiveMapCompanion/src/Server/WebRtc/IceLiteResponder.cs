using System.Net;
using System.Security.Cryptography;
using System.Text;

namespace InteractiveMapCompanion.Server.WebRtc;

/// <summary>
/// Answers ICE connectivity checks as an ICE-lite agent (RFC 8445). The browser learns
/// this agent's credentials from the pairing link, so a check is accepted when its
/// USERNAME starts with the local fragment and its MESSAGE-INTEGRITY matches the local
/// password. The browser's own fragment is never needed, which lets pairing be one-way.
/// </summary>
internal sealed class IceLiteResponder
{
    private const uint MagicCookie = 0x2112A442;
    private const ushort BindingRequest = 0x0001;
    private const ushort BindingSuccess = 0x0101;
    private const ushort AttrUsername = 0x0006;
    private const ushort AttrMessageIntegrity = 0x0008;
    private const ushort AttrXorMappedAddress = 0x0020;
    private const ushort AttrFingerprint = 0x8028;
    private const uint FingerprintXor = 0x5354554E;

    private readonly string _usernamePrefix;
    private readonly byte[] _password;

    public IceLiteResponder(string localUfrag, string localPassword)
    {
        _usernamePrefix = localUfrag + ":";
        _password = Encoding.UTF8.GetBytes(localPassword);
    }

    /// <summary>
    /// True when the datagram has a STUN header (first two bits zero and the magic cookie).
    /// </summary>
    public static bool IsStun(byte[] buffer, int length) =>
        length >= 20 && buffer[0] < 2 && ReadUInt32(buffer, 4) == MagicCookie;

    /// <summary>
    /// Returns the success response for a valid binding request, or null when the request
    /// is not for this agent or fails its integrity check.
    /// </summary>
    public byte[]? Respond(byte[] buffer, int length, IPEndPoint remote)
    {
        if (length < 20 || ReadUInt16(buffer, 0) != BindingRequest)
            return null;

        int end = 20 + ReadUInt16(buffer, 2);
        if (end > length)
            return null;

        string? username = null;
        int integrityOffset = -1;
        int position = 20;
        while (position + 4 <= end)
        {
            ushort type = ReadUInt16(buffer, position);
            ushort valueLength = ReadUInt16(buffer, position + 2);
            int valueStart = position + 4;
            if (valueStart + valueLength > end)
                return null;

            if (type == AttrUsername)
                username = Encoding.UTF8.GetString(buffer, valueStart, valueLength);
            else if (type == AttrMessageIntegrity)
            {
                integrityOffset = position;
                break;
            }

            position = valueStart + ((valueLength + 3) & ~3);
        }

        if (
            username == null
            || !username.StartsWith(_usernamePrefix, StringComparison.Ordinal)
            || integrityOffset < 0
            || integrityOffset + 24 > end
        )
            return null;

        // The HMAC covers everything before MESSAGE-INTEGRITY, with the header length
        // rewritten to end just after the MESSAGE-INTEGRITY attribute (RFC 5389 15.4).
        var signed = new byte[integrityOffset];
        Buffer.BlockCopy(buffer, 0, signed, 0, integrityOffset);
        WriteUInt16(signed, 2, (ushort)(integrityOffset + 24 - 20));
        byte[] expected;
        using (var hmac = new HMACSHA1(_password))
            expected = hmac.ComputeHash(signed);

        int diff = 0;
        for (int i = 0; i < 20; i++)
            diff |= expected[i] ^ buffer[integrityOffset + 4 + i];
        if (diff != 0)
            return null;

        return BuildSuccess(buffer, remote);
    }

    private byte[] BuildSuccess(byte[] request, IPEndPoint remote)
    {
        var message = new byte[20 + 12 + 24 + 8];
        WriteUInt16(message, 0, BindingSuccess);
        WriteUInt32(message, 4, MagicCookie);
        Buffer.BlockCopy(request, 8, message, 8, 12);

        int position = 20;
        WriteUInt16(message, position, AttrXorMappedAddress);
        WriteUInt16(message, position + 2, 8);
        message[position + 5] = 0x01;
        WriteUInt16(message, position + 6, (ushort)(remote.Port ^ (int)(MagicCookie >> 16)));
        byte[] address = remote.Address.MapToIPv4().GetAddressBytes();
        for (int i = 0; i < 4; i++)
            message[position + 8 + i] = (byte)(address[i] ^ (byte)(MagicCookie >> (24 - 8 * i)));
        position += 12;

        WriteUInt16(message, 2, (ushort)(position + 24 - 20));
        byte[] mac;
        using (var hmac = new HMACSHA1(_password))
            mac = hmac.ComputeHash(message, 0, position);
        WriteUInt16(message, position, AttrMessageIntegrity);
        WriteUInt16(message, position + 2, 20);
        Buffer.BlockCopy(mac, 0, message, position + 4, 20);
        position += 24;

        WriteUInt16(message, 2, (ushort)(position + 8 - 20));
        uint crc = Checksums.Crc32(message, 0, position) ^ FingerprintXor;
        WriteUInt16(message, position, AttrFingerprint);
        WriteUInt16(message, position + 2, 4);
        WriteUInt32(message, position + 4, crc);
        return message;
    }

    private static ushort ReadUInt16(byte[] b, int o) => (ushort)((b[o] << 8) | b[o + 1]);

    private static uint ReadUInt32(byte[] b, int o) =>
        ((uint)b[o] << 24) | ((uint)b[o + 1] << 16) | ((uint)b[o + 2] << 8) | b[o + 3];

    private static void WriteUInt16(byte[] b, int o, ushort v)
    {
        b[o] = (byte)(v >> 8);
        b[o + 1] = (byte)v;
    }

    private static void WriteUInt32(byte[] b, int o, uint v)
    {
        b[o] = (byte)(v >> 24);
        b[o + 1] = (byte)(v >> 16);
        b[o + 2] = (byte)(v >> 8);
        b[o + 3] = (byte)v;
    }
}
