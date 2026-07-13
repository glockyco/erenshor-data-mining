using AdventureGuide.Data;
using AdventureGuide.Navigation;
using AdventureGuide.State;

namespace AdventureGuide.Tests;

public sealed class WorkflowCycleStateTests
{
    [Fact]
    public void Trigger_requires_a_consumption_delta_inside_exported_bounds()
    {
        var quest = TestData.WorkflowQuest();
        var state = new WorkflowCycleState(quest);
        int itemCount = 1;

        state.BeginScene(itemCount);
        Assert.Equal(GuideWorkflowState.WorkflowStage.ItemReady, state.Stage);
        Assert.Equal(1, state.GetCurrentStepIndex(_ => itemCount));

        itemCount = 0;
        state.ObserveInventory(itemCount, insideTrigger: false);
        Assert.Equal(GuideWorkflowState.WorkflowStage.NeedItem, state.Stage);
        Assert.Equal(0, state.GetCurrentStepIndex(_ => itemCount));

        itemCount = 1;
        state.ObserveInventory(itemCount, insideTrigger: false);
        itemCount = 0;
        state.ObserveInventory(itemCount, insideTrigger: true);

        Assert.Equal(GuideWorkflowState.WorkflowStage.TriggerConsumed, state.Stage);
        Assert.Equal(2, state.GetCurrentStepIndex(_ => itemCount));
    }

    [Fact]
    public void Reload_without_positive_runtime_evidence_becomes_unverifiable()
    {
        var quest = TestData.WorkflowQuest();
        var state = new WorkflowCycleState(quest);
        int itemCount = 1;
        state.BeginScene(itemCount);
        itemCount = 0;
        state.ObserveInventory(itemCount, insideTrigger: true);

        state.BeginScene(itemCount);
        state.CompleteRecovery(hasRuntimeEvidence: false);

        Assert.Equal(GuideWorkflowState.WorkflowStage.Unverifiable, state.Stage);
        Assert.Equal(-1, state.GetCurrentStepIndex(_ => itemCount));
    }

    [Fact]
    public void Target_completion_resets_to_a_fresh_repeatable_generation()
    {
        var quest = TestData.WorkflowQuest();
        var state = new WorkflowCycleState(quest);
        int itemCount = 1;
        state.BeginScene(itemCount);
        itemCount = 0;
        state.ObserveInventory(itemCount, insideTrigger: true);
        state.ObserveTarget();

        state.RecordTargetDeath("character:test enemy", anyLiveTargets: false);

        Assert.True(state.TargetsDefeated);
        state.ResetCycle(itemCount);
        Assert.Equal(1, state.Generation);
        Assert.Equal(GuideWorkflowState.WorkflowStage.NeedItem, state.Stage);
        Assert.Equal(0, state.GetCurrentStepIndex(_ => itemCount));

        itemCount = 1;
        state.ObserveInventory(itemCount, insideTrigger: false);
        itemCount = 0;
        state.ObserveInventory(itemCount, insideTrigger: true);
        state.ObserveTarget();
        state.RecordTargetDeath("character:test enemy", anyLiveTargets: false);
        state.ResetCycle(itemCount);

        Assert.Equal(2, state.Generation);
        Assert.Equal(GuideWorkflowState.WorkflowStage.NeedItem, state.Stage);
        Assert.Equal(0, state.GetCurrentStepIndex(_ => itemCount));
    }

    [Fact]
    public void Reload_discovery_stops_after_the_bounded_window()
    {
        int discoveryCalls = 0;
        var workflows = new GuideWorkflowState(
            TestData.Build(TestData.WorkflowQuest()),
            new EntityRegistry(),
            () =>
            {
                discoveryCalls++;
                return Array.Empty<Character>();
            }
        );
        workflows.OnSceneChanged("TestScene", _ => 0);

        for (int i = 0; i < 10; i++)
            workflows.Update(1f, _ => 0);

        Assert.Equal(5, discoveryCalls);
    }

    [Fact]
    public void Repeated_target_keys_advance_at_each_cumulative_threshold()
    {
        var quest = TestData.WorkflowQuest();
        quest.WorkflowCycle!.Targets[0].Quantity = 2;
        quest.Steps!.Add(
            new QuestStep
            {
                Order = 4,
                Action = "kill",
                Description = "Defeat another Test Enemy.",
                TargetName = "Test Enemy",
                TargetType = "character",
                TargetKey = "character:test enemy:1",
                Quantity = 1,
            }
        );
        var state = new WorkflowCycleState(quest);
        state.BeginScene(1);
        state.ObserveInventory(0, insideTrigger: true);

        state.RecordTargetDeath("character:test enemy", anyLiveTargets: true);
        Assert.False(state.TargetsDefeated);
        Assert.Equal(3, state.GetCurrentStepIndex(_ => 0));

        state.RecordTargetDeath("character:test enemy", anyLiveTargets: false);
        Assert.True(state.TargetsDefeated);
        Assert.Equal(quest.Steps.Count, state.GetCurrentStepIndex(_ => 0));
    }

    [Fact]
    public void Reward_workflow_waits_for_consumption_before_reset()
    {
        var quest = TestData.WorkflowQuest();
        quest.WorkflowCycle!.RewardContainer = new WorkflowRewardContainer
        {
            StableKey = "character:test reward",
            DisplayName = "Test Reward",
        };
        quest.WorkflowCycle.ResetEvidence = "reward_container_consumed";
        quest.Steps!.Add(
            new QuestStep
            {
                Order = 4,
                Action = "loot",
                Description = "Loot Test Reward.",
                TargetName = "Test Reward",
                TargetType = "character",
                TargetKey = "character:test reward",
            }
        );
        var state = new WorkflowCycleState(quest);
        state.BeginScene(1);
        state.ObserveInventory(0, insideTrigger: true);
        state.RecordTargetDeath("character:test enemy", anyLiveTargets: false);
        state.ObserveReward();

        Assert.Equal(GuideWorkflowState.WorkflowStage.RewardAvailable, state.Stage);
        Assert.Equal(3, state.GetCurrentStepIndex(_ => 0));

        state.ResetCycle(0);
        Assert.Equal(GuideWorkflowState.WorkflowStage.NeedItem, state.Stage);
        Assert.Equal(0, state.GetCurrentStepIndex(_ => 0));
    }

    [Fact]
    public void Trigger_bounds_are_inclusive_and_three_dimensional()
    {
        var bounds = TestData.WorkflowQuest().WorkflowCycle!.Trigger.Location;

        Assert.True(bounds.Contains(12f, 4f, 22f));
        Assert.False(bounds.Contains(12.01f, 4f, 22f));
        Assert.False(bounds.Contains(12f, 4.01f, 22f));
        Assert.False(bounds.Contains(12f, 4f, 22.01f));
    }

    [Fact]
    public void Obtainability_skips_locked_seller_variants()
    {
        var quest = TestData.WorkflowQuest();
        quest.RequiredItems =
        [
            new RequiredItemInfo
            {
                ItemName = "Test Token",
                ItemStableKey = "item:test token",
                Quantity = 1,
                Sources =
                [
                    new ItemSource
                    {
                        Type = "vendor",
                        Name = "Unlocked Seller",
                        SourceKey = "character:unlocked seller",
                        RequiredQuestDBNames = ["GateQuest"],
                        Instruction = "Buy Test Token.",
                    },
                    new ItemSource
                    {
                        Type = "vendor",
                        Name = "Initial Seller",
                        SourceKey = "character:initial seller",
                        Instruction = "Buy Test Token.",
                    },
                ],
            },
        ];
        var obtain = quest.Steps![0];

        Assert.Equal(
            "character:initial seller",
            StepSceneResolver.FindFirstSourceKey(quest, obtain, _ => false)
        );
        Assert.Equal(
            "character:unlocked seller",
            StepSceneResolver.FindFirstSourceKey(quest, obtain, _ => true)
        );
    }
}
