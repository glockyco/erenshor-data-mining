using System.Collections.Generic;

// Scene changes can unload referenced Item assets too. Keep only copied values.
public sealed class LootItemInputs
{
    public readonly string StableKey;
    public readonly string Name;
    public readonly bool Unique;
    public readonly string EquipmentToActivate;

    public LootItemInputs(Item item, string stableKey)
    {
        StableKey = stableKey;
        Name = item.name;
        Unique = item.Unique;
        EquipmentToActivate = item.EquipmentToActivate;
    }
}

public sealed class LootTableInputs
{
    public readonly string Name;
    public readonly List<LootItemInputs> UltraRareDrop;
    public readonly List<LootItemInputs> LegendaryDrop;
    public readonly List<LootItemInputs> RareDrop;
    public readonly List<LootItemInputs> UncommonDrop;
    public readonly List<LootItemInputs> CommonDrop;
    public readonly List<LootItemInputs> GuaranteeOneDrop;
    public readonly List<LootItemInputs> ActualDrops;
    public readonly int MaxNumberDrops;
    public readonly int MaxNonCommonDrops;
    public readonly int NumberOfGuaranteedDrops;

    public LootTableInputs(LootTable table, Dictionary<string, LootItemInputs> items)
    {
        Name = table.name;
        UltraRareDrop = CaptureItems(table.UltraRareDrop, items);
        LegendaryDrop = CaptureItems(table.LegendaryDrop, items);
        RareDrop = CaptureItems(table.RareDrop, items);
        UncommonDrop = CaptureItems(table.UncommonDrop, items);
        CommonDrop = CaptureItems(table.CommonDrop, items);
        GuaranteeOneDrop = CaptureItems(table.GuaranteeOneDrop, items);
        ActualDrops = CaptureItems(table.ActualDrops, items);
        MaxNumberDrops = table.MaxNumberDrops;
        MaxNonCommonDrops = table.MaxNonCommonDrops;
        NumberOfGuaranteedDrops = table.NumberOfGuaranteedDrops;
    }

    public static List<LootItemInputs> CaptureItems(
        IEnumerable<Item> source,
        Dictionary<string, LootItemInputs> items
    )
    {
        var result = new List<LootItemInputs>();
        if (source == null)
            return result;
        foreach (var item in source)
        {
            if (item == null)
            {
                result.Add(null);
                continue;
            }
            string key = StableKeyGenerator.ForItem(item);
            if (!items.TryGetValue(key, out var snapshot))
            {
                snapshot = new LootItemInputs(item, key);
                items.Add(key, snapshot);
            }
            result.Add(snapshot);
        }
        return result;
    }
}
