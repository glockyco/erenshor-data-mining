using AdventureGuide.Frontier;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class QuestPhaseTrackerTests
{
    [Fact]
    public void Quest_without_prereqs_is_ready_to_accept()
    {
        var guide = new CompiledGuideBuilder().AddQuest("quest:a", dbName: "QUESTA").Build();
        var tracker = QuestPhaseTrackerFactory.Build(
            guide,
            completedQuestDbNames: Array.Empty<string>(),
            activeQuestDbNames: Array.Empty<string>(),
            inventory: new Dictionary<string, int>(),
            keyringItems: Array.Empty<string>()
        );

        Assert.Equal(QuestPhase.ReadyToAccept, tracker.GetPhase(0));
    }

    [Fact]
    public void Quest_with_incomplete_prereq_is_not_ready()
    {
        var guide = new CompiledGuideBuilder()
            .AddQuest("quest:a", dbName: "QUESTA", prereqs: new[] { "quest:b" })
            .AddQuest("quest:b", dbName: "QUESTB")
            .Build();
        var tracker = QuestPhaseTrackerFactory.Build(
            guide,
            Array.Empty<string>(),
            Array.Empty<string>(),
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );

        Assert.Equal(QuestPhase.NotReady, tracker.GetPhase(0));
        Assert.Equal(QuestPhase.ReadyToAccept, tracker.GetPhase(1));
    }

    [Fact]
    public void Completing_prereq_unblocks_dependent()
    {
        var guide = new CompiledGuideBuilder()
            .AddQuest("quest:a", dbName: "QUESTA", prereqs: new[] { "quest:b" })
            .AddQuest("quest:b", dbName: "QUESTB")
            .Build();
        var (state, tracker) = QuestPhaseTrackerFactory.BuildWithState(
            guide,
            Array.Empty<string>(),
            Array.Empty<string>(),
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        state.OnQuestCompleted("QUESTB");

        Assert.Equal(QuestPhase.ReadyToAccept, tracker.GetPhase(0));
        Assert.Equal(QuestPhase.Completed, tracker.GetPhase(1));
    }

    [Fact]
    public void Active_quest_is_accepted()
    {
        var guide = new CompiledGuideBuilder().AddQuest("quest:a", dbName: "QUESTA").Build();
        var tracker = QuestPhaseTrackerFactory.Build(
            guide,
            Array.Empty<string>(),
            new[] { "QUESTA" },
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );

        Assert.Equal(QuestPhase.Accepted, tracker.GetPhase(0));
    }

    [Fact]
    public void Completed_quest_is_completed()
    {
        var guide = new CompiledGuideBuilder().AddQuest("quest:a", dbName: "QUESTA").Build();
        var tracker = QuestPhaseTrackerFactory.Build(
            guide,
            new[] { "QUESTA" },
            Array.Empty<string>(),
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );

        Assert.Equal(QuestPhase.Completed, tracker.GetPhase(0));
        Assert.True(tracker.IsCompleted(0));
    }
}
