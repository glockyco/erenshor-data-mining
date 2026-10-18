using AdventureGuide.Data;
using AdventureGuide.State;

namespace AdventureGuide.Tests;

public sealed class MissingRequirementTests
{
    private static List<string> Missing(QuestEntry quest, Func<string, int> countItem)
    {
        var keys = new List<string>();
        var missing = StepProgress.MissingRequirements(quest, countItem);
        while (missing.MoveNext())
            keys.Add(missing.Current.ItemStableKey);
        return keys;
    }

    [Fact]
    public void Only_items_short_of_their_quantity_are_missing_and_follow_the_inventory()
    {
        var quest = new QuestEntry
        {
            RequiredItems =
            [
                new()
                {
                    ItemName = "Fire Shard",
                    ItemStableKey = "item:fire",
                    Quantity = 2,
                },
                new()
                {
                    ItemName = "Water Shard",
                    ItemStableKey = "item:water",
                    Quantity = 1,
                },
            ],
        };
        Assert.Equal(["item:fire"], Missing(quest, key => key == "item:water" ? 1 : 0));
        Assert.Empty(Missing(quest, _ => 2));
    }

    [Theory]
    [InlineData(1, 1, 0, 0, false)]
    [InlineData(0, 0, 1, 1, false)]
    [InlineData(1, 0, 0, 1, true)]
    public void Partial_native_bundles_never_combine(int a, int b, int c, int d, bool partial)
    {
        var quest = TestData
            .NativeRequirements(
                ("item:a", "A", [1]),
                ("item:b", "A", [1]),
                ("item:c", "B", [1]),
                ("item:d", "B", [1]),
                ("item:token", null, [1])
            )
            .Quests![0];
        int Count(string key) =>
            key switch
            {
                "item:a" => a,
                "item:b" => b,
                "item:c" => c,
                "item:d" => d,
                _ => 0,
            };

        var missing = Missing(quest, Count);

        if (partial)
            Assert.Equal(["item:b", "item:c", "item:token"], missing);
        else
            Assert.Equal(["item:token"], missing);
    }

    [Theory]
    [InlineData(0, true)]
    [InlineData(1, true)]
    [InlineData(2, false)]
    [InlineData(3, false)]
    [InlineData(4, false)]
    public void Repeated_item_alternatives_use_one_inventory_without_summing_bundles(
        int held,
        bool needed
    )
    {
        var quest = TestData
            .NativeRequirements(("item:runner", "A", [1, 3]), ("item:runner", "B", [2]))
            .Quests![0];
        Assert.Equal(needed ? ["item:runner"] : [], Missing(quest, _ => held).Distinct());
    }

    [Fact]
    public void An_authored_or_completion_does_not_suppress_an_unconditional_item()
    {
        var quest = new QuestEntry
        {
            RequiredItems =
            [
                new()
                {
                    ItemName = "Red",
                    ItemStableKey = "red",
                    OrGroup = "color",
                    Quantity = 1,
                },
                new()
                {
                    ItemName = "Blue",
                    ItemStableKey = "blue",
                    OrGroup = "color",
                    Quantity = 1,
                },
                new()
                {
                    ItemName = "Token",
                    ItemStableKey = "token",
                    Quantity = 1,
                },
            ],
        };
        Assert.Equal(["token"], Missing(quest, key => key == "red" ? 1 : 0));
    }
}
