using System.Collections.Concurrent;
using System.Net;
using System.Net.Sockets;

namespace InteractiveMapCompanion.Server.WebRtc;

/// <summary>
/// Streams the live map to browsers on the local network over WebRTC data channels.
/// Pairing is one-way: the link carries this server's address, ICE credentials and
/// certificate fingerprint, and the browser connects without sending anything back.
/// </summary>
internal sealed class WebRtcServer : IBroadcastTarget, IDisposable
{
    /// <summary>
    /// Each viewer costs a send thread and a copy of every snapshot.
    /// </summary>
    public const int MaxViewers = 8;

    private readonly int _port;
    private readonly SharingIdentity _identity;
    private readonly IceLiteResponder _ice;
    private readonly Action<string> _log;
    private readonly Func<string?> _handshake;
    private readonly ConcurrentDictionary<string, WebRtcPeer> _peers = new();

    // Closing a UDP socket does not wake a thread blocked in Receive on every platform
    // (.NET on macOS waits for it forever), so the loop wakes up to check for Stop.
    private const int ReceivePollMs = 100;

    private UdpClient? _udp;
    private Thread? _receiveThread;
    private volatile bool _running;
    private int _reportedViewers;
    private bool _warnedFull;

    public WebRtcServer(
        int port,
        SharingIdentity identity,
        Action<string> log,
        Func<string?> handshake
    )
    {
        _port = port;
        _identity = identity;
        _ice = new IceLiteResponder(identity.IceUfrag, identity.IcePassword);
        _log = log;
        _handshake = handshake;
    }

    /// <summary>
    /// Raised on a background thread when the number of open data channels changes.
    /// </summary>
    public event Action? ViewersChanged;

    public int ClientCount => _peers.Values.Count(peer => peer.IsOpen);

    /// <summary>
    /// Binds the UDP port. Throws <see cref="SocketException"/> when it is taken.
    /// </summary>
    public void Start()
    {
        if (_running)
            return;

        _udp = new UdpClient(new IPEndPoint(IPAddress.Any, _port));
        _udp.Client.ReceiveTimeout = ReceivePollMs;
        DisableConnectionResetErrors(_udp);
        _running = true;
        _receiveThread = new Thread(ReceiveLoop) { IsBackground = true, Name = "WebRTC receive" };
        _receiveThread.Start();
        _log($"Listening on UDP {_port}");
    }

    public void Stop()
    {
        // Sessions send their DTLS close alert over the socket, so browsers close their
        // data channel at once instead of after their consent checks time out.
        foreach (var peer in _peers.Values)
            peer.Dispose();
        _peers.Clear();

        _running = false;
        var receiveThread = _receiveThread;
        _receiveThread = null;
        if (receiveThread != null && receiveThread != Thread.CurrentThread)
            receiveThread.Join(ReceivePollMs * 10);
        _udp?.Close();
        _udp = null;
        ReportViewers();
    }

    public void Dispose() => Stop();

    public void Broadcast(string message)
    {
        foreach (var peer in _peers.Values)
        {
            if (peer.IsOpen)
                peer.Send(message);
        }
    }

    private void ReceiveLoop()
    {
        while (_running)
        {
            var udp = _udp;
            if (udp == null)
                break;

            byte[] datagram;
            var remote = new IPEndPoint(IPAddress.Any, 0);
            try
            {
                datagram = udp.Receive(ref remote);
            }
            catch (SocketException)
            {
                if (!_running)
                    break;
                continue;
            }
            catch (ObjectDisposedException)
            {
                break;
            }

            string key = remote.ToString();
            if (IceLiteResponder.IsStun(datagram, datagram.Length))
                HandleConnectivityCheck(datagram, remote, key);
            else if (datagram.Length > 0 && datagram[0] >= 20 && datagram[0] <= 63)
            {
                // DTLS records (RFC 7983) count only from an endpoint that passed an ICE check.
                if (_peers.TryGetValue(key, out var peer) && !peer.IsFinished)
                    peer.Deliver(datagram);
            }
        }
    }

    private void HandleConnectivityCheck(byte[] datagram, IPEndPoint remote, string key)
    {
        byte[]? response = _ice.Respond(datagram, datagram.Length, remote);
        if (response == null)
            return;

        if (_peers.TryGetValue(key, out var existing) && !existing.IsFinished)
        {
            SendDatagram(response, 0, response.Length, remote);
            existing.Touch();
            return;
        }

        // A browser whose checks go unanswered reports a failed connection.
        if (_peers.Values.Count(peer => !peer.IsFinished) >= MaxViewers)
        {
            if (!_warnedFull)
                _log($"Refusing {remote}: {MaxViewers} devices are already connected");
            _warnedFull = true;
            return;
        }

        _warnedFull = false;
        SendDatagram(response, 0, response.Length, remote);
        _log($"Connectivity check from {remote}, starting a session");
        _peers[key] = new WebRtcPeer(
            remote,
            SendDatagram,
            _identity.Dtls,
            _log,
            OnPeerOpened,
            OnPeerClosed
        );
    }

    private void SendDatagram(byte[] buffer, int offset, int length, IPEndPoint remote)
    {
        var udp = _udp;
        if (udp == null)
            return;

        try
        {
            if (offset == 0)
                udp.Send(buffer, length, remote);
            else
            {
                var copy = new byte[length];
                Buffer.BlockCopy(buffer, offset, copy, 0, length);
                udp.Send(copy, length, remote);
            }
        }
        catch (Exception ex) when (ex is SocketException || ex is ObjectDisposedException)
        {
            // The browser left; its session times out.
        }
    }

    private void OnPeerOpened(WebRtcPeer peer)
    {
        _log($"Data channel open with {peer.Remote}");
        string? handshake = _handshake();
        if (handshake != null)
            peer.Send(handshake);
        ReportViewers();
    }

    private void OnPeerClosed(WebRtcPeer peer)
    {
        string key = peer.Remote.ToString();
        if (_peers.TryGetValue(key, out var current) && ReferenceEquals(current, peer))
            _peers.TryRemove(key, out _);
        _log($"Session with {peer.Remote} closed");
        ReportViewers();
    }

    private void ReportViewers()
    {
        int viewers = ClientCount;
        if (Interlocked.Exchange(ref _reportedViewers, viewers) != viewers)
            ViewersChanged?.Invoke();
    }

    private static void DisableConnectionResetErrors(UdpClient udp)
    {
        // Windows reports an ICMP port-unreachable from a closed browser tab as an error
        // on the next receive. SIO_UDP_CONNRESET turns that off; other systems lack it.
        const int SioUdpConnReset = -1744830452;
        try
        {
            udp.Client.IOControl(SioUdpConnReset, [0], null);
        }
        catch (Exception)
        {
            // Unity's Mono and Wine differ in which exception reports a missing option.
        }
    }
}
