using System.Net;
using System.Net.Sockets;
using System.Text;
using InteractiveMapCompanion.Server.WebRtc;
using Xunit;

namespace InteractiveMapCompanion.Tests.Server;

public sealed class PairingRedirectServerTests : IDisposable
{
    private readonly PairingRedirectServer _server = new(
        address => $"https://map.example/map#live={address}:18586.ufrag.pwd.ff",
        _ => { }
    );

    public PairingRedirectServerTests() => _server.Start(0);

    public void Dispose() => _server.Dispose();

    [Fact]
    public async Task RedirectsToTheLinkForTheAddressTheRequestArrivedAt()
    {
        string response = await RequestAsync("GET / HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n");

        Assert.StartsWith("HTTP/1.1 302 ", response);
        Assert.Contains(
            "\r\nLocation: https://map.example/map#live=127.0.0.1:18586.ufrag.pwd.ff\r\n",
            response
        );
        Assert.Contains("\r\nCache-Control: no-store\r\n", response);
    }

    [Fact]
    public async Task IgnoresTheQueryString()
    {
        string response = await RequestAsync("GET /?from=qr HTTP/1.1\r\nHost: x\r\n\r\n");

        Assert.StartsWith("HTTP/1.1 302 ", response);
    }

    [Fact]
    public async Task DoesNotRedirectOtherPaths()
    {
        string response = await RequestAsync("GET /favicon.ico HTTP/1.1\r\nHost: x\r\n\r\n");

        Assert.StartsWith("HTTP/1.1 404 ", response);
        Assert.DoesNotContain("Location:", response);
    }

    [Fact]
    public async Task RefusesMethodsOtherThanGetAndHead()
    {
        string response = await RequestAsync(
            "POST / HTTP/1.1\r\nHost: x\r\nContent-Length: 0\r\n\r\n"
        );

        Assert.StartsWith("HTTP/1.1 405 ", response);
        Assert.DoesNotContain("Location:", response);
    }

    private async Task<string> RequestAsync(string request)
    {
        using var client = new TcpClient();
        await client.ConnectAsync(IPAddress.Loopback, _server.Port);
        var stream = client.GetStream();
        byte[] bytes = Encoding.ASCII.GetBytes(request);
        await stream.WriteAsync(bytes);
        using var reader = new StreamReader(stream, Encoding.ASCII);
        using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(5));
        return await reader.ReadToEndAsync(timeout.Token);
    }
}
