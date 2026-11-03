using System.Net;
using System.Net.Sockets;
using InteractiveMapCompanion.Config;
using InteractiveMapCompanion.Server;
using UnityEngine;
using Xunit;

namespace InteractiveMapCompanion.Tests.Server;

public class LiveSharingTests
{
    [Fact]
    public void SharingStaysOnWithTheSameCredentialsAfterARestart()
    {
        var config = new FakeConfig(FreeSharingPort() - 1);
        using (var sharing = new LiveSharing(config, new NullLogger(), () => null))
        {
            sharing.SetEnabled(true);
            Assert.True(sharing.Enabled);
        }

        Assert.True(config.SharingEnabled);
        string identity = config.SharingIdentity;
        Assert.NotEmpty(identity);

        using var restarted = new LiveSharing(config, new NullLogger(), () => null);
        restarted.Restore();

        Assert.True(restarted.Enabled);
        Assert.Equal(identity, config.SharingIdentity);
    }

    [Fact]
    public void StoppingSharingRetiresTheCredentialsOfEarlierLinks()
    {
        var config = new FakeConfig(FreeSharingPort() - 1);
        using var sharing = new LiveSharing(config, new NullLogger(), () => null);
        sharing.SetEnabled(true);
        string first = config.SharingIdentity;

        sharing.SetEnabled(false);

        Assert.False(sharing.Enabled);
        Assert.False(config.SharingEnabled);
        Assert.Empty(config.SharingIdentity);

        sharing.SetEnabled(true);

        Assert.NotEmpty(config.SharingIdentity);
        Assert.NotEqual(first, config.SharingIdentity);
    }

    [Fact]
    public void ATakenPortTurnsSharingOffAndSaysWhy()
    {
        int port = FreeSharingPort();
        using var occupant = new UdpClient(new IPEndPoint(IPAddress.Any, port));
        var config = new FakeConfig(port - 1);
        using var sharing = new LiveSharing(config, new NullLogger(), () => null);
        int changes = 0;
        sharing.Changed += () => changes++;

        sharing.SetEnabled(true);

        Assert.False(sharing.Enabled);
        Assert.Equal(LiveSharing.PortUnavailableError, sharing.Error);
        Assert.False(config.SharingEnabled);
        Assert.Equal(1, changes);
    }

    [Fact]
    public void ALinkOpensTheMapWithTheAddressAndPortToPairWith()
    {
        var config = new FakeConfig(FreeSharingPort() - 1);
        using var sharing = new LiveSharing(config, new NullLogger(), () => null);

        sharing.SetEnabled(true);

        // Hosts without a private IPv4 address have nothing to link to.
        if (sharing.Address == null)
            return;
        Assert.EndsWith($":{config.Port + 1}", sharing.Address);
        Assert.StartsWith(
            $"https://erenshor.compendiums.org/map#live={sharing.Address}.",
            sharing.Link
        );
    }

    /// <summary>
    /// A port free for both UDP and TCP, as sharing needs both.
    /// </summary>
    private static int FreeSharingPort()
    {
        for (int attempt = 0; attempt < 20; attempt++)
        {
            using var udp = new UdpClient(new IPEndPoint(IPAddress.Any, 0));
            int port = ((IPEndPoint)udp.Client.LocalEndPoint!).Port;
            var tcp = new TcpListener(IPAddress.Any, port);
            try
            {
                tcp.Start();
                return port;
            }
            catch (SocketException)
            {
                // Taken for TCP; try another.
            }
            finally
            {
                tcp.Stop();
            }
        }
        throw new InvalidOperationException("No port is free for both UDP and TCP");
    }

    private sealed class NullLogger : IModLogger
    {
        public void LogDebug(string message) { }

        public void LogInfo(string message) { }

        public void LogWarning(string message) { }

        public void LogError(string message) { }
    }

    private sealed class FakeConfig(int port) : IModConfig
    {
        public int Port { get; } = port;
        public int UpdateInterval => 100;
        public Config.LogLevel WebSocketLogLevel => Config.LogLevel.Warning;
        public Config.LogLevel ModLogLevel => Config.LogLevel.Info;
        public bool EnableOverlay => false;
        public KeyCode ToggleKey => KeyCode.None;
        public float AnchorX { get; set; }
        public float AnchorY { get; set; }
        public int OverlayWidth { get; set; }
        public int OverlayHeight { get; set; }
        public bool ResetToDefaults { get; set; }
        public bool SharingEnabled { get; set; }
        public string SharingIdentity { get; set; } = "";

        public string[] GetCapabilities() => ["entities"];
    }
}
