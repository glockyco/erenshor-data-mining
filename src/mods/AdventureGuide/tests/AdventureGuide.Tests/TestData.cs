using AdventureGuide.Data;

namespace AdventureGuide.Tests;

internal static class TestData
{
    public static GuideData Build(params QuestEntry[] quests) =>
        GuideData.FromWrapper(
            new GuideWrapper
            {
                Version = 8,
                Encounters = EmptyEncounters(),
                Quests = [.. quests],
            }
        );

    public static EncounterContext EmptyEncounters() =>
        new()
        {
            Placements = [],
            Conditions = [],
            Completions = [],
            EventConditions = [],
        };

    public static GuideWrapper NativeRequirements(
        params (string Item, string? Variant, int[] Slots)[] requirements
    )
    {
        var quest = new QuestEntry
        {
            StableKey = "quest:native",
            DBName = "NATIVE",
            DisplayName = "Native requirements",
            RequiredItems = [],
            Steps = [],
        };
        var wrapper = new GuideWrapper
        {
            Version = 8,
            Encounters = EmptyEncounters(),
            ZoneLineDestinationContexts = [],
            Quests = [quest],
        };
        int slot = 0;
        foreach (var (item, variant, quantities) in requirements)
        {
            var keys = new List<string>();
            foreach (int quantity in quantities)
            {
                string key = $"use:native:{slot}";
                keys.Add(key);
                wrapper.ItemUses!.Add(
                    key,
                    new ItemUseFact
                    {
                        UseKey = key,
                        ItemStableKey = item,
                        TargetStableKey = quest.StableKey,
                        Kind = "quest_requirement",
                        VariantKey = variant,
                        MaterialSlot = slot++,
                        QuantityKind = "exact",
                        QuantityMin = quantity,
                        QuantityMax = quantity,
                    }
                );
            }
            quest.RequiredItems.Add(
                new RequiredItemInfo
                {
                    ItemName = item,
                    ItemStableKey = item,
                    VariantKey = variant,
                    Quantity = quantities.Sum(),
                    UseKeys = keys,
                }
            );
            quest.Steps.Add(
                new QuestStep
                {
                    Order = quest.Steps.Count + 1,
                    Action = "collect",
                    Description = $"Collect {item}.",
                    TargetName = item,
                    TargetKey = item,
                    TargetType = "item",
                    Quantity = quantities.Sum(),
                    RequirementVariant = variant,
                }
            );
        }
        quest.Steps.Add(
            new QuestStep
            {
                Order = quest.Steps.Count + 1,
                Action = "turn_in",
                Description = "Turn in the requirements.",
            }
        );
        return wrapper;
    }
}
