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

    public static QuestEntry WorkflowQuest(string stableKey = "guide-quest:test")
    {
        var location = new WorkflowLocation
        {
            StableKey = "guide-location:test",
            DisplayName = "Test arena",
            Scene = "TestScene",
            X = 10f,
            Y = 2f,
            Z = 20f,
            Bounds = new WorkflowBounds
            {
                Center = new WorkflowVector
                {
                    X = 10f,
                    Y = 2f,
                    Z = 20f,
                },
                Extents = new WorkflowVector
                {
                    X = 2f,
                    Y = 2f,
                    Z = 2f,
                },
            },
        };
        return new QuestEntry
        {
            StableKey = stableKey,
            DBName = "guide.test.synthetic",
            DisplayName = "Test workflow",
            Acceptance = "implicit",
            Flags = new QuestFlags { GuideOnly = true, Repeatable = true },
            Steps =
            [
                new QuestStep
                {
                    Order = 1,
                    Action = "obtain",
                    Description = "Obtain Test Token.",
                    TargetName = "Test Token",
                    TargetType = "item",
                    TargetKey = "item:test token",
                    Quantity = 1,
                },
                new QuestStep
                {
                    Order = 2,
                    Action = "go_to",
                    Description = "Go to Test arena.",
                    TargetName = "Test arena",
                    TargetType = "location",
                    TargetKey = location.StableKey,
                    Location = location,
                },
                new QuestStep
                {
                    Order = 3,
                    Action = "kill",
                    Description = "Defeat Test Enemy.",
                    TargetName = "Test Enemy",
                    TargetType = "character",
                    TargetKey = "character:test enemy",
                    Quantity = 1,
                },
            ],
            WorkflowCycle = new WorkflowCycle
            {
                Trigger = new WorkflowTrigger
                {
                    ItemStableKey = "item:test token",
                    ItemName = "Test Token",
                    Quantity = 1,
                    Mode = "proximity_auto_consume",
                    ConsumesItemAutomatically = true,
                    Location = location,
                },
                Targets =
                [
                    new WorkflowTarget
                    {
                        StableKey = "character:test enemy",
                        DisplayName = "Test Enemy",
                        Quantity = 1,
                    },
                ],
                ResetEvidence = "targets_defeated",
            },
        };
    }
}
