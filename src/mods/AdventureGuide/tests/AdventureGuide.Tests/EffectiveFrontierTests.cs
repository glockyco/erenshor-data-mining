using AdventureGuide.Plan;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class EffectiveFrontierTests
{
    [Fact]
    public void Ready_quest_returns_itself()
    {
        var guide = new CompiledGuideBuilder().AddQuest("quest:a", dbName: "QUESTA").Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(Array.Empty<string>(), Array.Empty<string>(), new Dictionary<string, int>(), Array.Empty<string>());
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
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(new[] { "QUESTA" }, Array.Empty<string>(), new Dictionary<string, int>(), Array.Empty<string>());
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
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(Array.Empty<string>(), Array.Empty<string>(), new Dictionary<string, int>(), Array.Empty<string>());
        var frontier = new EffectiveFrontier(guide, tracker);
        var results = new List<FrontierEntry>();

        frontier.Resolve(0, results, -1);

        Assert.Single(results);
        Assert.Equal(1, results[0].QuestIndex);
        Assert.Equal(QuestPhase.ReadyToAccept, results[0].Phase);
        Assert.Equal(0, results[0].RequiredForQuestIndex);
    }
}
