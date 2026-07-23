using AdventureGuide.State;

namespace AdventureGuide.Tests;

public sealed class QuestPolicyTests
{
    [Theory]
    [InlineData(false, false, QuestRuntimeStatus.Available)]
    [InlineData(false, true, QuestRuntimeStatus.Available)]
    [InlineData(true, false, QuestRuntimeStatus.ImplicitlyActive)]
    [InlineData(true, true, QuestRuntimeStatus.Active)]
    public void Guide_only_status_is_determined_by_scene_and_progress(
        bool isInCurrentScene,
        bool isInProgress,
        QuestRuntimeStatus expected
    )
    {
        Assert.Equal(
            expected,
            QuestStatusPolicy.GetGuideOnlyStatus(isInCurrentScene, isInProgress)
        );
    }

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
