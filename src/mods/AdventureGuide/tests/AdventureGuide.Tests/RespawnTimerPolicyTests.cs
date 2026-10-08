using AdventureGuide.Navigation;

namespace AdventureGuide.Tests;

public sealed class RespawnTimerPolicyTests
{
    private const int Boss = (int)SpawnTiers.Boss;
    private const int Elite = (int)SpawnTiers.Elite;

    [Theory]
    [InlineData(false, false, false, Boss, false)]
    [InlineData(false, true, false, Boss, true)]
    [InlineData(false, true, false, Elite, false)]
    [InlineData(false, false, true, Elite, true)]
    [InlineData(false, false, true, Boss | Elite, true)]
    [InlineData(false, true, true, 0, false)]
    [InlineData(true, false, false, 0, true)]
    public void Timer_shows_for_the_selected_spawn_points(
        bool showAll,
        bool showBosses,
        bool showElites,
        int tiers,
        bool expected
    ) =>
        Assert.Equal(
            expected,
            RespawnTimerPolicy.Shows(showAll, showBosses, showElites, (SpawnTiers)tiers)
        );
}
