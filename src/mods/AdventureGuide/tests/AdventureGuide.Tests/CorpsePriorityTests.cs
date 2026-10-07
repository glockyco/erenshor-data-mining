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
}
