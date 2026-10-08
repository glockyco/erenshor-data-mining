using AdventureGuide.Navigation;

namespace AdventureGuide.Tests;

public sealed class RespawnTimerPolicyTests
{
    [Theory]
    [InlineData(false, false, false, false)]
    [InlineData(false, true, true, true)]
    [InlineData(false, true, false, false)]
    [InlineData(true, false, false, true)]
    [InlineData(true, true, false, true)]
    public void Timer_shows_for_the_selected_spawn_points(
        bool showAll,
        bool showBossesAndElites,
        bool spawnsBossOrElite,
        bool expected
    ) =>
        Assert.Equal(
            expected,
            RespawnTimerPolicy.Shows(
                RespawnTimerPolicy.Scope(showAll, showBossesAndElites),
                spawnsBossOrElite
            )
        );
}
