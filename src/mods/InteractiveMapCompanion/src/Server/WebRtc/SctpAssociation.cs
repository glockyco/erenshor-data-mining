using System.Security.Cryptography;
using System.Text;

namespace InteractiveMapCompanion.Server.WebRtc;

/// <summary>
/// The server side of the SCTP association that carries WebRTC data channels over DTLS
/// (RFC 4960, RFC 8831). It accepts the browser's INIT, sends text messages on stream 0,
/// which the browser opens as a negotiated channel with id 0, and answers the browser's
/// SACKs, heartbeats and data channel opens. Lost packets are retransmitted on a timer.
/// </summary>
internal sealed class SctpAssociation
{
    private const byte ChunkData = 0;
    private const byte ChunkInit = 1;
    private const byte ChunkInitAck = 2;
    private const byte ChunkSack = 3;
    private const byte ChunkHeartbeat = 4;
    private const byte ChunkHeartbeatAck = 5;
    private const byte ChunkAbort = 6;
    private const byte ChunkShutdown = 7;
    private const byte ChunkShutdownAck = 8;
    private const byte ChunkCookieEcho = 10;
    private const byte ChunkCookieAck = 11;
    private const byte ChunkForwardTsn = 192;

    private const uint PpidControl = 50;
    private const uint PpidString = 51;
    private const byte DataChannelOpen = 0x03;
    private const byte DataChannelAck = 0x02;

    private const int MaxFragment = 1024;
    private const uint LocalWindow = 1024 * 1024;
    private const int MinRtoMs = 300;
    private const int MaxRtoMs = 4000;

    private readonly Action<byte[]> _sendPacket;
    private readonly Action<string> _log;
    private readonly object _gate = new();
    private readonly LinkedList<OutstandingChunk> _outstanding = new();
    private readonly SortedSet<uint> _receivedAhead = new(new SerialComparer());
    private readonly uint _localTag;
    private readonly byte[] _cookie;

    private uint _peerTag;
    private ushort _localPort = 5000;
    private ushort _peerPort = 5000;
    private uint _nextTsn;
    private uint _peerCumulativeTsn;
    private bool _peerTsnKnown;
    private uint _peerWindow = 128 * 1024;
    private ushort _nextSequence;
    private int _outstandingBytes;
    private int _rtoMs = 1000;
    private bool _established;
    private bool _closed;

    public SctpAssociation(Action<byte[]> sendPacket, Action<string> log)
    {
        _sendPacket = sendPacket;
        _log = log;
        _localTag = RandomNonZero();
        _nextTsn = RandomNonZero();
        _cookie = RandomBytes(16);
    }

    /// <summary>
    /// Raised once, when the browser's COOKIE ECHO completes the association.
    /// </summary>
    public event Action? Established;

    public bool IsEstablished
    {
        get
        {
            lock (_gate)
                return _established && !_closed;
        }
    }

    public bool IsClosed
    {
        get
        {
            lock (_gate)
                return _closed;
        }
    }

    /// <summary>
    /// Handles one SCTP packet that DTLS decrypted.
    /// </summary>
    public void HandlePacket(byte[] packet, int length)
    {
        if (length < 12)
            return;

        uint checksum = BitConverter.ToUInt32(packet, 8);
        packet[8] = packet[9] = packet[10] = packet[11] = 0;
        if (Checksums.Crc32c(packet, 0, length) != checksum)
            _log(
                "SCTP checksum mismatch; DTLS already authenticated the packet, so it is used anyway"
            );

        ushort sourcePort = ReadUInt16(packet, 0);
        ushort destinationPort = ReadUInt16(packet, 2);
        bool receivedData = false;
        bool established = false;

        lock (_gate)
        {
            if (_closed)
                return;

            int position = 12;
            while (position + 4 <= length)
            {
                byte type = packet[position];
                byte flags = packet[position + 1];
                int chunkLength = ReadUInt16(packet, position + 2);
                if (chunkLength < 4 || position + chunkLength > length)
                    break;

                int value = position + 4;
                int valueLength = chunkLength - 4;
                switch (type)
                {
                    case ChunkInit:
                        HandleInit(packet, value, valueLength, sourcePort, destinationPort);
                        break;
                    case ChunkCookieEcho:
                        SendChunks(new Chunk(ChunkCookieAck, 0, []));
                        if (!_established)
                        {
                            _established = true;
                            established = true;
                        }
                        break;
                    case ChunkData:
                        receivedData |= HandleData(packet, value, valueLength, flags);
                        break;
                    case ChunkSack:
                        HandleSack(packet, value, valueLength);
                        break;
                    case ChunkHeartbeat:
                        SendChunks(
                            new Chunk(ChunkHeartbeatAck, 0, Slice(packet, value, valueLength))
                        );
                        break;
                    case ChunkForwardTsn when valueLength >= 4:
                        AdvancePeerTsn(ReadUInt32(packet, value));
                        receivedData = true;
                        break;
                    case ChunkShutdown:
                        SendChunks(new Chunk(ChunkShutdownAck, 0, []));
                        _closed = true;
                        break;
                    case ChunkAbort:
                        _closed = true;
                        break;
                }

                position += (chunkLength + 3) & ~3;
            }

            if (receivedData && !_closed)
                SendSack();
        }

        if (established)
            Established?.Invoke();
    }

    /// <summary>
    /// Sends one text message on stream 0. Returns false without queueing when the
    /// association is not open or the browser has not yet acknowledged enough earlier
    /// data, so a slow viewer skips snapshots instead of falling behind.
    /// </summary>
    public bool SendText(string text)
    {
        byte[] payload = Encoding.UTF8.GetBytes(text);
        lock (_gate)
        {
            if (!_established || _closed)
                return false;
            if (_outstandingBytes + payload.Length > Math.Min(_peerWindow, 512 * 1024))
                return false;

            ushort sequence = _nextSequence++;
            int fragments = Math.Max(1, (payload.Length + MaxFragment - 1) / MaxFragment);
            for (int i = 0; i < fragments; i++)
            {
                int offset = i * MaxFragment;
                int count = Math.Min(MaxFragment, payload.Length - offset);
                byte flags = (byte)((i == 0 ? 0x02 : 0) | (i == fragments - 1 ? 0x01 : 0));
                uint tsn = _nextTsn++;

                var value = new byte[12 + count];
                WriteUInt32(value, 0, tsn);
                WriteUInt16(value, 4, 0);
                WriteUInt16(value, 6, sequence);
                WriteUInt32(value, 8, PpidString);
                Buffer.BlockCopy(payload, offset, value, 12, count);

                byte[] packet = BuildPacket(new Chunk(ChunkData, flags, value));
                _outstanding.AddLast(new OutstandingChunk(tsn, count, packet, DateTime.UtcNow));
                _outstandingBytes += count;
                _sendPacket(packet);
            }

            return true;
        }
    }

    /// <summary>
    /// Retransmits the oldest unacknowledged packets when the retransmission timer expired.
    /// </summary>
    public void Tick()
    {
        lock (_gate)
        {
            if (_closed || _outstanding.Count == 0)
                return;

            var oldest = _outstanding.First!.Value;
            if ((DateTime.UtcNow - oldest.SentAt).TotalMilliseconds < _rtoMs)
                return;

            int resent = 0;
            for (var node = _outstanding.First; node != null && resent < 16; node = node.Next)
            {
                node.Value.SentAt = DateTime.UtcNow;
                _sendPacket(node.Value.Packet);
                resent++;
            }

            _rtoMs = Math.Min(_rtoMs * 2, MaxRtoMs);
        }
    }

    private void HandleInit(
        byte[] packet,
        int value,
        int valueLength,
        ushort sourcePort,
        ushort destinationPort
    )
    {
        if (valueLength < 16)
            return;

        _peerTag = ReadUInt32(packet, value);
        _peerWindow = ReadUInt32(packet, value + 4);
        ushort peerInboundStreams = ReadUInt16(packet, value + 10);
        uint peerInitialTsn = ReadUInt32(packet, value + 12);
        _peerCumulativeTsn = peerInitialTsn - 1;
        _peerTsnKnown = true;
        _peerPort = sourcePort;
        _localPort = destinationPort;

        // INIT ACK: our tag, window, stream counts and first TSN, then the state cookie
        // the browser must echo back.
        var ack = new byte[16 + 4 + _cookie.Length];
        WriteUInt32(ack, 0, _localTag);
        WriteUInt32(ack, 4, LocalWindow);
        WriteUInt16(ack, 8, Math.Min((ushort)1024, peerInboundStreams));
        WriteUInt16(ack, 10, 1024);
        WriteUInt32(ack, 12, _nextTsn);
        WriteUInt16(ack, 16, 7);
        WriteUInt16(ack, 18, (ushort)(4 + _cookie.Length));
        Buffer.BlockCopy(_cookie, 0, ack, 20, _cookie.Length);

        // An INIT ACK carries the initiate tag of the INIT it answers.
        SendChunks(new Chunk(ChunkInitAck, 0, ack));
    }

    private bool HandleData(byte[] packet, int value, int valueLength, byte flags)
    {
        if (valueLength < 12 || !_peerTsnKnown)
            return false;

        uint tsn = ReadUInt32(packet, value);
        ushort stream = ReadUInt16(packet, value + 4);
        uint ppid = ReadUInt32(packet, value + 8);

        if (!SerialGreater(tsn, _peerCumulativeTsn) || _receivedAhead.Contains(tsn))
            return true;

        if (tsn == _peerCumulativeTsn + 1)
            AdvancePeerTsn(tsn);
        else
            _receivedAhead.Add(tsn);

        // Answer a DATA_CHANNEL_OPEN for a channel the browser created itself, so both
        // negotiated and announced channels open. Single-fragment control messages only.
        bool whole = (flags & 0x03) == 0x03;
        if (
            whole
            && ppid == PpidControl
            && valueLength > 12
            && packet[value + 12] == DataChannelOpen
        )
        {
            var ack = new byte[12 + 1];
            WriteUInt32(ack, 0, _nextTsn++);
            WriteUInt16(ack, 4, stream);
            WriteUInt16(ack, 6, 0);
            WriteUInt32(ack, 8, PpidControl);
            ack[12] = DataChannelAck;
            byte[] ackPacket = BuildPacket(new Chunk(ChunkData, 0x07, ack));
            _outstanding.AddLast(
                new OutstandingChunk(ReadUInt32(ack, 0), 1, ackPacket, DateTime.UtcNow)
            );
            _outstandingBytes += 1;
            _sendPacket(ackPacket);
            _log($"Data channel open on stream {stream} acknowledged");
        }

        return true;
    }

    private void AdvancePeerTsn(uint tsn)
    {
        if (SerialGreater(tsn, _peerCumulativeTsn))
            _peerCumulativeTsn = tsn;
        while (_receivedAhead.Count > 0)
        {
            uint next = _receivedAhead.Min;
            if (SerialGreater(next, _peerCumulativeTsn + 1))
                break;
            _receivedAhead.Remove(next);
            if (SerialGreater(next, _peerCumulativeTsn))
                _peerCumulativeTsn = next;
        }
    }

    private void HandleSack(byte[] packet, int value, int valueLength)
    {
        if (valueLength < 12)
            return;

        uint cumulativeAck = ReadUInt32(packet, value);
        _peerWindow = ReadUInt32(packet, value + 4);
        int gapBlocks = ReadUInt16(packet, value + 8);

        bool progressed = false;
        for (var node = _outstanding.First; node != null; )
        {
            var next = node.Next;
            uint tsn = node.Value.Tsn;
            bool acknowledged = !SerialGreater(tsn, cumulativeAck);
            for (int g = 0; g < gapBlocks && !acknowledged; g++)
            {
                int block = value + 12 + g * 4;
                if (block + 4 > value + valueLength)
                    break;
                uint start = cumulativeAck + ReadUInt16(packet, block);
                uint end = cumulativeAck + ReadUInt16(packet, block + 2);
                acknowledged = !SerialGreater(start, tsn) && !SerialGreater(tsn, end);
            }

            if (acknowledged)
            {
                _outstandingBytes -= node.Value.Bytes;
                _outstanding.Remove(node);
                progressed = true;
            }

            node = next;
        }

        if (_outstanding.Count == 0)
            _outstandingBytes = 0;
        if (progressed)
            _rtoMs = MinRtoMs;
    }

    private void SendSack()
    {
        var sack = new byte[12];
        WriteUInt32(sack, 0, _peerCumulativeTsn);
        WriteUInt32(sack, 4, LocalWindow);
        SendChunks(new Chunk(ChunkSack, 0, sack));
    }

    private void SendChunks(Chunk chunk) => _sendPacket(BuildPacket(chunk));

    private byte[] BuildPacket(Chunk chunk)
    {
        int chunkLength = 4 + chunk.Value.Length;
        var packet = new byte[12 + ((chunkLength + 3) & ~3)];
        WriteUInt16(packet, 0, _localPort);
        WriteUInt16(packet, 2, _peerPort);
        WriteUInt32(packet, 4, _peerTag);
        packet[12] = chunk.Type;
        packet[13] = chunk.Flags;
        WriteUInt16(packet, 14, (ushort)chunkLength);
        Buffer.BlockCopy(chunk.Value, 0, packet, 16, chunk.Value.Length);

        // SCTP stores CRC-32C least significant byte first (RFC 4960 appendix B).
        uint crc = Checksums.Crc32c(packet, 0, packet.Length);
        packet[8] = (byte)crc;
        packet[9] = (byte)(crc >> 8);
        packet[10] = (byte)(crc >> 16);
        packet[11] = (byte)(crc >> 24);
        return packet;
    }

    private static bool SerialGreater(uint a, uint b) => (int)(a - b) > 0;

    private static byte[] Slice(byte[] source, int offset, int count)
    {
        var copy = new byte[count];
        Buffer.BlockCopy(source, offset, copy, 0, count);
        return copy;
    }

    private static uint RandomNonZero()
    {
        uint value;
        do value = BitConverter.ToUInt32(RandomBytes(4), 0);
        while (value == 0);
        return value;
    }

    private static byte[] RandomBytes(int count)
    {
        var bytes = new byte[count];
        using var rng = RandomNumberGenerator.Create();
        rng.GetBytes(bytes);
        return bytes;
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

    private readonly struct Chunk(byte type, byte flags, byte[] value)
    {
        public byte Type { get; } = type;
        public byte Flags { get; } = flags;
        public byte[] Value { get; } = value;
    }

    private sealed class OutstandingChunk(uint tsn, int bytes, byte[] packet, DateTime sentAt)
    {
        public uint Tsn { get; } = tsn;
        public int Bytes { get; } = bytes;
        public byte[] Packet { get; } = packet;
        public DateTime SentAt { get; set; } = sentAt;
    }

    private sealed class SerialComparer : IComparer<uint>
    {
        public int Compare(uint x, uint y) =>
            x == y ? 0
            : SerialGreater(x, y) ? 1
            : -1;
    }
}
