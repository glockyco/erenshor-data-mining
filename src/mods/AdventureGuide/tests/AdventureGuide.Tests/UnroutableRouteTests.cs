using AdventureGuide.Navigation;

namespace AdventureGuide.Tests;

public sealed class UnroutableRouteTests
{
    [Fact]
    public void Failed_pair_is_cached_without_poisoning_other_routes()
    {
        var memo = new UnroutableRoute();
        Assert.False(memo.Matches("Hidden", "Azynthi"));
        memo.Remember("Hidden", "Azynthi");
        for (int frame = 0; frame < 1000; frame++)
            Assert.True(memo.Matches("Hidden", "Azynthi"));
        Assert.True(memo.Matches("hidden", "azynthi"));
        Assert.False(memo.Matches("Stowaway", "Azynthi"));
        Assert.False(memo.Matches("Hidden", "Stowaway"));
        Assert.False(memo.Matches("Azynthi", "Hidden"));
        memo.Clear();
        Assert.False(memo.Matches("Hidden", "Azynthi"));
    }
}
