using System.IO;
using AdventureGuide.Plan;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class QuestPhaseTrackerSubscriptionTests
{
    [Fact]
    public void LoadState_UpdatesItemCountsWithoutManualSync()
    {
        var harness = QuestPhaseTrackerHarness.Build();
        var phases = harness.Phases;
        var state = harness.State;
        int itemIndex = harness.ItemIndex("item:wood");

        Assert.Equal(0, phases.GetItemCount(itemIndex));

        state.LoadState(
            currentZone: "Forest",
            activeQuests: Array.Empty<string>(),
            completedQuests: Array.Empty<string>(),
            inventoryCounts: new Dictionary<string, int>(StringComparer.Ordinal)
            {
                ["item:wood"] = 3,
            },
            keyringItemKeys: Array.Empty<string>()
        );

        Assert.Equal(3, phases.GetItemCount(itemIndex));
    }

    [Fact]
    public void QuestCompleted_MovesPhaseToCompletedWithoutManualSync()
    {
        var harness = QuestPhaseTrackerHarness.Build();
        var phases = harness.Phases;
        var state = harness.State;
        int questIndex = harness.QuestIndex("FetchWater");

        state.OnQuestCompleted("FetchWater");

        Assert.Equal(QuestPhase.Completed, phases.GetPhase(questIndex));
    }

    [Fact]
    public void QuestAssigned_MovesPhaseToAcceptedWithoutManualSync()
    {
        var harness = QuestPhaseTrackerHarness.Build();
        var phases = harness.Phases;
        var state = harness.State;
        int questIndex = harness.QuestIndex("FetchWater");

        state.OnQuestAssigned("FetchWater");

        Assert.Equal(QuestPhase.Accepted, phases.GetPhase(questIndex));
    }

    [Fact]
    public void Plugin_DoesNotExposeSyncCompiledQuestTracker()
    {
        string pluginSource = File.ReadAllText(Path.Combine(FindModRoot(), "src", "Plugin.cs"));

        Assert.DoesNotContain("SyncCompiledQuestTracker", pluginSource, StringComparison.Ordinal);
    }

    private static string FindModRoot()
    {
        var current = new DirectoryInfo(AppContext.BaseDirectory);
        while (current != null)
        {
            if (File.Exists(Path.Combine(current.FullName, "AdventureGuide.csproj")))
                return current.FullName;

            current = current.Parent;
        }

        throw new DirectoryNotFoundException("AdventureGuide.csproj not found from test base directory.");
    }
}
