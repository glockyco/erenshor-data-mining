using AdventureGuide.Markers;
using AdventureGuide.Resolution;
using AdventureGuide.State;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests.State;

public sealed class LiveStateTrackerChannelTests
{
	[Fact]
	public void TryConsumeLiveWorldChange_ReturnsTrueOncePerChange()
	{
		var guide = new CompiledGuideBuilder().Build();
		var phases = new QuestStateTracker(guide);
		var unlocks = new UnlockEvaluator(guide, new GameState(guide), phases);
		var tracker = new LiveStateTracker(guide, unlocks);

		Assert.False(tracker.TryConsumeLiveWorldChange(),
			"Fresh tracker has no pending change.");

		tracker.MarkLiveWorldChanged();

		var snapshot = tracker.GetLiveSourceSnapshot(
			new MarkerCandidate(
				questKey: "quest:a",
				targetNodeKey: "missing-target",
				positionNodeKey: "missing-source",
				sourceNodeKey: "missing-source",
				scene: "Town",
				questKind: QuestMarkerKind.Objective,
				spawnCategory: SpawnCategory.Alive,
				priority: 0,
				subText: "Missing target",
				x: 1f,
				y: 2f,
				z: 3f,
				keepWhileCorpsePresent: false,
				corpseSubText: null,
				isNightSpawnNode: false,
				displayName: "Missing",
				unlockBlockedReason: null));

		Assert.Equal(LiveSourceOccupancy.Unknown, snapshot.Occupancy);
		Assert.True(tracker.TryConsumeLiveWorldChange(),
			"Projection reads must not consume the pending change signal.");
		Assert.False(tracker.TryConsumeLiveWorldChange(),
			"Signal consumed; second call returns false.");

		tracker.MarkLiveWorldChanged();
		tracker.MarkLiveWorldChanged();
		tracker.MarkLiveWorldChanged();

		Assert.True(tracker.TryConsumeLiveWorldChange(),
			"Multiple changes coalesce into one positive consume.");
		Assert.False(tracker.TryConsumeLiveWorldChange(),
			"Coalesced consume clears the queue.");
	}
}
