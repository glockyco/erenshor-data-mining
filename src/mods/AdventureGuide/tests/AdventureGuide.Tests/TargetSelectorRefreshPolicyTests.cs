using AdventureGuide.Diagnostics;
using AdventureGuide.Navigation;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class TargetSelectorRefreshPolicyTests
{
    [Fact]
    public void Decide_WhenLiveWorldChanged_ReturnsForceWithLiveWorldReason()
    {
        var decision = TargetSelectorRefreshPolicy.Decide(
            liveWorldChanged: true,
            targetSourceVersion: 1,
            lastTargetSourceVersion: 1,
            navSetVersion: 1,
            lastNavSetVersion: 1);

        Assert.True(decision.Force);
        Assert.Equal(DiagnosticTrigger.LiveWorldChanged, decision.Reason);
    }

    [Fact]
    public void Decide_WhenResolutionVersionChanged_ReturnsForceWithResolutionReason()
    {
        var decision = TargetSelectorRefreshPolicy.Decide(
            liveWorldChanged: false,
            targetSourceVersion: 2,
            lastTargetSourceVersion: 1,
            navSetVersion: 1,
            lastNavSetVersion: 1);

        Assert.True(decision.Force);
        Assert.Equal(DiagnosticTrigger.TargetSourceVersionChanged, decision.Reason);
    }

    [Fact]
    public void Decide_WhenNavSetVersionChanged_ReturnsForceWithNavSetReason()
    {
        var decision = TargetSelectorRefreshPolicy.Decide(
            liveWorldChanged: false,
            targetSourceVersion: 1,
            lastTargetSourceVersion: 1,
            navSetVersion: 2,
            lastNavSetVersion: 1);

        Assert.True(decision.Force);
        Assert.Equal(DiagnosticTrigger.NavSetChanged, decision.Reason);
    }

    [Fact]
    public void Decide_WhenNothingChanged_ReturnsNoDecision()
    {
        var decision = TargetSelectorRefreshPolicy.Decide(
            liveWorldChanged: false,
            targetSourceVersion: 1,
            lastTargetSourceVersion: 1,
            navSetVersion: 1,
            lastNavSetVersion: 1);

        Assert.False(decision.Force);
        Assert.Equal(DiagnosticTrigger.Unknown, decision.Reason);
    }
}
