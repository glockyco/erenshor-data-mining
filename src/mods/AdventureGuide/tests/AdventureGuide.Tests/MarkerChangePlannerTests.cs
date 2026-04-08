using AdventureGuide.Markers;
using AdventureGuide.State;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class MarkerChangePlannerTests
{
    [Fact]
    public void Plan_EmptyChange_ReturnsNoop()
    {
        var plan = MarkerChangePlanner.Plan(GuideChangeSet.None);

        Assert.False(plan.FullRebuild);
        Assert.Empty(plan.AffectedQuestKeys);
    }

    [Fact]
    public void Plan_SceneChange_ForcesFullRebuild()
    {
        var changeSet = new GuideChangeSet(
            inventoryChanged: false,
            questLogChanged: false,
            sceneChanged: true,
            liveWorldChanged: false,
            changedItemKeys: Array.Empty<string>(),
            changedQuestDbNames: Array.Empty<string>(),
            affectedQuestKeys: new[] { "quest:a" },
            changedFacts: Array.Empty<GuideFactKey>());

        var plan = MarkerChangePlanner.Plan(changeSet);

        Assert.True(plan.FullRebuild);
        Assert.Empty(plan.AffectedQuestKeys);
    }

    [Fact]
    public void Plan_LiveWorldChange_ForcesFullRebuild()
    {
        var changeSet = new GuideChangeSet(
            inventoryChanged: false,
            questLogChanged: false,
            sceneChanged: false,
            liveWorldChanged: true,
            changedItemKeys: Array.Empty<string>(),
            changedQuestDbNames: Array.Empty<string>(),
            affectedQuestKeys: new[] { "quest:a" },
            changedFacts: Array.Empty<GuideFactKey>());

        var plan = MarkerChangePlanner.Plan(changeSet);

        Assert.True(plan.FullRebuild);
        Assert.Empty(plan.AffectedQuestKeys);
    }

    [Fact]
    public void Plan_AffectedQuestKeys_UsesPartialRebuild()
    {
        var changeSet = new GuideChangeSet(
            inventoryChanged: true,
            questLogChanged: false,
            sceneChanged: false,
            liveWorldChanged: false,
            changedItemKeys: new[] { "item:key" },
            changedQuestDbNames: Array.Empty<string>(),
            affectedQuestKeys: new[] { "quest:a", "quest:b" },
            changedFacts: Array.Empty<GuideFactKey>());

        var plan = MarkerChangePlanner.Plan(changeSet);

        Assert.False(plan.FullRebuild);
        Assert.Equal(new[] { "quest:a", "quest:b" }, plan.AffectedQuestKeys.OrderBy(key => key).ToArray());
    }
}
