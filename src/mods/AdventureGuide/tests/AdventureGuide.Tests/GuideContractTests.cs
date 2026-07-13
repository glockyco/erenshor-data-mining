using AdventureGuide.Data;
using AdventureGuide.Navigation;
using AdventureGuide.State;
using UnityEngine;

namespace AdventureGuide.Tests;

public sealed class GuideContractTests
{
    [Fact]
    public void Validation_rejects_cross_namespace_quest_identity_collisions()
    {
        var wrapper = new GuideWrapper
        {
            Version = 6,
            Quests =
            [
                OrdinaryQuest("quest:first", "FirstDB"),
                OrdinaryQuest("FirstDB", "SecondDB"),
            ],
        };

        var error = Assert.Throws<InvalidDataException>(() => GuideData.ValidateWrapper(wrapper));
        Assert.Contains("identity collides", error.Message);
    }

    [Fact]
    public void Vendor_instruction_is_generic_and_seller_gate_is_structured()
    {
        var workflow = TestData.WorkflowQuest();
        workflow.RequiredItems =
        [
            new RequiredItemInfo
            {
                ItemName = "Test Token",
                ItemStableKey = "item:test token",
                Sources =
                [
                    new ItemSource
                    {
                        Type = "vendor",
                        Name = "Seller",
                        SourceKey = "character:seller",
                        Instruction = "Buy Test Token.",
                        RequiredQuestDBNames = ["GateQuest"],
                    },
                ],
            },
        ];
        var wrapper = new GuideWrapper
        {
            Version = 6,
            Quests = [OrdinaryQuest("quest:gate", "GateQuest"), workflow],
        };

        GuideData.ValidateWrapper(wrapper);

        workflow.RequiredItems[0].Sources![0].Instruction = "Buy Test Token from Seller.";
        Assert.Throws<InvalidDataException>(() => GuideData.ValidateWrapper(wrapper));
    }

    [Fact]
    public void Guide_only_progress_never_mutates_game_quest_collections()
    {
        var workflow = TestData.WorkflowQuest();
        var data = TestData.Build(workflow);
        var game = new TestQuestGameState { PlayerPosition = new Vector3(10f, 2f, 20f) };
        game.ActiveQuests.Add("RealActiveQuest");
        game.CompletedQuests.Add("RealCompletedQuest");
        game.Inventory["item:test token"] = 1;
        var state = new QuestStateTracker(data, new EntityRegistry(), game);
        state.OnSceneChanged("TestScene");

        game.Inventory.Remove("item:test token");
        state.OnInventoryChanged();

        Assert.True(game.ActiveQuests.SetEquals(["RealActiveQuest"]));
        Assert.True(game.CompletedQuests.SetEquals(["RealCompletedQuest"]));
        Assert.DoesNotContain(workflow.DBName, game.ActiveQuests);
        Assert.DoesNotContain(workflow.DBName, game.CompletedQuests);
        Assert.Equal(QuestRuntimeStatus.Active, state.GetStatus(workflow));

        state.OnSceneChanged("Elsewhere");
        Assert.Equal(QuestRuntimeStatus.Available, state.GetStatus(workflow));
        Assert.False(state.IsActionable(workflow));
    }

    [Fact]
    public void Completed_repeatable_quests_remain_tracked()
    {
        var repeatable = OrdinaryQuest("quest:repeat", "RepeatDB", repeatable: true);
        var oneShot = OrdinaryQuest("quest:once", "OnceDB");
        var data = TestData.Build(repeatable, oneShot);
        var state = new QuestStateTracker(data, new EntityRegistry(), new TestQuestGameState());
        var tracker = new TrackerState();
        tracker.Track(repeatable.RuntimeKey);
        tracker.Track(oneShot.RuntimeKey);
        state.OnQuestCompleted(repeatable.DBName);
        state.OnQuestCompleted(oneShot.DBName);

        tracker.PruneCompleted(state, data);

        Assert.True(tracker.IsTracked(repeatable.RuntimeKey));
        Assert.False(tracker.IsTracked(oneShot.RuntimeKey));
    }

    private static QuestEntry OrdinaryQuest(
        string stableKey,
        string dbName,
        bool repeatable = false
    ) =>
        new()
        {
            StableKey = stableKey,
            DBName = dbName,
            DisplayName = dbName,
            Flags = new QuestFlags { Repeatable = repeatable },
        };
}
