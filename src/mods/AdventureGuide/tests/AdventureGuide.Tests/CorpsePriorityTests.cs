using AdventureGuide.Data;
using AdventureGuide.Navigation;

namespace AdventureGuide.Tests;

public sealed class CorpsePriorityTests
{
    private readonly QuestEntry _quest = new()
    {
        RequiredItems =
        [
            new RequiredItemInfo
            {
                ItemName = "Fire Shard",
                ItemStableKey = "item:fire",
                Quantity = 2,
            },
            new RequiredItemInfo
            {
                ItemName = "Water Shard",
                ItemStableKey = "item:water",
                Quantity = 1,
            },
        ],
    };
    private readonly HashSet<string> _items = new(StringComparer.OrdinalIgnoreCase);

    [Fact]
    public void Item_step_only_prioritizes_its_item()
    {
        CorpsePriorityPolicy.FillItems(
            new QuestStep
            {
                Action = "collect",
                TargetType = "item",
                TargetName = "Fire Shard",
            },
            _quest,
            _ => 0,
            _items
        );
        Assert.Equal(["Fire Shard"], _items);
        Assert.DoesNotContain("Water Shard", _items);
    }

    [Theory]
    [InlineData("talk")]
    [InlineData("kill")]
    [InlineData("turn_in")]
    public void Non_loot_actions_clear_prior_priority(string action)
    {
        _items.Add("Fire Shard");
        CorpsePriorityPolicy.FillItems(
            new QuestStep { Action = action, TargetType = "character" },
            _quest,
            _ => 0,
            _items
        );
        Assert.Empty(_items);
    }

    [Fact]
    public void Loot_step_prioritizes_only_missing_items_and_updates_after_inventory_change()
    {
        var step = new QuestStep { Action = "loot", TargetType = "character" };
        CorpsePriorityPolicy.FillItems(step, _quest, key => key == "item:water" ? 1 : 0, _items);
        Assert.Equal(["Fire Shard"], _items);
        CorpsePriorityPolicy.FillItems(step, _quest, _ => 2, _items);
        Assert.Empty(_items);
    }

    [Fact]
    public void Missing_resolved_step_clears_priority_without_reading_inventory()
    {
        _items.Add("Fire Shard");
        CorpsePriorityPolicy.FillItems(
            null,
            _quest,
            _ => throw new InvalidOperationException(),
            _items
        );
        Assert.Empty(_items);
    }

    [Theory]
    [InlineData(1, 1, 0, 0, false)]
    [InlineData(0, 0, 1, 1, false)]
    [InlineData(1, 0, 0, 1, true)]
    public void Loot_priority_never_combines_partial_native_bundles(
        int a,
        int b,
        int c,
        int d,
        bool partial
    )
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
        quest.RequiredItems![2].Sources =
        [
            new ItemSource
            {
                Type = "item_use",
                SourceKey = "item:bag",
                Name = "Bag",
            },
        ];
        int Count(string key) =>
            key switch
            {
                "item:a" => a,
                "item:b" => b,
                "item:c" => c,
                "item:d" => d,
                _ => 0,
            };

        CorpsePriorityPolicy.FillItems(new QuestStep { Action = "loot" }, quest, Count, _items);

        if (partial)
            Assert.True(_items.SetEquals(["item:b", "item:c", "Bag", "item:token"]));
        else
            Assert.Equal(["item:token"], _items);
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
        CorpsePriorityPolicy.FillItems(new QuestStep { Action = "loot" }, quest, _ => held, _items);
        Assert.Equal(needed, _items.Contains("item:runner"));
        Assert.Equal(needed ? 1 : 0, _items.Count);
    }

    [Fact]
    public void Authored_or_completion_does_not_suppress_unconditional_loot()
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
        CorpsePriorityPolicy.FillItems(
            new QuestStep { Action = "loot" },
            quest,
            key => key == "red" ? 1 : 0,
            _items
        );
        Assert.Equal(["Token"], _items);
    }
}
