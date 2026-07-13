using AdventureGuide.Data;

namespace AdventureGuide.Tests;

internal static class TestData
{
    public static GuideData Build(params QuestEntry[] quests) =>
        GuideData.FromWrapper(new GuideWrapper { Version = 6, Quests = [.. quests] });

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
