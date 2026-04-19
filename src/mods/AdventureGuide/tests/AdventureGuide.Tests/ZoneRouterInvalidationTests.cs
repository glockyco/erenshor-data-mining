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
		router.ObserveInvalidation(changeSet.ChangedFacts);

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
		router.ObserveInvalidation(changeSet.ChangedFacts);

		Assert.Equal(1, router.RebuildCount);
	}

	[Fact]
	public void SceneChange_AlwaysTriggersRebuild()
	{
		var (router, harness) = ZoneRouterHarness.BuildWithZoneLineUnlockedBy("item:silver-key");

		var changeSet = harness.ForSceneChange("SceneB");
		ApplyPluginStyleInvalidation(router, changeSet);

		Assert.Equal(1, router.RebuildCount);
	}

	// Mirrors Plugin.Update's invalidation fork: scene changes force a full rebuild
	// while all other fact changes flow through ObserveInvalidation.
	private static void ApplyPluginStyleInvalidation(
		AdventureGuide.Position.ZoneRouter router,
		ChangeSet changeSet
	)
	{
		if (changeSet.SceneChanged)
		{
			router.Rebuild();
			return;
		}

		router.ObserveInvalidation(changeSet.ChangedFacts);
	}
}
