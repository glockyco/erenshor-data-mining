using AdventureGuide.Data;
using AdventureGuide.Navigation;
using AdventureGuide.State;

namespace AdventureGuide.Tests;

public sealed class MarkerPolicyTests
{
    [Fact]
    public void Quest_giver_type_distinguishes_repeatable_quests()
    {
        Assert.Equal(MarkerType.QuestGiver, MarkerDecision.GetQuestGiverType(false));
        Assert.Equal(MarkerType.QuestGiverRepeat, MarkerDecision.GetQuestGiverType(true));
    }

    [Fact]
    public void Turn_in_type_distinguishes_ready_pending_and_repeatable_ready()
    {
        Assert.Equal(MarkerType.TurnInReady, MarkerDecision.GetTurnInType(true, false));
        Assert.Equal(MarkerType.TurnInRepeatReady, MarkerDecision.GetTurnInType(true, true));
        Assert.Equal(MarkerType.TurnInPending, MarkerDecision.GetTurnInType(false, false));
        Assert.Equal(MarkerType.TurnInPending, MarkerDecision.GetTurnInType(false, true));
    }

    [Fact]
    public void Duplicate_intent_replacement_uses_marker_priority_order()
    {
        Assert.True(MarkerDecision.ShouldReplace(MarkerType.Objective, MarkerType.TurnInReady));
        Assert.False(MarkerDecision.ShouldReplace(MarkerType.TurnInReady, MarkerType.Objective));
        Assert.False(MarkerDecision.ShouldReplace(MarkerType.Objective, MarkerType.Objective));
    }

    [Theory]
    [InlineData(0, false, 3)]
    [InlineData(1, false, 3)]
    [InlineData(2, false, 1)]
    [InlineData(3, false, 1)]
    [InlineData(4, false, 1)]
    [InlineData(4, true, 0)]
    public void Item_marker_candidates_preserve_bundle_quantities_and_independent_requirements(
        int runners,
        bool tokenHeld,
        int expectedCount
    )
    {
        var wrapper = TestData.NativeRequirements(
            ("item:runner", "A", [1, 3]),
            ("item:runner", "B", [2]),
            ("item:token", null, [1])
        );
        var quest = wrapper.Quests![0];
        for (int i = 0; i < quest.RequiredItems!.Count; i++)
            quest.RequiredItems[i].Sources =
            [
                new ItemSource { Type = "vendor", SourceKey = $"character:seller{i}" },
            ];
        int Count(string key) =>
            key == "item:runner" ? runners
            : tokenHeld ? 1
            : 0;
        var candidates = new List<(string? Source, int Have, int Need)>();
        var missing = StepProgress.MissingRequirements(quest, Count);
        while (missing.MoveNext())
            foreach (var source in missing.Current.Sources!)
                candidates.Add((source.SourceKey, missing.Have, missing.Current.Quantity));

        Assert.Equal(expectedCount, candidates.Count);
        if (runners >= 2)
        {
            Assert.DoesNotContain(candidates, candidate => candidate.Source == "character:seller0");
            Assert.DoesNotContain(candidates, candidate => candidate.Source == "character:seller1");
        }
        else
        {
            Assert.Contains(("character:seller0", runners, 4), candidates);
            Assert.Contains(("character:seller1", runners, 2), candidates);
        }
        Assert.Equal(
            tokenHeld && runners >= 2 ? MarkerType.TurnInReady : MarkerType.TurnInPending,
            MarkerDecision.GetTurnInType(StepProgress.HasRequiredItems(quest, Count), false)
        );
    }
}
