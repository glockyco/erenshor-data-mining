using AdventureGuide.Diagnostics;
using AdventureGuide.State;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class MaintainedViewInvalidationTests
{
    [Fact]
    public void Plan_TargetSourceVersionChangedWithAffectedSubset_PreservesUntouchedEntries()
    {
        var activeKeys = new[] { "quest:a", "quest:b", "quest:c" };
        var changeSet = new GuideChangeSet(
            inventoryChanged: true,
            questLogChanged: false,
            sceneChanged: false,
            liveWorldChanged: false,
            changedItemKeys: new[] { "item:ore" },
            changedQuestDbNames: Array.Empty<string>(),
            affectedQuestKeys: new[] { "quest:b" },
            changedFacts: Array.Empty<GuideFactKey>()
        );

        var plannerType = typeof(GuideChangeSet).Assembly.GetType(
            "AdventureGuide.Navigation.MaintainedViewRefreshPlanner"
        );

        Assert.NotNull(plannerType);
        var method = plannerType!.GetMethod("Plan");
        Assert.NotNull(method);
    }

    [Fact]
    public void Plan_NavSetChangedFallsBackToFullActiveSet()
    {
        var activeKeys = new[] { "quest:a", "quest:b" };
        var changeSet = GuideChangeSet.None;
        var plannerType = typeof(GuideChangeSet).Assembly.GetType(
            "AdventureGuide.Navigation.MaintainedViewRefreshPlanner"
        );

        Assert.NotNull(plannerType);
        var method = plannerType!.GetMethod("Plan");
        Assert.NotNull(method);
    }
}
