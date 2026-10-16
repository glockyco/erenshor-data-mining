using System.Text.Json;

// The production calculator is linked above; these are only the Unity asset surface it reads.
public class Item
{
    public string name;
    public bool Unique;
    public string EquipmentToActivate = "";

    public Item(string name) => this.name = name;
}

public static class StableKeyGenerator
{
    public static string ForItem(Item item) => item.name;
}

public class LootTable
{
    public string name = "fixture";
    public List<Item> UltraRareDrop = new();
    public List<Item> LegendaryDrop = new();
    public List<Item> RareDrop = new();
    public List<Item> UncommonDrop = new();
    public List<Item> CommonDrop = new();
    public List<Item> GuaranteeOneDrop = new();
    public List<Item> ActualDrops = new();
    public int MaxNumberDrops;
    public int MaxNonCommonDrops;
    public int NumberOfGuaranteedDrops;
}

namespace UnityEngine
{
    public static class Mathf
    {
        public static int Max(int a, int b) => Math.Max(a, b);
    }
}

public static class Program
{
    public static void Main()
    {
        var bread = new Item("Bread");
        var water = new Item("Water");
        var rare = new Item("Rare");
        var calculator = new LootTableProbabilityCalculator();
        var scenarios = new List<object>();
        void Add(string name, LootTable table, List<Item> world, bool mutate = false)
        {
            var items = new Dictionary<string, LootItemInputs>();
            var inputs = new LootTableInputs(table, items);
            var capturedWorld = LootTableInputs.CaptureItems(world, items);
            string[][] lists = new[]
            {
                inputs.UltraRareDrop,
                inputs.LegendaryDrop,
                inputs.RareDrop,
                inputs.UncommonDrop,
                inputs.CommonDrop,
            }
                .Select(list => list.Select(item => item?.Name).ToArray())
                .ToArray();
            if (mutate)
            {
                table.CommonDrop[0].name = "changed after snapshot";
                table.CommonDrop.Clear();
                table.MaxNumberDrops = 100;
                table.MaxNonCommonDrops = 100;
            }
            scenarios.Add(
                new
                {
                    name,
                    lists,
                    world = capturedWorld.Select(item => item?.Name).ToArray(),
                    rolls = Math.Max(0, inputs.MaxNumberDrops + 1),
                    cap = inputs.MaxNonCommonDrops,
                    distributions = calculator.CalculatePerItemDropCountDistributions(
                        inputs,
                        capturedWorld
                    ),
                }
            );
        }
        Add(
            "duplicates_nulls_and_combined_item",
            new LootTable
            {
                CommonDrop = new() { bread, bread, null, water },
                MaxNonCommonDrops = 0,
            },
            new() { bread, water, water, null }
        );
        Add(
            "cap_fallthrough",
            new LootTable
            {
                RareDrop = new() { rare },
                CommonDrop = new() { bread },
                MaxNumberDrops = 2,
                MaxNonCommonDrops = 1,
            },
            new() { water }
        );
        Add(
            "overlapping_tiers_do_not_consume_common_cap",
            new LootTable
            {
                UltraRareDrop = new() { bread },
                LegendaryDrop = new() { rare },
                RareDrop = new() { bread, null },
                UncommonDrop = new() { water },
                CommonDrop = new() { bread, rare },
                MaxNumberDrops = 2,
                MaxNonCommonDrops = 1,
            },
            new() { bread, water }
        );
        Add(
            "null_noncommon_consumes_cap",
            new LootTable
            {
                UncommonDrop = new() { null },
                CommonDrop = new() { bread },
                MaxNumberDrops = 1,
                MaxNonCommonDrops = 1,
            },
            new() { water, null }
        );
        Add(
            "no_common_no_world",
            new LootTable
            {
                RareDrop = new() { rare },
                MaxNumberDrops = 2,
                MaxNonCommonDrops = 1,
            },
            new() { water }
        );
        Add(
            "negative_roll_count",
            new LootTable
            {
                CommonDrop = new() { bread },
                MaxNumberDrops = -1,
            },
            new() { water }
        );
        Add(
            "snapshot_survives_source_changes",
            new LootTable
            {
                CommonDrop = new() { bread },
                MaxNumberDrops = 1,
            },
            new() { water },
            mutate: true
        );
        bread.name = "Bread";
        var fixedItems = new Dictionary<string, LootItemInputs>();
        var fixedAndGuaranteed = calculator.CalculatePerItemDropCountDistributions(
            new LootTableInputs(
                new LootTable
                {
                    CommonDrop = new() { bread },
                    ActualDrops = new() { bread },
                    GuaranteeOneDrop = new() { bread },
                    NumberOfGuaranteedDrops = 1,
                },
                fixedItems
            ),
            LootTableInputs.CaptureItems(new[] { bread }, fixedItems)
        );
        Console.WriteLine(JsonSerializer.Serialize(new { scenarios, fixedAndGuaranteed }));
    }
}
