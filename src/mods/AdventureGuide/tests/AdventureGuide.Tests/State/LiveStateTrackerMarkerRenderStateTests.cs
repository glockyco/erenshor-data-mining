using AdventureGuide.State;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests.State;

public sealed class LiveSourceSnapshotTests
{
    [Fact]
    public void GetLiveSourceSnapshot_ReturnsUnknown_WhenPositionNodeIsMissing()
    {
        var guide = new CompiledGuideBuilder()
            .AddCharacter("char:leaf", scene: "Town", x: 1f, y: 2f, z: 3f)
            .Build();
        var tracker = CreateTracker(guide);

        var state = tracker.GetLiveSourceSnapshot("spawn:leaf-1", guide.GetNode("char:leaf")!);

        Assert.Equal(LiveSourceSnapshot.Unknown("spawn:leaf-1", "char:leaf"), state);
    }

    [Fact]
    public void GetLiveSourceSnapshot_ReturnsUnknown_WhenTargetNodeIsMissing()
    {
        var tracker = CreateTracker(new CompiledGuideBuilder().Build());

        var state = tracker.GetLiveSourceSnapshot("spawn:leaf-1", targetNode: null!);

        Assert.Equal(LiveSourceSnapshot.Unknown("spawn:leaf-1", targetNodeKey: null), state);
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

        Assert.Equal(LiveSourceOccupancy.Dead, deadWithCorpse.Occupancy);
        Assert.False(deadWithCorpse.IsActionable);
        Assert.Equal(LiveSourceAnchor.LiveObject, deadWithCorpse.Anchor);
        Assert.Equal((4f, 5f, 6f), deadWithCorpse.LivePosition);
        Assert.Equal((4f, 8.3f, 6f), deadWithCorpse.AnchoredLivePosition);
        Assert.Equal(12f, deadWithCorpse.RespawnSeconds);

        Assert.Equal(LiveSourceOccupancy.Dead, deadNoCorpse.Occupancy);
        Assert.False(deadNoCorpse.IsActionable);
        Assert.Equal(LiveSourceAnchor.Source, deadNoCorpse.Anchor);
        Assert.Null(deadNoCorpse.LivePosition);
        Assert.Null(deadNoCorpse.AnchoredLivePosition);
        Assert.Equal(18f, deadNoCorpse.RespawnSeconds);

        Assert.Equal(LiveSourceOccupancy.Dead, zoneReentry.Occupancy);
        Assert.False(zoneReentry.IsActionable);
        Assert.True(zoneReentry.RequiresZoneReentry);
        Assert.Equal(LiveSourceAnchor.Source, zoneReentry.Anchor);
        Assert.Null(zoneReentry.LivePosition);
        Assert.Null(zoneReentry.AnchoredLivePosition);

        Assert.Equal(LiveSourceKind.MiningNode, mined.Kind);
        Assert.Equal(LiveSourceOccupancy.Mined, mined.Occupancy);
        Assert.False(mined.IsActionable);
        Assert.Equal(LiveSourceAnchor.Source, mined.Anchor);
        Assert.Equal(30f, mined.RespawnSeconds);

        Assert.Equal(LiveSourceKind.ItemBag, pickedUp.Kind);
        Assert.Equal(LiveSourceOccupancy.PickedUp, pickedUp.Occupancy);
        Assert.False(pickedUp.IsActionable);
        Assert.Equal(LiveSourceAnchor.Source, pickedUp.Anchor);
        Assert.Equal(45f, pickedUp.RespawnSeconds);

        Assert.Equal(LiveSourceOccupancy.UnlockBlocked, blocked.Occupancy);
        Assert.False(blocked.IsActionable);
        Assert.Equal(LiveSourceAnchor.Source, blocked.Anchor);
        Assert.Equal("Requires: quest:gate", blocked.UnlockReason);
    }

    [Fact]
    public void LiveSourceSnapshot_RepresentsDisabledCharacter()
    {
        var disabled = LiveSourceSnapshot.Disabled("spawn:gate", "char:gate");

        Assert.Equal(LiveSourceKind.Character, disabled.Kind);
        Assert.Equal(LiveSourceOccupancy.Disabled, disabled.Occupancy);
        Assert.False(disabled.IsActionable);
        Assert.Equal(LiveSourceAnchor.Source, disabled.Anchor);
    }

    private static LiveStateTracker CreateTracker(AdventureGuide.CompiledGuide.CompiledGuide guide)
    {
        var phases = new QuestStateTracker(guide);
        var unlocks = new UnlockEvaluator(guide, new GameState(guide), phases);
        return new LiveStateTracker(guide, unlocks);
    }
}
