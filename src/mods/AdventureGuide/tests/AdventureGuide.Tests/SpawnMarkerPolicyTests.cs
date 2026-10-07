using AdventureGuide.Navigation;

namespace AdventureGuide.Tests;

public sealed class SpawnMarkerPolicyTests
{
    [Theory]
    [InlineData(3, MarkerType.DeadSpawn)]
    [InlineData(4, MarkerType.NightSpawn)]
    [InlineData(7, MarkerType.NightSpawn)]
    [InlineData(22, MarkerType.NightSpawn)]
    [InlineData(23, MarkerType.DeadSpawn)]
    public void Lost_night_target_uses_the_spawn_window_not_the_reset_timer(
        int hour,
        MarkerType expected
    )
    {
        var facts = new SpawnPointFacts(false, false, true, false, true, hour, true);
        Assert.Equal(
            expected,
            SpawnMarkerPolicy.TypeWhenTargetLost(SpawnPointPolicy.Classify(facts))
        );
    }

    [Theory]
    [InlineData(2)]
    [InlineData(4)]
    [InlineData(1)]
    [InlineData(0)]
    public void Non_respawning_phases_do_not_claim_a_countdown(int phase)
    {
        Assert.Null(SpawnMarkerPolicy.TypeWhenTargetLost((SpawnPointPhase)phase));
    }

    [Fact]
    public void Ordinary_death_still_shows_a_clock()
    {
        var facts = new SpawnPointFacts(false, false, true, false, false, 7, true);
        Assert.Equal(
            MarkerType.DeadSpawn,
            SpawnMarkerPolicy.TypeWhenTargetLost(SpawnPointPolicy.Classify(facts))
        );
    }

    [Theory]
    [InlineData(-1, 20, false)]
    [InlineData(20, 20, false)]
    [InlineData(20, 21, true)]
    [InlineData(20, 25, true)]
    public void Reset_rebuild_waits_until_deferred_destruction_finishes(
        int resetFrame,
        int currentFrame,
        bool expected
    )
    {
        Assert.Equal(expected, SpawnMarkerPolicy.ResetReady(resetFrame, currentFrame));
    }
}
