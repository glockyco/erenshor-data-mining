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
        var phases = new QuestPhaseTracker(guide);
        phases.Initialize(Array.Empty<string>(), Array.Empty<string>(), new Dictionary<string, int>(), Array.Empty<string>());
        var frontier = new EffectiveFrontier(guide, phases);
        var unlocks = new UnlockPredicateEvaluator(guide, phases);
        var sourceResolver = new SourceResolver(guide, phases, unlocks, new StubLivePositionProvider());
        var targetResolver = new NavigationTargetResolver(
            guide,
            frontier,
            sourceResolver,
            _ => Array.Empty<ResolvedQuestTarget>());

        var targets = targetResolver.Resolve("quest:a", "Forest");

        Assert.Single(targets);
        Assert.Equal(ResolvedTargetRole.Giver, targets[0].Role);
        Assert.Equal(QuestMarkerKind.QuestGiver, targets[0].Semantic.PreferredMarkerKind);
        Assert.Equal(ResolvedActionKind.Talk, targets[0].Semantic.ActionKind);
        Assert.Equal(10f, targets[0].X);
        Assert.Equal(20f, targets[0].Y);
        Assert.Equal(30f, targets[0].Z);
    }

    [Fact]
    public void Resolve_NonQuestKey_ConvertsLegacyNavigationTargets()
    {
        var guide = new CompiledGuideBuilder()
            .AddCharacter("char:manual", scene: "Forest", x: 40f, y: 50f, z: 60f)
            .Build();
        var phases = new QuestPhaseTracker(guide);
        phases.Initialize(Array.Empty<string>(), Array.Empty<string>(), new Dictionary<string, int>(), Array.Empty<string>());
        var frontier = new EffectiveFrontier(guide, phases);
        var unlocks = new UnlockPredicateEvaluator(guide, phases);
        var sourceResolver = new SourceResolver(guide, phases, unlocks, new StubLivePositionProvider());
        var legacyTarget = MakeLegacyTarget("char:manual", "Forest", "char:manual", 40f, 50f, 60f);
        var targetResolver = new NavigationTargetResolver(
            guide,
            frontier,
            sourceResolver,
            key => key == "char:manual"
                ? new[] { legacyTarget }
                : Array.Empty<ResolvedQuestTarget>());

        var targets = targetResolver.Resolve("char:manual", "Forest");

        Assert.Single(targets);
        Assert.Equal(ResolvedTargetRole.Objective, targets[0].Role);
        Assert.Equal(QuestMarkerKind.Objective, targets[0].Semantic.PreferredMarkerKind);
        Assert.Equal(ResolvedActionKind.Talk, targets[0].Semantic.ActionKind);
        Assert.Equal(40f, targets[0].X);
        Assert.Equal(50f, targets[0].Y);
        Assert.Equal(60f, targets[0].Z);
    }

    private static ResolvedQuestTarget MakeLegacyTarget(
        string targetNodeKey,
        string scene,
        string sourceKey,
        float x,
        float y,
        float z)
    {
        var node = new Node
        {
            Key = targetNodeKey,
            Type = NodeType.Character,
            DisplayName = "Manual NPC",
        };
        var ctx = new ResolvedNodeContext(node.Key, node);
        var semantic = new ResolvedActionSemantic(
            NavigationGoalKind.TalkToTarget,
            NavigationTargetKind.Character,
            ResolvedActionKind.Talk,
            goalNodeKey: null,
            goalQuantity: null,
            keywordText: null,
            payloadText: null,
            targetIdentityText: node.DisplayName,
            contextText: null,
            rationaleText: null,
            zoneText: scene,
            availabilityText: null,
            preferredMarkerKind: QuestMarkerKind.Objective,
            markerPriority: 0);
        var explanation = NavigationExplanationBuilder.Build(semantic, ctx, ctx);
        return new ResolvedQuestTarget(
            targetNodeKey,
            scene,
            sourceKey,
            ctx,
            ctx,
            semantic,
            explanation,
            x,
            y,
            z,
            isActionable: true);
    }
}
