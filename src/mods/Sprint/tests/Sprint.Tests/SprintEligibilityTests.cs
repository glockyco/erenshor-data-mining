using Sprint.Core;
using Xunit;

namespace Sprint.Tests;

public sealed class SprintEligibilityTests
{
    [Fact]
    public void IsPlayer_uses_reference_identity_not_value_equality()
    {
        var player = new PlayerToken(7);
        var equalButDifferent = new PlayerToken(7);

        Assert.True(SprintEligibility.IsPlayer(player, player));
        Assert.False(SprintEligibility.IsPlayer(player, equalButDifferent));
    }

    [Fact]
    public void IsPlayer_rejects_a_null_player()
    {
        var candidate = new PlayerToken(7);

        Assert.False(SprintEligibility.IsPlayer<PlayerToken>(null, candidate));
    }

    [Theory]
    [InlineData(false, true)]
    [InlineData(true, false)]
    public void IsActiveFor_rejects_inactive_or_stopped_sprint(bool started, bool active)
    {
        var player = new PlayerToken(7);

        Assert.False(SprintEligibility.IsActiveFor(started, active, player, player));
    }

    [Fact]
    public void IsActiveFor_accepts_only_the_started_active_player()
    {
        var player = new PlayerToken(7);
        var equalButDifferent = new PlayerToken(7);

        Assert.True(SprintEligibility.IsActiveFor(true, true, player, player));
        Assert.False(SprintEligibility.IsActiveFor(true, true, player, equalButDifferent));
        Assert.False(SprintEligibility.IsActiveFor<PlayerToken>(true, true, null, player));
    }

    private sealed class PlayerToken
    {
        private readonly int _id;

        public PlayerToken(int id) => _id = id;

        public override bool Equals(object? obj) => obj is PlayerToken other && other._id == _id;

        public override int GetHashCode() => _id;
    }
}
