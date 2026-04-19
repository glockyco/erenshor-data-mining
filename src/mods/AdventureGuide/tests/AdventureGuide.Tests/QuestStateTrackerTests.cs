using AdventureGuide.State;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class QuestStateTrackerTests
{
    [Fact]
    public void OnQuestAssigned_FiresQuestLogChangedEventAfterStateCommit()
    {
        var guide = new CompiledGuideBuilder().AddQuest("quest:a", dbName: "QUESTA").Build();
        var tracker = new QuestStateTracker(guide, new GuideDependencyEngine());
        tracker.LoadState(
            currentZone: "Forest",
            activeQuests: Array.Empty<string>(),
            completedQuests: Array.Empty<string>(),
            inventoryCounts: new Dictionary<string, int>(),
            keyringItemKeys: Array.Empty<string>()
        );

        bool sawCommittedState = false;
        int observedVersion = -1;
        ChangeSet? observedChangeSet = null;
        tracker.QuestLogChangedEvent += changeSet =>
        {
            observedChangeSet = changeSet;
            observedVersion = tracker.Version;
            sawCommittedState = tracker.ActiveQuests.Contains("QUESTA")
                && tracker.LastChangeSet == changeSet;
        };

        var changeSet = tracker.OnQuestAssigned("QUESTA");

        Assert.True(sawCommittedState);
        Assert.Equal(1, observedVersion);
        Assert.Same(changeSet, observedChangeSet);
    }

    [Fact]
    public void LoadState_FiresLoadedEventAfterStateCommit()
    {
        var guide = new CompiledGuideBuilder().AddItem("item:wood").Build();
        var tracker = new QuestStateTracker(guide, new GuideDependencyEngine());

        string observedZone = string.Empty;
        int observedCount = -1;
        ChangeSet? observedChangeSet = null;
        tracker.LoadedEvent += changeSet =>
        {
            observedChangeSet = changeSet;
            observedZone = tracker.CurrentZone;
            observedCount = tracker.CountItem("item:wood");
        };

        tracker.LoadState(
            currentZone: "Forest",
            activeQuests: Array.Empty<string>(),
            completedQuests: Array.Empty<string>(),
            inventoryCounts: new Dictionary<string, int>(StringComparer.Ordinal)
            {
                ["item:wood"] = 2,
            },
            keyringItemKeys: Array.Empty<string>()
        );

        Assert.Equal("Forest", observedZone);
        Assert.Equal(2, observedCount);
        Assert.NotNull(observedChangeSet);
        Assert.Same(observedChangeSet, tracker.LastChangeSet);
    }
}
