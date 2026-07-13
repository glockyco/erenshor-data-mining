using AdventureGuide.Data;
using AdventureGuide.Navigation;
using AdventureGuide.State;
using AdventureGuide.UI;
using UnityEngine;

namespace AdventureGuide.Tests;

public sealed class TrackerSorterTests
{
    [Fact]
    public void Fixed_position_step_reports_real_same_zone_distance()
    {
        var quest = new QuestEntry
        {
            StableKey = "quest:position",
            DBName = "PositionQuest",
            DisplayName = "Position quest",
            Steps =
            [
                new QuestStep
                {
                    Order = 1,
                    Action = "go_to",
                    Description = "Go to the point.",
                    TargetName = "The point",
                    TargetType = "location",
                    TargetKey = "guide-location:point",
                    Location = new WorkflowLocation
                    {
                        StableKey = "guide-location:point",
                        DisplayName = "The point",
                        Scene = "TestScene",
                        X = 3f,
                        Y = 0f,
                        Z = 4f,
                    },
                },
            ],
        };
        var data = TestData.Build(quest);
        var entities = new EntityRegistry();
        var state = new QuestStateTracker(data, entities, new TestQuestGameState());
        state.OnSceneChanged("TestScene");
        state.OnQuestAssigned(quest.DBName);
        var distances = new Dictionary<string, StepDistance>();

        TrackerSorter.ComputeDistances(
            [quest.RuntimeKey],
            data,
            state,
            navigationTarget: null,
            navigationDistance: 0f,
            playerPos: Vector3.zero,
            output: distances
        );

        var step = quest.Steps[0];
        var target = NavigationController.CreateFixedPositionTarget(
            step,
            quest,
            quest.RuntimeKey,
            step.Order
        );
        Assert.Equal(NavigationTarget.Kind.Position, target.TargetKind);
        Assert.Equal(new Vector3(3f, 0f, 4f), target.Position);
        Assert.Equal("TestScene", target.Scene);
        Assert.Equal("guide-location:point", target.SourceId);

        Assert.True(distances[quest.RuntimeKey].InCurrentZone);
        Assert.Equal(5f, distances[quest.RuntimeKey].Meters, 3);
    }
}
