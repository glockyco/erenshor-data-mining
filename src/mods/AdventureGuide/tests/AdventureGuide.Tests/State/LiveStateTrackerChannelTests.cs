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

        var snapshot = tracker.GetLiveSourceSnapshot("missing-source", targetNode: null!);

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
