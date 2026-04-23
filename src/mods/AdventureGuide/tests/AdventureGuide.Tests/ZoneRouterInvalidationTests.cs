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

		var changeSet = harness.ForInventoryChange(changedItemKey: "item:wooden-cup");
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

		var changeSet = harness.ForInventoryChange(changedItemKey: "item:silver-key");
		router.ObserveInvalidation(changeSet.ChangedFacts);

		Assert.Equal(1, router.RebuildCount);
	}

	[Fact]
	public void SourceStateChangeOfUnrelatedSource_DoesNotRebuild()
	{
		var (router, harness) = ZoneRouterHarness.BuildWithZoneLineUnlockedBy("item:silver-key");
		var hopsBefore = router.GetHopCount("SceneA", "SceneC");

		var changeSet = harness.ForSourceStateChange("char:unrelated-gatekeeper");
		router.ObserveInvalidation(changeSet.ChangedFacts);

		Assert.Equal(hopsBefore, router.GetHopCount("SceneA", "SceneC"));
		Assert.Equal(0, router.RebuildCount);
	}

	[Fact]
	public void SourceStateWildcardWithoutRouteSpecificKey_DoesNotRebuild()
	{
		var (router, _) = ZoneRouterHarness.BuildWithZoneLineUnlockedBy("item:silver-key");

		router.ObserveInvalidation(new[] { new FactKey(FactKind.SourceState, "*") });

		Assert.Equal(0, router.RebuildCount);
	}

	[Fact]
	public void SourceStateChangeOfRuntimeRouteUnlockSource_TriggersRebuild()
	{
		var (router, harness) = ZoneRouterHarness.BuildWithZoneLineUnlockedByLiveSource(
			characterKey: "char:gatekeeper",
			runtimeSourceKey: "spawn:gatekeeper"
		);
		_ = router.GetHopCount("SceneA", "SceneC");

		var changeSet = harness.ForSourceStateChange("spawn:gatekeeper");
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
