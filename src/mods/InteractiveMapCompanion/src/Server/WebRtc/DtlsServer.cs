using System.Collections.Concurrent;
using Org.BouncyCastle.Tls;
using Org.BouncyCastle.Tls.Crypto;
using Org.BouncyCastle.Tls.Crypto.Impl.BC;

namespace InteractiveMapCompanion.Server.WebRtc;

/// <summary>
/// DTLS 1.2 server side of a WebRTC connection. It asks for the browser's certificate,
/// as WebRTC requires, but does not pin it: the browser already proved it holds the
/// pairing link's ICE password, and it pins this server's certificate by fingerprint.
/// </summary>
internal sealed class WebRtcTlsServer : DefaultTlsServer
{
    private readonly DtlsIdentity _identity;
    private readonly Action<string> _log;

    public WebRtcTlsServer(BcTlsCrypto crypto, DtlsIdentity identity, Action<string> log)
        : base(crypto)
    {
        _identity = identity;
        _log = log;
    }

    protected override ProtocolVersion[] GetSupportedVersions() => ProtocolVersion.DTLSv12.Only();

    protected override int[] GetSupportedCipherSuites() =>
        [
            CipherSuite.TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256,
            CipherSuite.TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384,
            CipherSuite.TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305_SHA256,
        ];

    protected override TlsCredentialedSigner GetECDsaSignerCredentials()
    {
        var crypto = (BcTlsCrypto)Crypto;
        var certificate = new Certificate([
            new BcTlsCertificate(crypto, _identity.Certificate.CertificateStructure),
        ]);
        return new BcDefaultTlsCredentialedSigner(
            new TlsCryptoParameters(m_context),
            crypto,
            _identity.PrivateKey,
            certificate,
            new SignatureAndHashAlgorithm(
                Org.BouncyCastle.Tls.HashAlgorithm.sha256,
                SignatureAlgorithm.ecdsa
            )
        );
    }

    public override CertificateRequest GetCertificateRequest() =>
        new(
            [ClientCertificateType.ecdsa_sign, ClientCertificateType.rsa_sign],
            TlsUtilities.GetDefaultSupportedSignatureAlgorithms(m_context),
            null
        );

    public override void NotifyClientCertificate(Certificate clientCertificate) { }

    public override int GetHandshakeTimeoutMillis() => 10_000;

    public override void NotifyAlertRaised(
        short alertLevel,
        short alertDescription,
        string message,
        Exception cause
    ) =>
        _log(
            $"DTLS alert raised: {AlertDescription.GetText(alertDescription)} {message} {cause?.Message}"
        );

    public override void NotifyAlertReceived(short alertLevel, short alertDescription) =>
        _log($"DTLS alert received: {AlertDescription.GetText(alertDescription)}");
}

/// <summary>
/// Feeds one remote endpoint's datagrams to BouncyCastle and sends its records back
/// through the shared UDP socket.
/// </summary>
internal sealed class PeerDatagramTransport(Action<byte[], int, int> send) : DatagramTransport
{
    private const int Mtu = 1200;
    private readonly BlockingCollection<byte[]> _incoming = new(new ConcurrentQueue<byte[]>());

    public void Enqueue(byte[] datagram)
    {
        if (!_incoming.IsAddingCompleted)
            _incoming.TryAdd(datagram);
    }

    public int GetReceiveLimit() => 1500;

    public int GetSendLimit() => Mtu;

    public int Receive(byte[] buf, int off, int len, int waitMillis)
    {
        if (_incoming.IsCompleted)
            throw new IOException("Peer transport closed");
        if (!_incoming.TryTake(out byte[]? datagram, waitMillis == 0 ? -1 : waitMillis))
            return -1;
        int count = Math.Min(len, datagram.Length);
        Buffer.BlockCopy(datagram, 0, buf, off, count);
        return count;
    }

    public int Receive(Span<byte> buffer, int waitMillis)
    {
        var copy = new byte[buffer.Length];
        int count = Receive(copy, 0, copy.Length, waitMillis);
        if (count > 0)
            copy.AsSpan(0, count).CopyTo(buffer);
        return count;
    }

    public void Send(byte[] buf, int off, int len) => send(buf, off, len);

    public void Send(ReadOnlySpan<byte> buffer)
    {
        byte[] copy = buffer.ToArray();
        send(copy, 0, copy.Length);
    }

    public void Close() => _incoming.CompleteAdding();
}
