using AdventureGuide.Graph;
using AdventureGuide.Plan;
using AdventureGuide.Resolution;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class NavigationTargetResolverTests
{
    [Fact]
    public void Resolve_QuestKey_UsesCompiledFrontierTargets()
    {
        var guide = new CompiledGuideBuilder()
            .AddCharacter("char:giver", scene: "Forest", x: 10f, y: 20f, z: 30f)
            .AddQuest("quest:a", dbName: "QUESTA", givers: new[] { "char:giver" })
            .Build();
        var graph = new TestGraphBuilder()
            .AddQuest("quest:a", "Quest A", dbName: "QUESTA")
            .AddCharacter("char:giver", "Guide NPC", scene: "Forest")
            .Build();
        var phases = new QuestPhaseTracker(guide);
        phases.Initialize(Array.Empty<string>(), Array.Empty<string>(), new Dictionary<string, int>(), Array.Empty<string>());
        var frontier = new EffectiveFrontier(guide, phases);
        var unlocks = new UnlockPredicateEvaluator(guide, phases);
        var sourceResolver = new SourceResolver(guide, phases, unlocks, new StubLivePositionProvider());
        var targetResolver = new NavigationTargetResolver(
            guide,
            graph,
            frontier,
            sourceResolver);

        var targets = targetResolver.Resolve("quest:a", "Forest");

        Assert.Single(targets);
        Assert.Equal("char:giver", targets[0].TargetNodeKey);
        Assert.Equal("char:giver", targets[0].SourceKey);
        Assert.Equal("Quest A", targets[0].GoalNode.Node.DisplayName);
        Assert.Equal("Guide NPC", targets[0].TargetNode.Node.DisplayName);
        Assert.Equal(QuestMarkerKind.QuestGiver, targets[0].Semantic.PreferredMarkerKind);
        Assert.Equal(ResolvedActionKind.Talk, targets[0].Semantic.ActionKind);
        Assert.Equal("Talk to char:giver", targets[0].Explanation.PrimaryText);
        Assert.Equal(10f, targets[0].X);
        Assert.Equal(20f, targets[0].Y);
        Assert.Equal(30f, targets[0].Z);
    }

    [Fact]
    public void Resolve_NonQuestKey_ReturnsEmptyWhenCompiledNavigationOnlySupportsQuests()
    {
        var guide = new CompiledGuideBuilder()
            .AddCharacter("char:manual", scene: "Forest", x: 40f, y: 50f, z: 60f)
            .Build();
        var graph = new TestGraphBuilder()
            .AddCharacter("char:manual", "Manual NPC", scene: "Forest")
            .Build();
        var phases = new QuestPhaseTracker(guide);
        phases.Initialize(Array.Empty<string>(), Array.Empty<string>(), new Dictionary<string, int>(), Array.Empty<string>());
        var frontier = new EffectiveFrontier(guide, phases);
        var unlocks = new UnlockPredicateEvaluator(guide, phases);
        var sourceResolver = new SourceResolver(guide, phases, unlocks, new StubLivePositionProvider());
        var targetResolver = new NavigationTargetResolver(
            guide,
            graph,
            frontier,
            sourceResolver);

        var targets = targetResolver.Resolve("char:manual", "Forest");

        Assert.Empty(targets);
    }

    [Fact]
    public void Version_UsesProvidedVersionSource()
    {
        int version = 1;
        var guide = new CompiledGuideBuilder().Build();
        var graph = new TestGraphBuilder().Build();
        var phases = new QuestPhaseTracker(guide);
        phases.Initialize(Array.Empty<string>(), Array.Empty<string>(), new Dictionary<string, int>(), Array.Empty<string>());
        var frontier = new EffectiveFrontier(guide, phases);
        var unlocks = new UnlockPredicateEvaluator(guide, phases);
        var sourceResolver = new SourceResolver(guide, phases, unlocks, new StubLivePositionProvider());
        var targetResolver = new NavigationTargetResolver(
            guide,
            graph,
            frontier,
            sourceResolver,
            () => version);

        Assert.Equal(1, targetResolver.Version);
        version = 2;
        Assert.Equal(2, targetResolver.Version);
    }


}
