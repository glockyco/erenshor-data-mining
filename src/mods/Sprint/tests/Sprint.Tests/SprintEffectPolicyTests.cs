using Sprint.Core;
using Xunit;

namespace Sprint.Tests;

public sealed class SprintEffectPolicyTests
{
    [Fact]
    public void Inactive_speed_restores_base_plus_status_without_multiplier()
    {
        Assert.Equal(
            7f,
            SprintEffectPolicy.CalculateActualRunSpeed(
                baseRunSpeed: 5f,
                statusEffectRunSpeed: 2f,
                active: false,
                multiplier: 3f
            )
        );
    }

    [Theory]
    [InlineData(4f, 2f, 1.5f, 9f)]
    [InlineData(4f, 2f, 2f, 12f)]
    [InlineData(4f, 2f, 0.5f, 3f)]
    public void Active_speed_applies_the_live_multiplier_to_base_and_status(
        float baseRunSpeed,
        float statusEffectRunSpeed,
        float multiplier,
        float expected
    )
    {
        Assert.Equal(
            expected,
            SprintEffectPolicy.CalculateActualRunSpeed(
                baseRunSpeed,
                statusEffectRunSpeed,
                active: true,
                multiplier: multiplier
            )
        );
    }

    [Theory]
    [InlineData(1f, 0f, false)]
    [InlineData(1.5f, 0.5f, false)]
    [InlineData(4f, -2f, true)]
    [InlineData(4f, 2f, true)]
    public void Run_speed_has_a_floor_of_two(
        float baseRunSpeed,
        float statusEffectRunSpeed,
        bool active
    )
    {
        Assert.Equal(
            2f,
            SprintEffectPolicy.CalculateActualRunSpeed(
                baseRunSpeed,
                statusEffectRunSpeed,
                active,
                multiplier: -1f
            )
        );
    }
}
