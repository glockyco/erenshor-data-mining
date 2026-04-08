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
    public void Ready_to_accept_resolves_giver_position()
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

        Assert.Single(targets);
        Assert.Equal(10f, targets[0].X);
        Assert.Equal(20f, targets[0].Y);
        Assert.Equal(30f, targets[0].Z);
    }

    [Fact]
    public void Accepted_with_missing_item_resolves_item_source_position()
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

        Assert.Single(targets);
        Assert.Equal(40f, targets[0].X);
        Assert.Equal(50f, targets[0].Y);
        Assert.Equal(60f, targets[0].Z);
    }
}
