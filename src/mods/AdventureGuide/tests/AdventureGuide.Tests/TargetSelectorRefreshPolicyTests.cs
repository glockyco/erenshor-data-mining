using AdventureGuide.Navigation;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class TargetSelectorRefreshPolicyTests
{
    [Fact]
    public void ShouldForce_WhenLiveWorldChanged_ReturnsTrue()
    {
        bool force = TargetSelectorRefreshPolicy.ShouldForce(
            liveWorldChanged: true,
            resolutionVersion: 1,
            lastResolutionVersion: 1,
            navSetVersion: 1,
            lastNavSetVersion: 1);

        Assert.True(force);
    }

    [Fact]
    public void ShouldForce_WhenResolutionVersionChanged_ReturnsTrue()
    {
        bool force = TargetSelectorRefreshPolicy.ShouldForce(
            liveWorldChanged: false,
            resolutionVersion: 2,
            lastResolutionVersion: 1,
            navSetVersion: 1,
            lastNavSetVersion: 1);

        Assert.True(force);
    }

    [Fact]
    public void ShouldForce_WhenNavSetVersionChanged_ReturnsTrue()
    {
        bool force = TargetSelectorRefreshPolicy.ShouldForce(
            liveWorldChanged: false,
            resolutionVersion: 1,
            lastResolutionVersion: 1,
            navSetVersion: 2,
            lastNavSetVersion: 1);

        Assert.True(force);
    }

    [Fact]
    public void ShouldForce_WhenNothingChanged_ReturnsFalse()
    {
        bool force = TargetSelectorRefreshPolicy.ShouldForce(
            liveWorldChanged: false,
            resolutionVersion: 1,
            lastResolutionVersion: 1,
            navSetVersion: 1,
            lastNavSetVersion: 1);

        Assert.False(force);
    }
}
