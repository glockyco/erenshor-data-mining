using AdventureGuide.Navigation;

namespace AdventureGuide.Tests;

public sealed class CrossZoneWaypointTests
{
    [Fact]
    public void Leaving_and_returning_resets_waypoint_even_at_same_position()
    {
        Assert.True(CrossZoneWaypointPolicy.SceneChanged("Hidden", "Stowaway"));
        Assert.True(CrossZoneWaypointPolicy.SceneChanged("Stowaway", "Hidden"));
        Assert.True(CrossZoneWaypointPolicy.ShouldRebuild(false, false, false, false));
        Assert.False(CrossZoneWaypointPolicy.SceneChanged("Hidden", "hidden"));
    }

    [Fact]
    public void Same_line_is_rebuilt_when_lock_changes_but_not_every_frame()
    {
        Assert.True(CrossZoneWaypointPolicy.ShouldRebuild(true, false, true, false));
        Assert.True(CrossZoneWaypointPolicy.ShouldRebuild(true, false, false, true));
        Assert.True(CrossZoneWaypointPolicy.ShouldRebuild(true, true, false, false));
        Assert.False(CrossZoneWaypointPolicy.ShouldRebuild(true, false, true, true));
        Assert.False(CrossZoneWaypointPolicy.ShouldRebuild(true, false, false, false));
    }
}
