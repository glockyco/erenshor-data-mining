using System.Text;
using InteractiveMapCompanion.Server.WebRtc;
using Xunit;

namespace InteractiveMapCompanion.Tests.Server;

public class SctpAssociationTests
{
    private const uint BrowserTag = 0x0A0B0C0D;
    private const uint BrowserInitialTsn = 100;

    [Fact]
    public void CompletesTheHandshakeTheBrowserStarts()
    {
        var harness = new Harness();
        int established = 0;
        harness.Association.Established += () => established++;

        harness.Receive(Chunk(1, 0, InitValue(BrowserTag, 128 * 1024, BrowserInitialTsn)));

        var initAck = Assert.Single(harness.SentChunks());
        Assert.Equal(2, initAck.Type);
        Assert.Equal(BrowserTag, ReadUInt32(harness.Sent[0], 4));
        Assert.NotEqual(0u, ReadUInt32(initAck.Value, 0));
        Assert.False(harness.Association.IsEstablished);

        byte[] cookie = StateCookie(initAck.Value);
        harness.Sent.Clear();
        harness.Receive(Chunk(10, 0, cookie));

        Assert.Equal(11, Assert.Single(harness.SentChunks()).Type);
        Assert.True(harness.Association.IsEstablished);
        Assert.Equal(1, established);
    }

    [Fact]
    public void SignsEveryPacketWithCrc32c()
    {
        var harness = Harness.Established();
        harness.Association.SendText(new string('m', 3000));
        harness.Receive(Chunk(4, 0, [0, 1, 0, 8, 1, 2, 3, 4]));

        Assert.NotEmpty(harness.Sent);
        foreach (byte[] packet in harness.Sent)
        {
            uint stored = BitConverter.ToUInt32(packet, 8);
            byte[] zeroed = (byte[])packet.Clone();
            zeroed[8] = zeroed[9] = zeroed[10] = zeroed[11] = 0;
            Assert.Equal(Checksums.Crc32c(zeroed, 0, zeroed.Length), stored);
        }
    }

    [Fact]
    public void SplitsALongMessageIntoOneOrderedSequenceOfFragments()
    {
        var harness = Harness.Established();
        string text = string.Concat(Enumerable.Range(0, 2500).Select(i => (char)('a' + i % 26)));

        Assert.True(harness.Association.SendText(text));
        Assert.True(harness.Association.SendText("next"));

        var data = harness.SentChunks().Select(DataChunk.From).ToList();
        Assert.Equal(4, data.Count);
        Assert.Equal(new byte[] { 0x02, 0x00, 0x01, 0x03 }, data.Select(d => d.Flags));
        for (int i = 1; i < data.Count; i++)
            Assert.Equal(data[0].Tsn + (uint)i, data[i].Tsn);
        Assert.All(data, d => Assert.Equal(0, d.Stream));
        Assert.All(data, d => Assert.Equal(51u, d.Ppid));
        Assert.All(data.Take(3), d => Assert.Equal(data[0].Sequence, d.Sequence));
        Assert.Equal(data[0].Sequence + 1, data[3].Sequence);
        Assert.Equal(
            text,
            Encoding.UTF8.GetString(data.Take(3).SelectMany(d => d.Payload).ToArray())
        );
    }

    [Fact]
    public void RetransmitsOnlyUnacknowledgedDataOnceTheTimerExpires()
    {
        var harness = Harness.Established();
        harness.Association.SendText("one");
        harness.Association.SendText("two");
        var sent = harness.SentChunks().Select(DataChunk.From).ToList();
        harness.Sent.Clear();

        harness.Receive(Chunk(3, 0, SackValue(sent[0].Tsn, 128 * 1024)));
        harness.Now += TimeSpan.FromMilliseconds(200);
        harness.Association.Tick();
        Assert.Empty(harness.Sent);

        harness.Now += TimeSpan.FromMilliseconds(1000);
        harness.Association.Tick();

        var resent = DataChunk.From(Assert.Single(harness.SentChunks()));
        Assert.Equal(sent[1].Tsn, resent.Tsn);
        Assert.Equal("two", Encoding.UTF8.GetString(resent.Payload));
    }

    [Fact]
    public void HoldsBackAMessageTheBrowserHasNoRoomForUntilItAcknowledges()
    {
        var harness = Harness.Established(window: 2000);
        string message = new('x', 1500);

        Assert.True(harness.Association.SendText(message));
        Assert.False(harness.Association.SendText(message));

        uint tsn = DataChunk.From(harness.SentChunks()[^1]).Tsn;
        harness.Receive(Chunk(3, 0, SackValue(tsn, 2000)));

        Assert.True(harness.Association.SendText(message));
    }

    [Fact]
    public void AcknowledgesBrowserDataUpToTheFirstGap()
    {
        var harness = Harness.Established();

        harness.Receive(Chunk(0, 0x03, DataValue(BrowserInitialTsn, 0, 51, [1])));
        Assert.Equal(BrowserInitialTsn, LastSackCumulativeTsn(harness));

        harness.Receive(Chunk(0, 0x03, DataValue(BrowserInitialTsn + 2, 0, 51, [3])));
        Assert.Equal(BrowserInitialTsn, LastSackCumulativeTsn(harness));

        harness.Receive(Chunk(0, 0x03, DataValue(BrowserInitialTsn + 1, 0, 51, [2])));
        Assert.Equal(BrowserInitialTsn + 2, LastSackCumulativeTsn(harness));
    }

    [Fact]
    public void AcknowledgesADataChannelOpenOnTheStreamItArrivedOn()
    {
        var harness = Harness.Established();
        byte[] open = [0x03, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0];

        harness.Receive(Chunk(0, 0x03, DataValue(BrowserInitialTsn, 2, 50, open)));

        var ack = DataChunk.From(Assert.Single(harness.SentChunks(), chunk => chunk.Type == 0));
        Assert.Equal(2, ack.Stream);
        Assert.Equal(50u, ack.Ppid);
        Assert.Equal(new byte[] { 0x02 }, ack.Payload);
    }

    [Fact]
    public void StopsSendingAfterTheBrowserAborts()
    {
        var harness = Harness.Established();

        harness.Receive(Chunk(6, 0, []));

        Assert.True(harness.Association.IsClosed);
        Assert.False(harness.Association.SendText("late"));
    }

    private static uint LastSackCumulativeTsn(Harness harness)
    {
        var sack = harness.SentChunks().Last(chunk => chunk.Type == 3);
        return ReadUInt32(sack.Value, 0);
    }

    private static byte[] InitValue(uint tag, uint window, uint initialTsn)
    {
        var value = new byte[16];
        WriteUInt32(value, 0, tag);
        WriteUInt32(value, 4, window);
        WriteUInt16(value, 8, 1024);
        WriteUInt16(value, 10, 1024);
        WriteUInt32(value, 12, initialTsn);
        return value;
    }

    private static byte[] SackValue(uint cumulativeTsn, uint window)
    {
        var value = new byte[12];
        WriteUInt32(value, 0, cumulativeTsn);
        WriteUInt32(value, 4, window);
        return value;
    }

    private static byte[] DataValue(uint tsn, ushort stream, uint ppid, byte[] payload)
    {
        var value = new byte[12 + payload.Length];
        WriteUInt32(value, 0, tsn);
        WriteUInt16(value, 4, stream);
        WriteUInt32(value, 8, ppid);
        payload.CopyTo(value, 12);
        return value;
    }

    /// <summary>
    /// The STATE COOKIE parameter (type 7) that follows the fixed INIT ACK fields.
    /// </summary>
    private static byte[] StateCookie(byte[] initAck)
    {
        int position = 16;
        while (position + 4 <= initAck.Length)
        {
            int type = ReadUInt16(initAck, position);
            int length = ReadUInt16(initAck, position + 2);
            if (type == 7)
                return initAck[(position + 4)..(position + length)];
            position += (length + 3) & ~3;
        }
        throw new InvalidOperationException("INIT ACK carries no state cookie");
    }

    private static byte[] Chunk(byte type, byte flags, byte[] value)
    {
        var chunk = new byte[(4 + value.Length + 3) & ~3];
        chunk[0] = type;
        chunk[1] = flags;
        WriteUInt16(chunk, 2, (ushort)(4 + value.Length));
        value.CopyTo(chunk, 4);
        return chunk;
    }

    private static int ReadUInt16(byte[] b, int o) => (b[o] << 8) | b[o + 1];

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

    private sealed record ParsedChunk(byte Type, byte Flags, byte[] Value);

    private sealed record DataChunk(
        byte Flags,
        uint Tsn,
        int Stream,
        int Sequence,
        uint Ppid,
        byte[] Payload
    )
    {
        public static DataChunk From(ParsedChunk chunk)
        {
            Assert.Equal(0, chunk.Type);
            byte[] v = chunk.Value;
            return new DataChunk(
                chunk.Flags,
                ReadUInt32(v, 0),
                ReadUInt16(v, 4),
                ReadUInt16(v, 6),
                ReadUInt32(v, 8),
                v[12..]
            );
        }
    }

    /// <summary>
    /// Plays the browser's side: feeds packets to the association and records what it
    /// sends, with a clock the test advances.
    /// </summary>
    private sealed class Harness
    {
        public Harness()
        {
            Association = new SctpAssociation(Sent.Add, _ => { }, () => Now);
        }

        public List<byte[]> Sent { get; } = [];

        public DateTime Now { get; set; } = new(2026, 1, 1, 0, 0, 0, DateTimeKind.Utc);

        public SctpAssociation Association { get; }

        public static Harness Established(uint window = 128 * 1024)
        {
            var harness = new Harness();
            harness.Receive(Chunk(1, 0, InitValue(BrowserTag, window, BrowserInitialTsn)));
            byte[] cookie = StateCookie(harness.SentChunks()[0].Value);
            harness.Receive(Chunk(10, 0, cookie));
            harness.Sent.Clear();
            return harness;
        }

        public void Receive(params byte[][] chunks)
        {
            int length = 12 + chunks.Sum(chunk => chunk.Length);
            var packet = new byte[length];
            WriteUInt16(packet, 0, 5000);
            WriteUInt16(packet, 2, 5000);
            int position = 12;
            foreach (byte[] chunk in chunks)
            {
                chunk.CopyTo(packet, position);
                position += chunk.Length;
            }
            uint crc = Checksums.Crc32c(packet, 0, length);
            BitConverter.GetBytes(crc).CopyTo(packet, 8);
            Association.HandlePacket(packet, length);
        }

        public List<ParsedChunk> SentChunks()
        {
            var chunks = new List<ParsedChunk>();
            foreach (byte[] packet in Sent)
            {
                int position = 12;
                while (position + 4 <= packet.Length)
                {
                    int length = ReadUInt16(packet, position + 2);
                    chunks.Add(
                        new ParsedChunk(
                            packet[position],
                            packet[position + 1],
                            packet[(position + 4)..(position + length)]
                        )
                    );
                    position += (length + 3) & ~3;
                }
            }
            return chunks;
        }
    }
}
