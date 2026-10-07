using AdventureGuide.Navigation;

namespace AdventureGuide.Tests;

public sealed class CrossZoneWaypointTests
{
    [Fact]
    public void Missing_waypoint_recalculates_with_a_cached_line_and_stationary_player()
    {
        Assert.True(CrossZoneWaypointPolicy.ShouldRecalculate(true, false, 0f, 100f));
        Assert.True(CrossZoneWaypointPolicy.ShouldRecalculate(false, true, 0f, 100f));
        Assert.False(CrossZoneWaypointPolicy.ShouldRecalculate(true, true, 100f, 100f));
        Assert.True(CrossZoneWaypointPolicy.ShouldRecalculate(true, true, 100.1f, 100f));
    }

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
