using AdventureGuide.Diagnostics;
using AdventureGuide.Plan;
using AdventureGuide.State;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class MaintainedViewPlannerTests
{
	private static readonly string[] ActiveKeys =
		new[] { "quest:a", "quest:b", "quest:c" };

	[Fact]
	public void NoChanges_ReturnsNone()
	{
		var plan = MaintainedViewPlanner.Plan(
			ActiveKeys,
			ChangeSet.None,
			liveWorldChanged: false,
			targetSourceVersionChanged: false,
			navSetVersionChanged: false
		);

		Assert.Equal(MaintainedViewRefreshKind.None, plan.Kind);
		Assert.Empty(plan.Keys);
	}

	[Fact]
	public void SceneChanged_ReturnsFull()
	{
		var changeSet = new ChangeSet(
			inventoryChanged: false,
			questLogChanged: false,
			sceneChanged: true,
			liveWorldChanged: false,
			changedItemKeys: Array.Empty<string>(),
			changedQuestDbNames: Array.Empty<string>(),
			affectedQuestKeys: Array.Empty<string>(),
			changedFacts: Array.Empty<FactKey>()
		);

		var plan = MaintainedViewPlanner.Plan(
			ActiveKeys,
			changeSet,
			liveWorldChanged: false,
			targetSourceVersionChanged: false,
			navSetVersionChanged: false
		);

		Assert.Equal(MaintainedViewRefreshKind.Full, plan.Kind);
		Assert.Equal(DiagnosticTrigger.SceneChanged, plan.Reason);
	}

	[Fact]
	public void NavSetVersionChanged_ReturnsFull()
	{
		var plan = MaintainedViewPlanner.Plan(
			ActiveKeys,
			ChangeSet.None,
			liveWorldChanged: false,
			targetSourceVersionChanged: false,
			navSetVersionChanged: true
		);

		Assert.Equal(MaintainedViewRefreshKind.Full, plan.Kind);
		Assert.Equal(DiagnosticTrigger.NavSetChanged, plan.Reason);
	}

	[Fact]
	public void TargetSourceVersionChanged_ReturnsFull()
	{
		var plan = MaintainedViewPlanner.Plan(
			ActiveKeys,
			ChangeSet.None,
			liveWorldChanged: false,
			targetSourceVersionChanged: true,
			navSetVersionChanged: false
		);

		Assert.Equal(MaintainedViewRefreshKind.Full, plan.Kind);
		Assert.Equal(DiagnosticTrigger.TargetSourceVersionChanged, plan.Reason);
	}

	[Fact]
	public void LiveWorldChanged_NoAffectedKeys_ReturnsFull()
	{
		var changeSet = new ChangeSet(
			inventoryChanged: false,
			questLogChanged: false,
			sceneChanged: false,
			liveWorldChanged: true,
			changedItemKeys: Array.Empty<string>(),
			changedQuestDbNames: Array.Empty<string>(),
			affectedQuestKeys: Array.Empty<string>(),
			changedFacts: Array.Empty<FactKey>()
		);

		var plan = MaintainedViewPlanner.Plan(
			ActiveKeys,
			changeSet,
			liveWorldChanged: true,
			targetSourceVersionChanged: false,
			navSetVersionChanged: false
		);

		Assert.Equal(MaintainedViewRefreshKind.Full, plan.Kind);
		Assert.Equal(DiagnosticTrigger.LiveWorldChanged, plan.Reason);
	}

	[Fact]
	public void AffectedKeysSubset_ReturnsPartialForSubset()
	{
		var changeSet = new ChangeSet(
			inventoryChanged: true,
			questLogChanged: false,
			sceneChanged: false,
			liveWorldChanged: false,
			changedItemKeys: new[] { "item:x" },
			changedQuestDbNames: Array.Empty<string>(),
			affectedQuestKeys: new[] { "quest:a", "quest:unrelated" },
			changedFacts: new[] { new FactKey(FactKind.InventoryItemCount, "item:x") }
		);

		var plan = MaintainedViewPlanner.Plan(
			ActiveKeys,
			changeSet,
			liveWorldChanged: false,
			targetSourceVersionChanged: false,
			navSetVersionChanged: false
		);

		Assert.Equal(MaintainedViewRefreshKind.Partial, plan.Kind);
		Assert.Equal(new[] { "quest:a" }, plan.Keys);
	}

	[Fact]
	public void AffectedKeysExhaustActive_ReturnsFull()
	{
		var changeSet = new ChangeSet(
			inventoryChanged: true,
			questLogChanged: false,
			sceneChanged: false,
			liveWorldChanged: false,
			changedItemKeys: new[] { "item:x" },
			changedQuestDbNames: Array.Empty<string>(),
			affectedQuestKeys: new[] { "quest:a", "quest:b", "quest:c" },
			changedFacts: new[] { new FactKey(FactKind.InventoryItemCount, "item:x") }
		);

		var plan = MaintainedViewPlanner.Plan(
			ActiveKeys,
			changeSet,
			liveWorldChanged: false,
			targetSourceVersionChanged: false,
			navSetVersionChanged: false
		);

		Assert.Equal(MaintainedViewRefreshKind.Full, plan.Kind);
	}

	[Fact]
	public void EmptyActiveKeys_ReturnsNone()
	{
		var changeSet = new ChangeSet(
			inventoryChanged: false,
			questLogChanged: false,
			sceneChanged: true,
			liveWorldChanged: false,
			changedItemKeys: Array.Empty<string>(),
			changedQuestDbNames: Array.Empty<string>(),
			affectedQuestKeys: Array.Empty<string>(),
			changedFacts: Array.Empty<FactKey>()
		);

		var plan = MaintainedViewPlanner.Plan(
			Array.Empty<string>(),
			changeSet,
			liveWorldChanged: false,
			targetSourceVersionChanged: false,
			navSetVersionChanged: false
		);

		Assert.Equal(MaintainedViewRefreshKind.None, plan.Kind);
	}
}
