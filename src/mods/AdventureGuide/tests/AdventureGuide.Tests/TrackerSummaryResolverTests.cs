using AdventureGuide.Plan;
using AdventureGuide.Resolution;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class TrackerSummaryResolverTests
{
    [Fact]
    public void Resolve_UsesCompiledFrontierSummaryWhenQuestIsPresent()
    {
        var guide = new CompiledGuideBuilder()
            .AddCharacter("char:giver", scene: "Forest", x: 10f, y: 20f, z: 30f)
            .AddQuest("quest:a", dbName: "QUESTA", givers: new[] { "char:giver" })
            .Build();
        var phases = new QuestPhaseTracker(guide);
        phases.Initialize(Array.Empty<string>(), Array.Empty<string>(), new Dictionary<string, int>(), Array.Empty<string>());
        var frontier = new EffectiveFrontier(guide, phases);
        var sourceResolver = new SourceResolver(guide, phases, new UnlockPredicateEvaluator(guide, phases), new StubLivePositionProvider());
        var resolver = new TrackerSummaryResolver(guide, phases, frontier, sourceResolver);

        var summary = resolver.Resolve("quest:a", "QUESTA", "Forest");

        var resolved = Assert.IsType<TrackerSummary>(summary);
        Assert.Equal("Talk to char:giver", resolved.PrimaryText);
        Assert.Null(resolved.SecondaryText);
    }

    [Fact]
    public void Resolve_Quest_with_quest_giver_uses_nested_quest_frontier_summary()
    {
        var guide = new CompiledGuideBuilder()
            .AddCharacter("char:percy")
            .AddQuest("quest:percy", dbName: "PERCY", givers: new[] { "char:percy" })
            .AddQuest("quest:root", dbName: "ROOT", givers: new[] { "quest:percy" })
            .Build();
        var phases = new QuestPhaseTracker(guide);
        phases.Initialize(Array.Empty<string>(), Array.Empty<string>(), new Dictionary<string, int>(), Array.Empty<string>());
        var frontier = new EffectiveFrontier(guide, phases);
        var sourceResolver = new SourceResolver(guide, phases, new UnlockPredicateEvaluator(guide, phases), new StubLivePositionProvider());
        var resolver = new TrackerSummaryResolver(guide, phases, frontier, sourceResolver);

        var summary = resolver.Resolve("quest:root", "ROOT", "");

        var resolved = Assert.IsType<TrackerSummary>(summary);
        Assert.Equal("Talk to char:percy", resolved.PrimaryText);
    }

    [Fact]
    public void Resolve_Blocked_item_source_uses_unlock_quest_summary()
    {
        var guide = new CompiledGuideBuilder()
            .AddItem("item:crystal")
            .AddCharacter("char:keeper", scene: "Vault", x: 40f, y: 50f, z: 60f)
            .AddItemSource("item:crystal", "char:keeper")
            .AddCharacter("char:elder", scene: "Town", x: 5f, y: 6f, z: 7f)
            .AddQuest("quest:gate", dbName: "GATE", givers: new[] { "char:elder" })
            .AddUnlockPredicate("char:keeper", "quest:gate")
            .AddQuest("quest:root", dbName: "ROOT", requiredItems: new[] { ("item:crystal", 1) })
            .Build();
        var phases = new QuestPhaseTracker(guide);
        phases.Initialize(Array.Empty<string>(), new[] { "ROOT" }, new Dictionary<string, int>(), Array.Empty<string>());
        var frontier = new EffectiveFrontier(guide, phases);
        var sourceResolver = new SourceResolver(guide, phases, new UnlockPredicateEvaluator(guide, phases), new StubLivePositionProvider());
        var resolver = new TrackerSummaryResolver(guide, phases, frontier, sourceResolver);

        var summary = resolver.Resolve("quest:root", "ROOT", "Town");

        var resolved = Assert.IsType<TrackerSummary>(summary);
        Assert.Equal("Talk to char:elder", resolved.PrimaryText);
    }

    [Fact]
    public void Resolve_ReturnsNullWhenCompiledQuestIsMissing()
    {
        var guide = new CompiledGuideBuilder()
            .AddQuest("quest:other", dbName: "OTHER")
            .Build();
        var phases = new QuestPhaseTracker(guide);
        phases.Initialize(Array.Empty<string>(), Array.Empty<string>(), new Dictionary<string, int>(), Array.Empty<string>());
        var frontier = new EffectiveFrontier(guide, phases);
        var sourceResolver = new SourceResolver(guide, phases, new UnlockPredicateEvaluator(guide, phases), new StubLivePositionProvider());
        var resolver = new TrackerSummaryResolver(guide, phases, frontier, sourceResolver);

        var summary = resolver.Resolve("quest:missing", "MISSING", "");

        Assert.Null(summary);
    }
}
