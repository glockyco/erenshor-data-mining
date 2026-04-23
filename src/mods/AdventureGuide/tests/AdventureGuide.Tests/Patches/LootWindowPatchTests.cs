using AdventureGuide.Patches;
using AdventureGuide.State;
using Xunit;

namespace AdventureGuide.Tests.Patches;

public sealed class LootWindowPatchTests
{
	[Fact]
	public void TryHandleLootClose_NoOpsWhenParentIsUnsafeToInspect()
	{
		var parent = new FakeLootParent(canInspect: false, npc: new FakeNpc());
		bool getNpcCalled = false;
		bool onCorpseLootedCalled = false;
		bool invalidateCalled = false;
		bool observeCalled = false;

		var exception = Record.Exception(() =>
			LootWindowCloseWindowPatch.TryHandleLootClose<FakeLootParent, FakeNpc>(
				parent,
				static lootParent => lootParent.CanInspect,
				lootParent =>
				{
					getNpcCalled = true;
					throw new InvalidOperationException("Unsafe parent should not be inspected.");
				},
				npc =>
				{
					onCorpseLootedCalled = true;
					return ChangeSet.None;
				},
				_ => invalidateCalled = true,
				_ => observeCalled = true
			)
		);

		Assert.Null(exception);
		Assert.False(getNpcCalled);
		Assert.False(onCorpseLootedCalled);
		Assert.False(invalidateCalled);
		Assert.False(observeCalled);
	}

	[Fact]
	public void TryHandleLootClose_InvalidatesFactsWhenParentAndNpcAreValid()
	{
		var npc = new FakeNpc();
		var parent = new FakeLootParent(canInspect: true, npc);
		var changedFacts = new[] { new FactKey(FactKind.SourceState, "spawn:bandit") };
		var change = new ChangeSet(
			inventoryChanged: false,
			questLogChanged: false,
			sceneChanged: false,
			liveWorldChanged: true,
			changedItemKeys: Array.Empty<string>(),
			changedQuestDbNames: Array.Empty<string>(),
			changedFacts: changedFacts
		);
		int invalidateCount = 0;
		int observeCount = 0;
		IReadOnlyCollection<FactKey>? invalidatedFacts = null;
		IReadOnlyCollection<FactKey>? observedFacts = null;

		bool handled = LootWindowCloseWindowPatch.TryHandleLootClose<FakeLootParent, FakeNpc>(
			parent,
			static lootParent => lootParent.CanInspect,
			static lootParent => lootParent.Npc,
			_ => change,
			facts =>
			{
				invalidateCount++;
				invalidatedFacts = facts;
			},
			facts =>
			{
				observeCount++;
				observedFacts = facts;
			}
		);

		Assert.True(handled);
		Assert.Equal(1, invalidateCount);
		Assert.Equal(1, observeCount);
		Assert.Equal(changedFacts, invalidatedFacts);
		Assert.Equal(changedFacts, observedFacts);
	}

	private sealed class FakeLootParent(bool canInspect, FakeNpc? npc)
	{
		public bool CanInspect { get; } = canInspect;

		public FakeNpc? Npc { get; } = npc;
	}

	private sealed class FakeNpc;
}
