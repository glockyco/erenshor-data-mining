using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class ZoneRouterLockedHopMemoTests
{
	[Fact]
	public void FindFirstLockedHop_ReturnsConsistentResultAcrossRepeatedCalls()
	{
		// Key in SceneA locks the SceneB->SceneC transition. From SceneA there
		// is no accessible path to SceneC, so FindFirstLockedHop must surface
		// the SceneB->SceneC zone line as the locked hop every time.
		var (router, _) = ZoneRouterHarness.BuildWithZoneLineUnlockedBy("item:silver-key");

		var first = router.FindFirstLockedHop("SceneA", "SceneC");
		var second = router.FindFirstLockedHop("SceneA", "SceneC");
		var third = router.FindFirstLockedHop("SceneA", "SceneC");

		Assert.NotNull(first);
		Assert.NotNull(second);
		Assert.NotNull(third);
		// Memoization must not change the answer — identity of the locked hop
		// is stable across repeated calls on the same adjacency snapshot.
		Assert.Equal(first!.ZoneLineKey, second!.ZoneLineKey);
		Assert.Equal(first.ZoneLineKey, third!.ZoneLineKey);
		Assert.Equal(first.FromScene, second.FromScene);
		Assert.Equal(first.ToScene, second.ToScene);
	}

	[Fact]
	public void FindFirstLockedHop_ReturnsNullForAccessibleRouteAndRepeats()
	{
		// Unlock the key — SceneA->SceneC becomes fully accessible, so
		// FindFirstLockedHop must return null. That null must be cached
		// too, not just positive results.
		var (router, harness) = ZoneRouterHarness.BuildWithZoneLineUnlockedBy("item:silver-key");
		harness.AddToInventory("item:silver-key");
		router.Rebuild();

		var first = router.FindFirstLockedHop("SceneA", "SceneC");
		var second = router.FindFirstLockedHop("SceneA", "SceneC");

		Assert.Null(first);
		Assert.Null(second);
	}

	[Fact]
	public void FindFirstLockedHop_MemoClearedOnRebuild()
	{
		// Cache a locked-hop answer, then change adjacency (obtain key,
		// Rebuild). The previously cached result must be discarded; the
		// new query must see the unlocked graph.
		var (router, harness) = ZoneRouterHarness.BuildWithZoneLineUnlockedBy("item:silver-key");

		var lockedBefore = router.FindFirstLockedHop("SceneA", "SceneC");
		Assert.NotNull(lockedBefore);

		harness.AddToInventory("item:silver-key");
		router.Rebuild();

		var afterRebuild = router.FindFirstLockedHop("SceneA", "SceneC");
		Assert.Null(afterRebuild);
	}

	[Fact]
	public void FindFirstLockedHop_DistinctScenePairsDoNotCollide()
	{
		// Memo keys must distinguish scene pairs. Querying a same-scene
		// round-trip must return null without poisoning the SceneA->SceneC
		// entry in the memo.
		var (router, _) = ZoneRouterHarness.BuildWithZoneLineUnlockedBy("item:silver-key");

		Assert.Null(router.FindFirstLockedHop("SceneA", "SceneA"));
		Assert.Null(router.FindFirstLockedHop("SceneB", "SceneB"));
		Assert.NotNull(router.FindFirstLockedHop("SceneA", "SceneC"));
	}
}
