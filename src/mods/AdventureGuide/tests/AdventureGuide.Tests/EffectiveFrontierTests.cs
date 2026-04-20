using AdventureGuide.Frontier;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class EffectiveFrontierTests
{
    [Fact]
    public void Ready_quest_returns_itself()
    {
        var guide = new CompiledGuideBuilder().AddQuest("quest:a", dbName: "QUESTA").Build();
        var tracker = QuestPhaseTrackerFactory.Build(
            guide,
            Array.Empty<string>(),
            Array.Empty<string>(),
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        var frontier = new EffectiveFrontier(guide, tracker);
        var results = new List<FrontierEntry>();

        frontier.Resolve(0, results, -1);

        Assert.Single(results);
        Assert.Equal(0, results[0].QuestIndex);
        Assert.Equal(QuestPhase.ReadyToAccept, results[0].Phase);
        Assert.Equal(-1, results[0].RequiredForQuestIndex);
    }

    [Fact]
    public void Completed_quest_returns_no_entries()
    {
        var guide = new CompiledGuideBuilder().AddQuest("quest:a", dbName: "QUESTA").Build();
        var tracker = QuestPhaseTrackerFactory.Build(
            guide,
            new[] { "QUESTA" },
            Array.Empty<string>(),
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        var frontier = new EffectiveFrontier(guide, tracker);
        var results = new List<FrontierEntry>();

        frontier.Resolve(0, results, -1);

        Assert.Empty(results);
    }

    [Fact]
    public void Not_ready_quest_returns_prereq_frontier()
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
        var frontier = new EffectiveFrontier(guide, tracker);
        var results = new List<FrontierEntry>();

        frontier.Resolve(0, results, -1);

        Assert.Single(results);
        Assert.Equal(1, results[0].QuestIndex);
        Assert.Equal(QuestPhase.ReadyToAccept, results[0].Phase);
        Assert.Equal(0, results[0].RequiredForQuestIndex);
    }

    [Fact]
    public void Implicit_quest_is_accepted_and_included_in_frontier()
    {
        var guide = new CompiledGuideBuilder()
            .AddQuest("quest:a", dbName: "QUESTA", implicit_: true)
            .Build();
        var tracker = QuestPhaseTrackerFactory.Build(
            guide,
            Array.Empty<string>(),
            Array.Empty<string>(),
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        var frontier = new EffectiveFrontier(guide, tracker);
        var results = new List<FrontierEntry>();

        frontier.Resolve(0, results, -1);

        Assert.Single(results);
        Assert.Equal(0, results[0].QuestIndex);
        Assert.Equal(QuestPhase.Accepted, results[0].Phase);
    }

    [Fact]
    public void Implicit_prereq_is_accepted_and_included_in_frontier()
    {
        var guide = new CompiledGuideBuilder()
            .AddQuest("quest:b", dbName: "QUESTB", implicit_: true)
            .AddQuest("quest:a", dbName: "QUESTA", prereqs: new[] { "quest:b" })
            .Build();
        var tracker = QuestPhaseTrackerFactory.Build(
            guide,
            Array.Empty<string>(),
            Array.Empty<string>(),
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        var frontier = new EffectiveFrontier(guide, tracker);
        var results = new List<FrontierEntry>();

        frontier.Resolve(0, results, -1);

        Assert.Single(results);
        Assert.Equal(1, results[0].QuestIndex);
        Assert.Equal(QuestPhase.Accepted, results[0].Phase);
        Assert.Equal(0, results[0].RequiredForQuestIndex);
    }

    [Fact]
    public void Ready_quest_with_quest_giver_returns_giver_quest_frontier()
    {
        var guide = new CompiledGuideBuilder()
            .AddCharacter("char:percy")
            .AddQuest("quest:percy", dbName: "PERCY", givers: new[] { "char:percy" })
            .AddQuest("quest:root", dbName: "ROOT", givers: new[] { "quest:percy" })
            .Build();
        var tracker = QuestPhaseTrackerFactory.Build(
            guide,
            Array.Empty<string>(),
            Array.Empty<string>(),
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        var frontier = new EffectiveFrontier(guide, tracker);
        var results = new List<FrontierEntry>();
        Assert.True(guide.TryGetNodeId("quest:root", out int rootNodeId));
        Assert.True(guide.TryGetNodeId("quest:percy", out int percyNodeId));
        int rootIndex = guide.FindQuestIndex(rootNodeId);
        int percyIndex = guide.FindQuestIndex(percyNodeId);

        frontier.Resolve(rootIndex, results, -1);

        Assert.Single(results);
        Assert.Equal(percyIndex, results[0].QuestIndex);
        Assert.Equal(QuestPhase.ReadyToAccept, results[0].Phase);
        Assert.Equal(rootIndex, results[0].RequiredForQuestIndex);
    }
}
