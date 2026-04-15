using AdventureGuide.Diagnostics;
using AdventureGuide.Plan;
using AdventureGuide.Resolution;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class ResolutionTracerTests
{
    [Fact]
    public void Tracer_captures_quest_phase_and_frontier_entry()
    {
        var guide = new CompiledGuideBuilder()
            .AddQuest("quest:a", dbName: "QUESTA")
            .Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(
            Array.Empty<string>(),
            Array.Empty<string>(),
            new Dictionary<string, int>(),
            Array.Empty<string>());
        var frontier = new EffectiveFrontier(guide, tracker);
        var unlocks = new UnlockPredicateEvaluator(guide, tracker);
        var sourceResolver = new SourceResolver(guide, tracker, unlocks, new NullLivePositionProvider());
        var resolver = new NavigationTargetResolver(guide, frontier, sourceResolver);

        var tracer = new TextResolutionTracer();
        resolver.Resolve("quest:a", "TestScene", tracer);
        var output = tracer.GetTrace();

        Assert.Contains("quest:a", output);
        Assert.Contains("Phase:", output);
        Assert.Contains("Frontier:", output);
        Assert.Contains("ReadyToAccept", output);
        Assert.Contains("Total targets:", output);
    }

    [Fact]
    public void Tracer_captures_accepted_quest_targets()
    {
        var guide = new CompiledGuideBuilder()
            .AddQuest("quest:b", dbName: "QUESTB", givers: new[] { "character:npc" })
            .AddCharacter("character:npc", scene: "Zone1", x: 10, y: 0, z: 20)
            .Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(
            Array.Empty<string>(),
            new[] { "QUESTB" }, // active
            new Dictionary<string, int>(),
            Array.Empty<string>());
        var frontier = new EffectiveFrontier(guide, tracker);
        var unlocks = new UnlockPredicateEvaluator(guide, tracker);
        var sourceResolver = new SourceResolver(guide, tracker, unlocks, new NullLivePositionProvider());
        var resolver = new NavigationTargetResolver(guide, frontier, sourceResolver);

        var tracer = new TextResolutionTracer();
        resolver.Resolve("quest:b", "Zone1", tracer);
        var output = tracer.GetTrace();

        Assert.Contains("Accepted", output);
    }

    [Fact]
    public void Null_tracer_does_not_throw()
    {
        var guide = new CompiledGuideBuilder()
            .AddQuest("quest:c", dbName: "QUESTC")
            .Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(
            Array.Empty<string>(),
            Array.Empty<string>(),
            new Dictionary<string, int>(),
            Array.Empty<string>());
        var frontier = new EffectiveFrontier(guide, tracker);
        var unlocks = new UnlockPredicateEvaluator(guide, tracker);
        var sourceResolver = new SourceResolver(guide, tracker, unlocks, new NullLivePositionProvider());
        var resolver = new NavigationTargetResolver(guide, frontier, sourceResolver);

        // Should not throw with null tracer (default)
        var results = resolver.Resolve("quest:c", "TestScene");
        Assert.NotNull(results);
    }

    private sealed class NullLivePositionProvider : ILivePositionProvider
    {
        public WorldPosition? GetLivePosition(int nodeId) => null;
        public bool IsAlive(int nodeId) => false;
    }
}
