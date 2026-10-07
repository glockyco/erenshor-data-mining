using AdventureGuide.Patches;

namespace AdventureGuide.Tests;

public sealed class DeathObservationPolicyTests
{
    [Fact]
    public void SurvivalDoesNotRemoveLivingNpcOrCreditAKill() =>
        Assert.False(DeathObservationPolicy.ShouldObserve(aliveAfterDoDeath: true));

    [Fact]
    public void RealDeathStillReachesDeathObservers() =>
        Assert.True(DeathObservationPolicy.ShouldObserve(aliveAfterDoDeath: false));
}
