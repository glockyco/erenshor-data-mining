using AdventureGuide.Navigation;

namespace AdventureGuide.Tests;

public sealed class GameMarkerPolicyTests
{
    [Theory]
    [InlineData(false, false, true)]
    [InlineData(true, false, false)]
    [InlineData(false, true, false)]
    [InlineData(true, true, false)]
    public void Only_unheld_uncompleted_quests_make_givers_eligible(
        bool held,
        bool completed,
        bool expected
    )
    {
        Assert.Equal(expected, GameMarkerPolicy.IsQuestAvailable(held, completed));
    }

    [Fact]
    public void Toggling_off_restores_or_spawns_and_toggling_on_hides_native_indicators()
    {
        Assert.Equal(
            GameMarkerAction.Hide,
            GameMarkerPolicy.Decide(true, true, false, true, true, true)
        );
        Assert.Equal(
            GameMarkerAction.None,
            GameMarkerPolicy.Decide(true, true, false, true, true, false)
        );
        Assert.Equal(
            GameMarkerAction.Spawn,
            GameMarkerPolicy.Decide(false, true, false, true, true, false)
        );
        Assert.Equal(
            GameMarkerAction.Restore,
            GameMarkerPolicy.Decide(false, true, false, true, true, true)
        );
    }

    [Theory]
    [InlineData(false, false, true, true)]
    [InlineData(true, true, true, true)]
    [InlineData(true, false, false, true)]
    [InlineData(true, false, true, false)]
    public void Disabled_game_markers_sims_dead_and_ineligible_npcs_never_gain_indicators(
        bool useMarkers,
        bool sim,
        bool alive,
        bool eligible
    )
    {
        Assert.Equal(
            GameMarkerAction.None,
            GameMarkerPolicy.Decide(false, useMarkers, sim, alive, eligible, false)
        );
        Assert.Equal(
            GameMarkerAction.Hide,
            GameMarkerPolicy.Decide(false, useMarkers, sim, alive, eligible, true)
        );
    }
}
