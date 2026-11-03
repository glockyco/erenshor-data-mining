using System.Net;
using System.Net.NetworkInformation;
using System.Net.Sockets;

namespace InteractiveMapCompanion.Server.WebRtc;

/// <summary>
/// Finds the addresses other devices on the same network can reach this PC at.
/// </summary>
internal static class NetworkAddresses
{
    /// <summary>
    /// Private IPv4 addresses of interfaces that are up, best first. Interfaces with a
    /// default gateway lead, because that is the network a phone joins, while virtual
    /// adapters for VMs and WSL usually have none.
    /// </summary>
    public static IReadOnlyList<IPAddress> GetLanAddresses()
    {
        var candidates = new List<(IPAddress Address, bool HasGateway)>();
        try
        {
            foreach (var networkInterface in NetworkInterface.GetAllNetworkInterfaces())
            {
                if (
                    networkInterface.OperationalStatus != OperationalStatus.Up
                    || networkInterface.NetworkInterfaceType == NetworkInterfaceType.Loopback
                )
                    continue;

                var properties = networkInterface.GetIPProperties();
                bool hasGateway = HasIPv4Gateway(properties);
                foreach (var unicast in properties.UnicastAddresses)
                {
                    var address = unicast.Address;
                    if (address.AddressFamily == AddressFamily.InterNetwork && IsPrivate(address))
                        candidates.Add((address, hasGateway));
                }
            }
        }
        catch (Exception)
        {
            // Unity's Mono under Wine fails here in runtime-specific ways; sharing then
            // shows no address and the typed-address hint stays empty.
        }

        return candidates
            .OrderByDescending(candidate => candidate.HasGateway)
            .ThenBy(candidate => RangeRank(candidate.Address))
            .Select(candidate => candidate.Address)
            .Distinct()
            .ToList();
    }

    private static bool HasIPv4Gateway(IPInterfaceProperties properties)
    {
        try
        {
            return properties.GatewayAddresses.Any(gateway =>
                gateway.Address.AddressFamily == AddressFamily.InterNetwork
                && !gateway.Address.Equals(IPAddress.Any)
            );
        }
        catch (Exception)
        {
            return false;
        }
    }

    private static bool IsPrivate(IPAddress address) => RangeRank(address) < 3;

    /// <summary>
    /// Home networks mostly use 192.168/16, then 10/8, then 172.16/12, where Docker and
    /// WSL also put their virtual networks.
    /// </summary>
    private static int RangeRank(IPAddress address)
    {
        byte[] b = address.GetAddressBytes();
        if (b[0] == 192 && b[1] == 168)
            return 0;
        if (b[0] == 10)
            return 1;
        if (b[0] == 172 && b[1] >= 16 && b[1] <= 31)
            return 2;
        return 3;
    }
}
