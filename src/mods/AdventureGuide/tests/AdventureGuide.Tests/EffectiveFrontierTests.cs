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

    [Fact]
    public void Implicit_quest_is_accepted_and_included_in_frontier()
    {
        // Implicit quests skip ReadyToAccept — QuestPhaseTracker assigns Accepted
        // directly. EffectiveFrontier must include them so the resolution pipeline
        // can emit objectives and completion targets.
        var guide = new CompiledGuideBuilder()
            .AddQuest("quest:a", dbName: "QUESTA", implicit_: true)
            .Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(Array.Empty<string>(), Array.Empty<string>(), new Dictionary<string, int>(), Array.Empty<string>());
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
        // quest:a (explicit, not-ready) requires quest:b (implicit).
        // QuestPhaseTracker places quest:b in Accepted directly, so the frontier
        // for quest:a resolves to quest:b's Accepted entry.
        // Builder sorts quest keys alphabetically: quest:a=0, quest:b=1.
        var guide = new CompiledGuideBuilder()
            .AddQuest("quest:b", dbName: "QUESTB", implicit_: true)
            .AddQuest("quest:a", dbName: "QUESTA", prereqs: new[] { "quest:b" })
            .Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(Array.Empty<string>(), Array.Empty<string>(), new Dictionary<string, int>(), Array.Empty<string>());
        var frontier = new EffectiveFrontier(guide, tracker);
        var results = new List<FrontierEntry>();

        frontier.Resolve(0, results, -1); // quest:a is index 0 (alphabetical)

        Assert.Single(results);
        Assert.Equal(1, results[0].QuestIndex);  // quest:b is index 1
        Assert.Equal(QuestPhase.Accepted, results[0].Phase);
        Assert.Equal(0, results[0].RequiredForQuestIndex); // required for quest:a
    }
}
