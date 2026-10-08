using AdventureGuide.State;

namespace AdventureGuide.Tests;

public sealed class TreasureHuntTests
{
    [Fact]
    public void Hunt_routes_to_zone_then_known_position_then_clears()
    {
        var state = new TreasureHuntState();
        Assert.Equal(TreasureHuntChange.None, state.Observe(null, 0, 0, 0));
        Assert.False(state.Active);
        Assert.False(state.HasLocation);
        Assert.Equal(TreasureHuntChange.Started, state.Observe("DigZone", 0, 0, 0));
        Assert.True(state.Active);
        Assert.Equal("DigZone", state.Scene);
        Assert.False(state.HasLocation);
        Assert.Equal(TreasureHuntChange.None, state.Observe("DigZone", 0, 0, 0));
        Assert.Equal(TreasureHuntChange.Updated, state.Observe("DigZone", 12, 3, -5));
        Assert.True(state.HasLocation);
        Assert.Equal((12f, 3f, -5f), (state.X, state.Y, state.Z));
        Assert.Equal(TreasureHuntChange.None, state.Observe("DigZone", 12, 3, -5));
        Assert.Equal(TreasureHuntChange.Ended, state.Observe("", 0, 0, 0));
        Assert.False(state.Active);
        Assert.False(state.HasLocation);
        Assert.Equal("", state.Scene);
        Assert.Equal((0f, 0f, 0f), (state.X, state.Y, state.Z));
        Assert.Equal(TreasureHuntChange.None, state.Observe("", 0, 0, 0));
    }

    [Fact]
    public void A_map_read_in_its_destination_starts_with_a_known_location()
    {
        var state = new TreasureHuntState();
        Assert.Equal(TreasureHuntChange.Started, state.Observe("Here", 1, 0, 0));
        Assert.True(state.HasLocation);
    }

    [Theory]
    [InlineData(1, 0, 0)]
    [InlineData(0, -1, 0)]
    [InlineData(0, 0, 1)]
    public void Any_nonzero_axis_is_a_known_location(float x, float y, float z)
    {
        var state = new TreasureHuntState();
        state.Observe("Here", x, y, z);
        Assert.True(state.HasLocation);
    }

    [Fact]
    public void Replacing_hunt_routes_to_the_new_zone_not_the_previous_position()
    {
        var state = new TreasureHuntState();
        state.Observe("First", 1, 2, 3);
        Assert.Equal(TreasureHuntChange.Started, state.Observe("Second", 0, 0, 0));
        Assert.Equal("Second", state.Scene);
        Assert.False(state.HasLocation);
    }

    [Fact]
    public void Empty_zone_discards_stale_coordinates_on_end_or_runtime_stop()
    {
        var state = new TreasureHuntState();
        state.Observe("Here", 1, 2, 3);
        Assert.Equal(TreasureHuntChange.Ended, state.Observe(null, 1, 2, 3));
        Assert.False(state.HasLocation);
        Assert.Equal((0f, 0f, 0f), (state.X, state.Y, state.Z));
    }
}
