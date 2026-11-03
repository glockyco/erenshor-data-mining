using System.Collections.Concurrent;
using System.Net;
using Org.BouncyCastle.Security;
using Org.BouncyCastle.Tls;
using Org.BouncyCastle.Tls.Crypto.Impl.BC;

namespace InteractiveMapCompanion.Server.WebRtc;

/// <summary>
/// One browser's connection: DTLS on top of the shared UDP socket, then SCTP inside DTLS.
/// A dedicated thread runs the blocking BouncyCastle handshake and the receive loop, and
/// a second one encrypts and sends, so broadcasting from the game's main thread only
/// queues a message.
/// </summary>
internal sealed class WebRtcPeer
{
    // Browsers send ICE consent checks every few seconds; silence this long means the
    // page closed or the device left the network.
    private static readonly long IdleTimeoutTicks = TimeSpan.FromSeconds(30).Ticks;

    // A viewer with this many messages waiting is behind; it skips snapshots until it
    // catches up instead of building a backlog.
    private const int MaxQueuedMessages = 4;

    private readonly PeerDatagramTransport _transport;
    private readonly DtlsIdentity _identity;
    private readonly Action<string> _log;
    private readonly Action<WebRtcPeer> _opened;
    private readonly Action<WebRtcPeer> _closed;
    private readonly object _sendGate = new();
    private readonly ConcurrentQueue<string> _outbox = new();
    private readonly SemaphoreSlim _outboxSignal = new(0);
    private DtlsTransport? _dtls;
    private SctpAssociation? _sctp;
    private long _lastSeenTicks;
    private int _disposed;

    public WebRtcPeer(
        IPEndPoint remote,
        Action<byte[], int, int, IPEndPoint> sendDatagram,
        DtlsIdentity identity,
        Action<string> log,
        Action<WebRtcPeer> opened,
        Action<WebRtcPeer> closed
    )
    {
        Remote = remote;
        _identity = identity;
        _log = log;
        _opened = opened;
        _closed = closed;
        _transport = new PeerDatagramTransport(
            (buf, off, len) => sendDatagram(buf, off, len, remote)
        );
        Touch();
        new Thread(Run) { IsBackground = true, Name = $"WebRTC {remote}" }.Start();
    }

    public IPEndPoint Remote { get; }

    public bool IsOpen => Volatile.Read(ref _disposed) == 0 && _sctp?.IsEstablished == true;

    public bool IsFinished => Volatile.Read(ref _disposed) != 0;

    public void Touch() => Interlocked.Exchange(ref _lastSeenTicks, DateTime.UtcNow.Ticks);

    public void Deliver(byte[] datagram)
    {
        Touch();
        _transport.Enqueue(datagram);
    }

    public bool Send(string text)
    {
        if (IsFinished || _sctp?.IsEstablished != true || _outbox.Count >= MaxQueuedMessages)
            return false;

        _outbox.Enqueue(text);
        _outboxSignal.Release();
        return true;
    }

    public void Dispose()
    {
        if (Interlocked.Exchange(ref _disposed, 1) != 0)
            return;

        try
        {
            _dtls?.Close();
        }
        catch
        {
            // The browser may already be gone.
        }

        _transport.Close();
        _outboxSignal.Release();
        _closed(this);
    }

    private void Run()
    {
        try
        {
            var crypto = new BcTlsCrypto(new SecureRandom());
            var server = new WebRtcTlsServer(crypto, _identity, _log);
            var protocol = new DtlsServerProtocol { VerifyRequests = false };
            var dtls = protocol.Accept(server, _transport);
            _dtls = dtls;
            _log($"DTLS handshake complete with {Remote}");

            var sctp = new SctpAssociation(SendSctp, _log);
            sctp.Established += () => _opened(this);
            _sctp = sctp;
            new Thread(() => SendLoop(sctp))
            {
                IsBackground = true,
                Name = $"WebRTC send {Remote}",
            }.Start();

            var buffer = new byte[dtls.GetReceiveLimit()];
            while (!IsFinished && !sctp.IsClosed)
            {
                int count = dtls.Receive(buffer, 0, buffer.Length, 100);
                if (count > 0)
                    sctp.HandlePacket(buffer, count);
                sctp.Tick();

                if (DateTime.UtcNow.Ticks - Interlocked.Read(ref _lastSeenTicks) > IdleTimeoutTicks)
                {
                    _log($"No traffic from {Remote} for 30 seconds");
                    break;
                }
            }
        }
        catch (Exception ex)
        {
            if (!IsFinished)
                _log($"WebRTC session with {Remote} ended: {ex.GetType().Name}: {ex.Message}");
        }
        finally
        {
            Dispose();
        }
    }

    private void SendLoop(SctpAssociation sctp)
    {
        while (!IsFinished)
        {
            if (!_outboxSignal.Wait(1000))
                continue;
            while (!IsFinished && _outbox.TryDequeue(out string? text))
                sctp.SendText(text);
        }
    }

    private void SendSctp(byte[] packet)
    {
        var dtls = _dtls;
        if (dtls == null)
            return;

        lock (_sendGate)
        {
            try
            {
                dtls.Send(packet, 0, packet.Length);
            }
            catch (Exception ex)
            {
                _log($"DTLS send to {Remote} failed: {ex.Message}");
            }
        }
    }
}
