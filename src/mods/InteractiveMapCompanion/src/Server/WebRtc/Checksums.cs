namespace InteractiveMapCompanion.Server.WebRtc;

/// <summary>
/// Table-driven CRC-32 (STUN FINGERPRINT, RFC 5389) and CRC-32C (SCTP, RFC 4960).
/// </summary>
internal static class Checksums
{
    private static readonly uint[] Crc32Table = BuildTable(0xEDB88320u);
    private static readonly uint[] Crc32cTable = BuildTable(0x82F63B78u);

    public static uint Crc32(byte[] data, int offset, int count) =>
        Compute(Crc32Table, data, offset, count);

    public static uint Crc32c(byte[] data, int offset, int count) =>
        Compute(Crc32cTable, data, offset, count);

    private static uint Compute(uint[] table, byte[] data, int offset, int count)
    {
        uint crc = 0xFFFFFFFFu;
        int end = offset + count;
        for (int i = offset; i < end; i++)
            crc = table[(crc ^ data[i]) & 0xFF] ^ (crc >> 8);
        return ~crc;
    }

    private static uint[] BuildTable(uint reflectedPolynomial)
    {
        var table = new uint[256];
        for (uint n = 0; n < 256; n++)
        {
            uint c = n;
            for (int k = 0; k < 8; k++)
                c = (c & 1) != 0 ? reflectedPolynomial ^ (c >> 1) : c >> 1;
            table[n] = c;
        }
        return table;
    }
}
