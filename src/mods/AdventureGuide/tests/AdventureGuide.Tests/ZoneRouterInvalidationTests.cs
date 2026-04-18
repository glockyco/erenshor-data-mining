using AdventureGuide.State;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class ZoneRouterInvalidationTests
{
    [Fact]
    public void InventoryChangeOfUnrelatedItem_DoesNotRebuild()
    {
        var (router, harness) = ZoneRouterHarness.BuildWithZoneLineUnlockedBy("item:silver-key");
        var hopsBefore = router.GetHopCount("SceneA", "SceneC");

        var changeSet = harness.ForInventoryChange(
            changedItemKey: "item:wooden-cup",
            affectedQuestKeys: Array.Empty<string>()
        );
        router.ObserveInvalidation(harness.DependencyEngine.InvalidateFacts(changeSet.ChangedFacts));

        Assert.Equal(hopsBefore, router.GetHopCount("SceneA", "SceneC"));
        Assert.Equal(0, router.RebuildCount);
    }

    [Fact]
    public void InventoryChangeOfKeyringItem_TriggersRebuild()
    {
        var (router, harness) = ZoneRouterHarness.BuildWithZoneLineUnlockedBy("item:silver-key");
        harness.AddToInventory("item:silver-key");
        _ = router.GetHopCount("SceneA", "SceneC");

        var changeSet = harness.ForInventoryChange(
            changedItemKey: "item:silver-key",
            affectedQuestKeys: Array.Empty<string>()
        );
        router.ObserveInvalidation(harness.DependencyEngine.InvalidateFacts(changeSet.ChangedFacts));

        Assert.Equal(1, router.RebuildCount);
    }

    [Fact]
    public void SceneChange_AlwaysTriggersRebuild()
    {
        var (router, harness) = ZoneRouterHarness.BuildWithZoneLineUnlockedBy("item:silver-key");

        var changeSet = harness.ForSceneChange("SceneB");
        ApplyPluginStyleInvalidation(router, harness.DependencyEngine, changeSet);

        Assert.Equal(1, router.RebuildCount);
    }

    private static void ApplyPluginStyleInvalidation(
        AdventureGuide.Position.ZoneRouter router,
        GuideDependencyEngine dependencies,
        GuideChangeSet changeSet
    )
    {
        if (changeSet.SceneChanged)
        {
            router.Rebuild();
            return;
        }

        router.ObserveInvalidation(dependencies.InvalidateFacts(changeSet.ChangedFacts));
    }
}
