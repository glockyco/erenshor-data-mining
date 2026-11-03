using System.Collections.Concurrent;
using System.Net;
using System.Net.NetworkInformation;
using System.Net.Sockets;
using System.Security.Cryptography;

namespace InteractiveMapCompanion.Server.WebRtc;

/// <summary>
/// Streams the live map to browsers on the local network over WebRTC data channels.
/// Pairing is one-way: the link carries this server's address, ICE credentials and
/// certificate fingerprint, and the browser connects without sending anything back.
/// </summary>
public sealed class WebRtcServer : IWebSocketServer
{
    private const string TokenAlphabet =
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";

    private readonly int _port;
    private readonly Action<string> _log;
    private readonly Func<string?> _handshake;
    private readonly ConcurrentDictionary<string, WebRtcPeer> _peers = new();

    private DtlsIdentity? _identity;
    private IceLiteResponder? _ice;
    private UdpClient? _udp;
    private volatile bool _running;

    public WebRtcServer(int port, Action<string> log, Func<string?> handshake)
    {
        _port = port;
        _log = log;
        _handshake = handshake;
        IceUfrag = RandomToken(8);
        IcePassword = RandomToken(24);
    }

    public int Port => _port;

    public string IceUfrag { get; }

    public string IcePassword { get; }

    public string? Fingerprint => _identity?.Fingerprint;

    public int ClientCount => _peers.Values.Count(peer => peer.IsOpen);

    public void Start()
    {
        if (_running)
            return;

        _identity = DtlsIdentity.Create();
        _ice = new IceLiteResponder(IceUfrag, IcePassword);
        _udp = new UdpClient(new IPEndPoint(IPAddress.Any, _port));
        DisableConnectionResetErrors(_udp);
        _running = true;
        new Thread(ReceiveLoop) { IsBackground = true, Name = "WebRTC receive" }.Start();

        _log(
            $"WebRTC listening on UDP {_port} at {string.Join(", ", GetLanAddresses())}, "
                + $"ufrag {IceUfrag}, fingerprint {Fingerprint}"
        );
    }

    public void Stop()
    {
        _running = false;
        try
        {
            _udp?.Close();
        }
        catch
        {
            // Closing an already closed socket.
        }

        foreach (var peer in _peers.Values)
            peer.Dispose();
        _peers.Clear();
        _udp = null;
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

    /// <summary>
    /// Private IPv4 addresses of interfaces that are up, which a device on the same
    /// network can reach.
    /// </summary>
    public static IReadOnlyList<IPAddress> GetLanAddresses()
    {
        var addresses = new List<IPAddress>();
        try
        {
            foreach (var networkInterface in NetworkInterface.GetAllNetworkInterfaces())
            {
                if (
                    networkInterface.OperationalStatus != OperationalStatus.Up
                    || networkInterface.NetworkInterfaceType == NetworkInterfaceType.Loopback
                )
                    continue;

                foreach (var unicast in networkInterface.GetIPProperties().UnicastAddresses)
                {
                    var address = unicast.Address;
                    if (address.AddressFamily == AddressFamily.InterNetwork && IsPrivate(address))
                        addresses.Add(address);
                }
            }
        }
        catch
        {
            // Some runtimes cannot enumerate interfaces; the caller shows no address.
        }

        return addresses;
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
            {
                byte[]? response = _ice!.Respond(datagram, datagram.Length, remote);
                if (response == null)
                    continue;

                SendDatagram(response, 0, response.Length, remote);
                if (_peers.TryGetValue(key, out var existing) && !existing.IsFinished)
                {
                    existing.Touch();
                    continue;
                }

                _log($"ICE check from {remote}, starting a session");
                _peers[key] = new WebRtcPeer(
                    remote,
                    SendDatagram,
                    _identity!,
                    _log,
                    OnPeerOpened,
                    OnPeerClosed
                );
            }
            else if (datagram.Length > 0 && datagram[0] >= 20 && datagram[0] <= 63)
            {
                // DTLS records (RFC 7983) count only from an endpoint that passed an ICE check.
                if (_peers.TryGetValue(key, out var peer) && !peer.IsFinished)
                    peer.Deliver(datagram);
            }
        }
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
        _log($"Data channel open with {peer.Remote} (open: {ClientCount})");
        string? handshake = _handshake();
        if (handshake != null)
            peer.Send(handshake);
    }

    private void OnPeerClosed(WebRtcPeer peer)
    {
        string key = peer.Remote.ToString();
        if (_peers.TryGetValue(key, out var current) && ReferenceEquals(current, peer))
            _peers.TryRemove(key, out _);
        _log($"Session with {peer.Remote} closed (open: {ClientCount})");
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
        catch
        {
            // Not supported on this runtime.
        }
    }

    private static bool IsPrivate(IPAddress address)
    {
        byte[] b = address.GetAddressBytes();
        return b[0] == 10
            || (b[0] == 172 && b[1] >= 16 && b[1] <= 31)
            || (b[0] == 192 && b[1] == 168);
    }

    private static string RandomToken(int length)
    {
        var bytes = new byte[length];
        using (var rng = RandomNumberGenerator.Create())
            rng.GetBytes(bytes);
        var chars = new char[length];
        for (int i = 0; i < length; i++)
            chars[i] = TokenAlphabet[bytes[i] % TokenAlphabet.Length];
        return new string(chars);
    }
}
