using AdventureGuide.State;

namespace AdventureGuide.Tests;

public sealed class QuestPolicyTests
{
    [Theory]
    [InlineData(false, false, false, true)]
    [InlineData(false, false, true, true)]
    [InlineData(false, true, false, true)]
    [InlineData(false, true, true, true)]
    [InlineData(true, false, false, false)]
    [InlineData(true, false, true, false)]
    [InlineData(true, true, false, true)]
    [InlineData(true, true, true, false)]
    public void Tracker_pruning_covers_missing_completion_and_repeatability(
        bool questExists,
        bool isCompleted,
        bool isRepeatable,
        bool expected
    )
    {
        Assert.Equal(
            expected,
            TrackerPruningPolicy.ShouldPrune(questExists, isCompleted, isRepeatable)
        );
    }

    [Fact]
    public void Completed_repeatable_quest_is_retained()
    {
        Assert.False(TrackerPruningPolicy.ShouldPrune(true, isCompleted: true, isRepeatable: true));
    }

    [Fact]
    public void Missing_quest_is_pruned_even_when_completion_is_unknown()
    {
        Assert.True(
            TrackerPruningPolicy.ShouldPrune(false, isCompleted: false, isRepeatable: true)
        );
    }
}
