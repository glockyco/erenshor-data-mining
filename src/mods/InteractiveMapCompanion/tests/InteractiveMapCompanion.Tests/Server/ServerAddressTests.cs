using InteractiveMapCompanion.Server;
using Xunit;

namespace InteractiveMapCompanion.Tests.Server;

public class ServerAddressTests
{
    [Theory]
    [InlineData(false, 18585, "ws://127.0.0.1:18585")]
    [InlineData(true, 18585, "ws://0.0.0.0:18585")]
    [InlineData(false, 19000, "ws://127.0.0.1:19000")]
    [InlineData(true, 19000, "ws://0.0.0.0:19000")]
    public void GetLocation_OnlyAllowsLanConnectionsWhenEnabled(
        bool allowLanConnections,
        int port,
        string expected
    )
    {
        Assert.Equal(expected, ServerAddress.GetLocation(port, allowLanConnections));
    }
}
