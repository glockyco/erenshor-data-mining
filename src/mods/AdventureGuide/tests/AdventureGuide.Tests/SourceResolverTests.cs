using AdventureGuide.Plan;
using AdventureGuide.Resolution;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests;

internal sealed class StubLivePositionProvider : ILivePositionProvider
{
    public WorldPosition? GetLivePosition(int spawnNodeId) => null;

    public bool IsAlive(int spawnNodeId) => false;
}

public sealed class SourceResolverTests
{
    [Fact]
    public void Ready_to_accept_resolves_giver_position_with_giver_semantics()
    {
        var guide = new CompiledGuideBuilder()
            .AddCharacter("char:guard", scene: "Forest", x: 10f, y: 20f, z: 30f)
            .AddQuest("quest:a", dbName: "QUESTA", givers: new[] { "char:guard" })
            .Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(Array.Empty<string>(), Array.Empty<string>(), new Dictionary<string, int>(), Array.Empty<string>());
        var evaluator = new UnlockPredicateEvaluator(guide, tracker);
        var resolver = new SourceResolver(guide, tracker, evaluator, new StubLivePositionProvider());

        var targets = resolver.ResolveTargets(new FrontierEntry(0, QuestPhase.ReadyToAccept, -1), "Forest");

        guide.TryGetNodeId("char:guard", out int giverId);
        Assert.Single(targets);
        Assert.Equal(giverId, targets[0].TargetNodeId);
        Assert.Equal(giverId, targets[0].PositionNodeId);
        Assert.Equal(ResolvedTargetRole.Giver, targets[0].Role);
        Assert.Equal(QuestMarkerKind.QuestGiver, targets[0].Semantic.PreferredMarkerKind);
        Assert.Equal(ResolvedActionKind.Talk, targets[0].Semantic.ActionKind);
        Assert.Equal(10f, targets[0].X);
        Assert.Equal(20f, targets[0].Y);
        Assert.Equal(30f, targets[0].Z);
    }



    [Fact]
    public void Accepted_with_missing_item_resolves_objective_source_semantics()
    {
        var guide = new CompiledGuideBuilder()
            .AddCharacter("char:wolf", scene: "Forest", x: 40f, y: 50f, z: 60f)
            .AddItem("item:pelt")
            .AddItemSource("item:pelt", "char:wolf")
            .AddQuest("quest:a", dbName: "QUESTA", requiredItems: new[] { ("item:pelt", 1) })
            .Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(Array.Empty<string>(), new[] { "QUESTA" }, new Dictionary<string, int>(), Array.Empty<string>());
        var evaluator = new UnlockPredicateEvaluator(guide, tracker);
        var resolver = new SourceResolver(guide, tracker, evaluator, new StubLivePositionProvider());

        var targets = resolver.ResolveTargets(new FrontierEntry(0, QuestPhase.Accepted, -1), "Forest");

        guide.TryGetNodeId("char:wolf", out int wolfId);
        Assert.Single(targets);
        Assert.Equal(wolfId, targets[0].TargetNodeId);
        Assert.Equal(wolfId, targets[0].PositionNodeId);
        Assert.Equal(ResolvedTargetRole.Objective, targets[0].Role);
        Assert.Equal(QuestMarkerKind.Objective, targets[0].Semantic.PreferredMarkerKind);
        Assert.Equal(ResolvedActionKind.Kill, targets[0].Semantic.ActionKind);
        Assert.Equal(40f, targets[0].X);
        Assert.Equal(50f, targets[0].Y);
        Assert.Equal(60f, targets[0].Z);
    }


    [Fact]
    public void Accepted_with_hostile_drop_source_hides_friendly_drop_sources()
    {
        var guide = new CompiledGuideBuilder()
            .AddCharacter("char:wolf", scene: "Forest", x: 40f, y: 50f, z: 60f, isFriendly: false)
            .AddCharacter("char:ranger", scene: "Forest", x: 70f, y: 80f, z: 90f, isFriendly: true)
            .AddItem("item:pelt")
            .AddItemSource("item:pelt", "char:wolf", edgeType: 16)
            .AddItemSource("item:pelt", "char:ranger", edgeType: 16)
            .AddQuest("quest:a", dbName: "QUESTA", requiredItems: new[] { ("item:pelt", 1) })
            .Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(Array.Empty<string>(), new[] { "QUESTA" }, new Dictionary<string, int>(), Array.Empty<string>());
        var evaluator = new UnlockPredicateEvaluator(guide, tracker);
        var resolver = new SourceResolver(guide, tracker, evaluator, new StubLivePositionProvider());

        var targets = resolver.ResolveTargets(new FrontierEntry(0, QuestPhase.Accepted, -1), "Forest");

        Assert.Single(targets);
        guide.TryGetNodeId("char:wolf", out int wolfId);
        Assert.Equal(wolfId, targets[0].TargetNodeId);
    }
    [Fact]
    public void Accepted_with_satisfied_items_resolves_turnin_semantics()
    {
        var guide = new CompiledGuideBuilder()
            .AddItem("item:pelt")
            .AddCharacter("char:turnin", scene: "Forest", x: 70f, y: 80f, z: 90f)
            .AddQuest(
                "quest:a",
                dbName: "QUESTA",
                completers: new[] { "char:turnin" },
                requiredItems: new[] { ("item:pelt", 1) })
            .Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(Array.Empty<string>(), new[] { "QUESTA" }, new Dictionary<string, int> { ["item:pelt"] = 1 }, Array.Empty<string>());
        var evaluator = new UnlockPredicateEvaluator(guide, tracker);
        var resolver = new SourceResolver(guide, tracker, evaluator, new StubLivePositionProvider());

        var targets = resolver.ResolveTargets(new FrontierEntry(0, QuestPhase.Accepted, -1), "Forest");

        guide.TryGetNodeId("char:turnin", out int turnInId);
        Assert.Single(targets);
        Assert.Equal(turnInId, targets[0].TargetNodeId);
        Assert.Equal(ResolvedTargetRole.TurnIn, targets[0].Role);
        Assert.Equal(QuestMarkerKind.TurnInReady, targets[0].Semantic.PreferredMarkerKind);
        Assert.Equal(ResolvedActionKind.Give, targets[0].Semantic.ActionKind);
    }

    [Fact]
    public void Accepted_with_unindexed_required_item_does_not_emit_turnin()
    {
        // Quest requires "item:mystery" which exists as a graph node but is NOT
        // registered via AddItem, so FindItemIndex returns -1.
        var guide = new CompiledGuideBuilder()
            .AddCharacter("char:turnin", scene: "Forest", x: 70f, y: 80f, z: 90f)
            .AddQuest(
                "quest:a",
                dbName: "QUESTA",
                completers: new[] { "char:turnin" },
                requiredItems: new[] { ("item:mystery", 1) })
            .Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(Array.Empty<string>(), new[] { "QUESTA" }, new Dictionary<string, int>(), Array.Empty<string>());
        var evaluator = new UnlockPredicateEvaluator(guide, tracker);
        var resolver = new SourceResolver(guide, tracker, evaluator, new StubLivePositionProvider());

        var targets = resolver.ResolveTargets(new FrontierEntry(0, QuestPhase.Accepted, -1), "Forest");

        // The item is unindexed, so no objective sources can be resolved.
        // But it is still a requirement — turn-in must NOT be emitted.
        Assert.Empty(targets);
    }
}
