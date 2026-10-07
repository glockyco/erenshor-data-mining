using AdventureGuide.Navigation;

namespace AdventureGuide.Tests;

public sealed class ZoneArrivalTests
{
    [Fact]
    public void Destination_target_stops_routing_on_arrival_and_routes_again_after_leaving()
    {
        const string destination = "Hidden";
        Assert.True(NavigationPolicy.IsCrossZone(destination, "Stowaway"));
        Assert.False(NavigationPolicy.IsCrossZone(destination, "Hidden"));
        Assert.False(NavigationPolicy.IsCrossZone(destination, "hidden"));
        Assert.True(NavigationPolicy.IsCrossZone(destination, "Stowaway"));
    }
}
