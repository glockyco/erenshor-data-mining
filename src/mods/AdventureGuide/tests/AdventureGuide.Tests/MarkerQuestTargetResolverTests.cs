using AdventureGuide.Markers;
using AdventureGuide.Plan;
using AdventureGuide.Resolution;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class MarkerQuestTargetResolverTests
{
    [Fact]
    public void Resolve_ReturnsCompiledTargetsForQuestDbName()
    {
        var guide = new CompiledGuideBuilder()
            .AddCharacter("char:giver", scene: "Forest", x: 10f, y: 20f, z: 30f)
            .AddQuest("quest:a", dbName: "QUESTA", givers: new[] { "char:giver" })
            .Build();
        var phases = new QuestPhaseTracker(guide);
        phases.Initialize(Array.Empty<string>(), Array.Empty<string>(), new Dictionary<string, int>(), Array.Empty<string>());
        var frontier = new EffectiveFrontier(guide, phases);
        var unlocks = new UnlockPredicateEvaluator(guide, phases);
        var sourceResolver = new SourceResolver(guide, phases, unlocks, new StubLivePositionProvider());
        var resolver = new MarkerQuestTargetResolver(guide, frontier, sourceResolver);

        var targets = resolver.Resolve("QUESTA", "Forest");

        Assert.Single(targets);
        Assert.Equal(QuestMarkerKind.QuestGiver, targets[0].Semantic.PreferredMarkerKind);
        Assert.Equal(10f, targets[0].X);
        Assert.Equal(20f, targets[0].Y);
        Assert.Equal(30f, targets[0].Z);
    }

    [Fact]
    public void Resolve_ThrowsWhenQuestDbNameMissingFromCompiledGuide()
    {
        var guide = new CompiledGuideBuilder().Build();
        var phases = new QuestPhaseTracker(guide);
        phases.Initialize(Array.Empty<string>(), Array.Empty<string>(), new Dictionary<string, int>(), Array.Empty<string>());
        var frontier = new EffectiveFrontier(guide, phases);
        var unlocks = new UnlockPredicateEvaluator(guide, phases);
        var sourceResolver = new SourceResolver(guide, phases, unlocks, new StubLivePositionProvider());
        var resolver = new MarkerQuestTargetResolver(guide, frontier, sourceResolver);

        var ex = Assert.Throws<InvalidOperationException>(() => resolver.Resolve("MISSING", "Forest"));

        Assert.Contains("MISSING", ex.Message, System.StringComparison.Ordinal);
    }
}
