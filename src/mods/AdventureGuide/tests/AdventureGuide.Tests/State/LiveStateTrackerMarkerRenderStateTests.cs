using AdventureGuide.Markers;
using AdventureGuide.Resolution;
using AdventureGuide.State;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests.State;

public sealed class LiveStateTrackerMarkerRenderStateTests
{
	[Fact]
	public void GetMarkerLiveRenderState_ReturnsUnknown_WhenPositionNodeIsMissing()
	{
		var tracker = CreateTracker(new CompiledGuideBuilder().Build());

		var state = tracker.GetMarkerLiveRenderState(SampleCandidate());

		Assert.Equal(MarkerLiveRenderState.Unknown, state);
	}

	[Fact]
	public void GetMarkerLiveRenderState_ReturnsUnknown_WhenTargetNodeIsMissing()
	{
		var guide = new CompiledGuideBuilder()
			.AddSpawnPoint("spawn:leaf-1", scene: "Town", x: 1f, y: 2f, z: 3f)
			.Build();
		var tracker = CreateTracker(guide);

		var state = tracker.GetMarkerLiveRenderState(SampleCandidate());

		Assert.Equal(MarkerLiveRenderState.Unknown, state);
		Assert.Equal(
			LiveSourceSnapshot.Unknown("spawn:leaf-1", "char:leaf"),
			tracker.GetLiveSourceSnapshot(SampleCandidate()));
	}



	[Fact]
	public void LiveSourceSnapshot_RepresentsAnchoredCharacterAndStaticResourceSemantics()
	{
		var alive = LiveSourceSnapshot.Alive(
			sourceNodeKey: "spawn:alive",
			targetNodeKey: "char:alive",
			livePosition: (1f, 2f, 3f),
			anchoredLivePosition: (1f, 4.8f, 3f));
		var deadWithCorpse = LiveSourceSnapshot.Dead(
			sourceNodeKey: "spawn:corpse",
			targetNodeKey: "char:corpse",
			livePosition: (4f, 5f, 6f),
			anchoredLivePosition: (4f, 8.3f, 6f),
			respawnSeconds: 12f);
		var deadNoCorpse = LiveSourceSnapshot.Dead(
			sourceNodeKey: "spawn:dead",
			targetNodeKey: "char:dead",
			livePosition: null,
			anchoredLivePosition: null,
			respawnSeconds: 18f);
		var zoneReentry = LiveSourceSnapshot.ZoneReentry(
			sourceNodeKey: "spawn:direct",
			targetNodeKey: "char:direct",
			respawnSeconds: 0f);
		var mined = LiveSourceSnapshot.Mined(
			sourceNodeKey: "mining:iron",
			targetNodeKey: "mining:iron",
			respawnSeconds: 30f);
		var pickedUp = LiveSourceSnapshot.PickedUp(
			sourceNodeKey: "bag:cache",
			targetNodeKey: "bag:cache",
			respawnSeconds: 45f);
		var blocked = LiveSourceSnapshot.UnlockBlocked(
			sourceNodeKey: "spawn:blocked",
			targetNodeKey: "char:blocked",
			reason: "Requires: quest:gate");

		Assert.Equal(LiveSourceOccupancy.Alive, alive.Occupancy);
		Assert.True(alive.IsActionable);
		Assert.Equal(LiveSourceAnchor.LiveObject, alive.Anchor);
		Assert.Equal((1f, 2f, 3f), alive.LivePosition);
		Assert.Equal((1f, 4.8f, 3f), alive.AnchoredLivePosition);
		Assert.Equal(new MarkerLiveRenderState(MarkerLiveStatus.Alive, (1f, 4.8f, 3f), 0f, null), alive.ToMarkerRenderState());

		Assert.Equal(LiveSourceOccupancy.Dead, deadWithCorpse.Occupancy);
		Assert.False(deadWithCorpse.IsActionable);
		Assert.Equal(LiveSourceAnchor.LiveObject, deadWithCorpse.Anchor);
		Assert.Equal((4f, 5f, 6f), deadWithCorpse.LivePosition);
		Assert.Equal((4f, 8.3f, 6f), deadWithCorpse.AnchoredLivePosition);
		Assert.Equal(new MarkerLiveRenderState(MarkerLiveStatus.DeadWithCorpse, (4f, 8.3f, 6f), 12f, null), deadWithCorpse.ToMarkerRenderState());

		Assert.Equal(LiveSourceOccupancy.Dead, deadNoCorpse.Occupancy);
		Assert.False(deadNoCorpse.IsActionable);
		Assert.Equal(LiveSourceAnchor.Source, deadNoCorpse.Anchor);
		Assert.Null(deadNoCorpse.LivePosition);
		Assert.Null(deadNoCorpse.AnchoredLivePosition);
		Assert.Equal(new MarkerLiveRenderState(MarkerLiveStatus.DeadNoCorpse, null, 18f, null), deadNoCorpse.ToMarkerRenderState());

		Assert.Equal(LiveSourceOccupancy.Dead, zoneReentry.Occupancy);
		Assert.False(zoneReentry.IsActionable);
		Assert.True(zoneReentry.RequiresZoneReentry);
		Assert.Equal(LiveSourceAnchor.Source, zoneReentry.Anchor);
		Assert.Null(zoneReentry.LivePosition);
		Assert.Null(zoneReentry.AnchoredLivePosition);
		Assert.Equal(new MarkerLiveRenderState(MarkerLiveStatus.ZoneReentry, null, 0f, null), zoneReentry.ToMarkerRenderState());

		Assert.Equal(LiveSourceOccupancy.Mined, mined.Occupancy);
		Assert.False(mined.IsActionable);
		Assert.Equal(LiveSourceAnchor.Source, mined.Anchor);
		Assert.Equal(new MarkerLiveRenderState(MarkerLiveStatus.MiningMined, null, 30f, null), mined.ToMarkerRenderState());

		Assert.Equal(LiveSourceOccupancy.PickedUp, pickedUp.Occupancy);
		Assert.False(pickedUp.IsActionable);
		Assert.Equal(LiveSourceAnchor.Source, pickedUp.Anchor);
		Assert.Equal(new MarkerLiveRenderState(MarkerLiveStatus.PickedUp, null, 45f, null), pickedUp.ToMarkerRenderState());

		Assert.Equal(LiveSourceOccupancy.UnlockBlocked, blocked.Occupancy);
		Assert.False(blocked.IsActionable);
		Assert.Equal(LiveSourceAnchor.Source, blocked.Anchor);
		Assert.Equal("Requires: quest:gate", blocked.UnlockReason);
		Assert.Equal(
			new MarkerLiveRenderState(MarkerLiveStatus.UnlockBlocked, null, 0f, "Requires: quest:gate"),
			blocked.ToMarkerRenderState());
	}

	[Fact]
	public void LiveSourceSnapshot_ToMarkerRenderState_MapsDisabledCharacter()
	{
		var disabled = LiveSourceSnapshot.Disabled("spawn:gate", "char:gate");

		Assert.Equal(MarkerLiveStatus.Disabled, disabled.ToMarkerRenderState().Status);
	}

	private static LiveStateTracker CreateTracker(AdventureGuide.CompiledGuide.CompiledGuide guide)
	{
		var phases = new QuestStateTracker(guide);
		var unlocks = new UnlockEvaluator(guide, new GameState(guide), phases);
		return new LiveStateTracker(guide, unlocks);
	}

	private static MarkerCandidate SampleCandidate(
		string targetNodeKey = "char:leaf",
		string positionNodeKey = "spawn:leaf-1",
		string sourceNodeKey = "spawn:leaf-1",
		string scene = "Town",
		string displayName = "Leaf") =>
		new(
			questKey: "quest:a",
			targetNodeKey: targetNodeKey,
			positionNodeKey: positionNodeKey,
			sourceNodeKey: sourceNodeKey,
			scene: scene,
			questKind: QuestMarkerKind.Objective,
			spawnCategory: SpawnCategory.Alive,
			priority: 0,
			subText: $"Talk to {displayName}",
			x: 1f,
			y: 2f,
			z: 3f,
			keepWhileCorpsePresent: false,
			corpseSubText: null,
			isNightSpawnNode: false,
			displayName: displayName,
			unlockBlockedReason: null);
}
