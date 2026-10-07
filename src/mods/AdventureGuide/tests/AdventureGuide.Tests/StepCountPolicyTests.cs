using AdventureGuide.Data;
using AdventureGuide.UI;

namespace AdventureGuide.Tests;

public sealed class StepCountPolicyTests
{
    [Theory]
    [InlineData("kill", false)]
    [InlineData("talk", false)]
    [InlineData("collect", true)]
    [InlineData("obtain", true)]
    public void Only_inventory_objectives_show_have_need_counts(string action, bool expected) =>
        Assert.Equal(
            expected,
            StepCountPolicy.ShowsInventoryCount(
                new QuestStep
                {
                    Action = action,
                    TargetKey = "target",
                    Quantity = 2,
                }
            )
        );

    [Fact]
    public void Incomplete_inventory_objectives_do_not_show_counts()
    {
        Assert.False(
            StepCountPolicy.ShowsInventoryCount(new QuestStep { Action = "collect", Quantity = 2 })
        );
        Assert.False(
            StepCountPolicy.ShowsInventoryCount(
                new QuestStep { Action = "obtain", TargetKey = "item:fee" }
            )
        );
    }
}
