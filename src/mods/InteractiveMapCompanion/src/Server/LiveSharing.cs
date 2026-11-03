using System.Net;
using System.Net.Sockets;
using InteractiveMapCompanion.Config;
using InteractiveMapCompanion.Protocol;
using InteractiveMapCompanion.Server.WebRtc;

namespace InteractiveMapCompanion.Server;

/// <summary>
/// Shares the live map with phones and other PCs on the same network. While sharing is
/// on it runs the WebRTC server and the pairing redirect on the port after
/// <see cref="IModConfig.Port"/>, and it keeps the setting and the pairing credentials in
/// the config. Change it on the main thread; the properties and broadcast members may be
/// read from any thread.
/// </summary>
internal sealed class LiveSharing : IBroadcastTarget, IDisposable
{
    /// <summary>
    /// <see cref="SharingStatus.Error"/> when the sharing port could not be bound.
    /// </summary>
    public const string PortUnavailableError = "portUnavailable";

    private readonly IModConfig _config;
    private readonly IModLogger _log;
    private readonly Func<string?> _remoteHandshake;

    private WebRtcServer? _webRtc;
    private PairingRedirectServer? _redirect;
    private volatile Snapshot _snapshot = Snapshot.Off;

    /// <summary>
    /// <paramref name="remoteHandshake"/> builds the handshake a remote viewer receives
    /// when its data channel opens.
    /// </summary>
    public LiveSharing(IModConfig config, IModLogger log, Func<string?> remoteHandshake)
    {
        _config = config;
        _log = log;
        _remoteHandshake = remoteHandshake;
    }

    /// <summary>
    /// Raised when sharing turns on or off, fails, or the number of viewers changes.
    /// Viewer changes arrive on a background thread.
    /// </summary>
    public event Action? Changed;

    public int Port => _config.Port + 1;

    public bool Enabled => _snapshot.Enabled;

    /// <summary>
    /// What a trusted map on this PC shows about sharing.
    /// </summary>
    public SharingStatus Status
    {
        get
        {
            var snapshot = _snapshot;
            return new SharingStatus(
                snapshot.Enabled,
                ClientCount,
                Port,
                snapshot.Address,
                snapshot.Link,
                snapshot.Error
            );
        }
    }

    public int ClientCount => _webRtc?.ClientCount ?? 0;

    public void Broadcast(string message) => _webRtc?.Broadcast(message);

    /// <summary>
    /// Starts sharing when the config says it was on when the game last ran.
    /// </summary>
    public void Restore()
    {
        if (_config.SharingEnabled)
            SetEnabled(true);
    }

    /// <summary>
    /// Starts or stops sharing and saves the choice. Stopping also discards the pairing
    /// credentials, so links shown earlier stop working.
    /// </summary>
    public void SetEnabled(bool enabled)
    {
        if (enabled == Enabled)
            return;

        if (enabled)
            Start();
        else
        {
            StopServers();
            _config.SharingIdentity = "";
            _config.SharingEnabled = false;
            _snapshot = Snapshot.Off;
            _log.LogInfo("Stopped sharing the live map");
        }

        Changed?.Invoke();
    }

    /// <summary>
    /// Closes the sockets without changing the saved setting, so sharing resumes on the
    /// next start.
    /// </summary>
    public void Dispose() => StopServers();

    private void Start()
    {
        int port = Port;
        var identity = SharingIdentity.Parse(_config.SharingIdentity);
        if (identity == null)
        {
            identity = SharingIdentity.Create();
            _config.SharingIdentity = identity.Serialize();
        }

        var webRtc = new WebRtcServer(
            port,
            identity,
            message => _log.LogInfo($"[Sharing] {message}"),
            _remoteHandshake
        );
        var redirect = new PairingRedirectServer(
            address => LinkFor(address, port, identity),
            message => _log.LogDebug($"[Sharing] {message}")
        );
        try
        {
            webRtc.Start();
            redirect.Start(port);
        }
        catch (SocketException ex)
        {
            webRtc.Dispose();
            redirect.Dispose();
            _config.SharingEnabled = false;
            _snapshot = new Snapshot(false, PortUnavailableError, null, null);
            // Mono under Wine reports "Error looking up error string" as the message.
            _log.LogWarning(
                $"Cannot share the live map on port {port} (UDP and TCP): {ex.SocketErrorCode}"
            );
            return;
        }

        webRtc.ViewersChanged += OnViewersChanged;
        _webRtc = webRtc;
        _redirect = redirect;
        _config.SharingEnabled = true;

        IPAddress? address = NetworkAddresses.GetLanAddresses().FirstOrDefault();
        _snapshot =
            address == null
                ? new Snapshot(true, null, null, null)
                : new Snapshot(true, null, $"{address}:{port}", LinkFor(address, port, identity));
        _log.LogInfo(
            address == null
                ? $"Sharing the live map on port {port}, but found no network address"
                : $"Sharing the live map at {address}:{port}"
        );
    }

    private void StopServers()
    {
        if (_webRtc != null)
            _webRtc.ViewersChanged -= OnViewersChanged;
        _webRtc?.Dispose();
        _redirect?.Dispose();
        _webRtc = null;
        _redirect = null;
    }

    private void OnViewersChanged() => Changed?.Invoke();

    private static string LinkFor(IPAddress address, int port, SharingIdentity identity) =>
        $"{MapSite.MapUrl}#live={address}:{port}.{identity.IceUfrag}.{identity.IcePassword}.{identity.FingerprintHex}";

    private sealed class Snapshot(bool enabled, string? error, string? address, string? link)
    {
        public static readonly Snapshot Off = new(false, null, null, null);

        public bool Enabled { get; } = enabled;
        public string? Error { get; } = error;
        public string? Address { get; } = address;
        public string? Link { get; } = link;
    }
}
