using AdventureGuide.Plan;
using AdventureGuide.Resolution;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class UnlockPredicateEvaluatorTests
{
    [Fact]
    public void Missing_predicate_is_unlocked()
    {
        var guide = new CompiledGuideBuilder().AddQuest("quest:a", dbName: "QUESTA").Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(Array.Empty<string>(), Array.Empty<string>(), new Dictionary<string, int>(), Array.Empty<string>());
        var evaluator = new UnlockPredicateEvaluator(guide, tracker);

        guide.TryGetNodeId("quest:a", out int nodeId);
        Assert.Equal(UnlockResult.Unlocked, evaluator.Evaluate(nodeId));
    }

    [Fact]
    public void Quest_completed_unlocks_target()
    {
        var guide = new CompiledGuideBuilder()
            .AddQuest("quest:unlock", dbName: "UNLOCK")
            .AddCharacter("char:vendor")
            .AddUnlockPredicate("char:vendor", "quest:unlock")
            .Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(new[] { "UNLOCK" }, Array.Empty<string>(), new Dictionary<string, int>(), Array.Empty<string>());
        var evaluator = new UnlockPredicateEvaluator(guide, tracker);

        guide.TryGetNodeId("char:vendor", out int nodeId);
        Assert.Equal(UnlockResult.Unlocked, evaluator.Evaluate(nodeId));
    }

    [Fact]
    public void Missing_completion_blocks_target()
    {
        var guide = new CompiledGuideBuilder()
            .AddQuest("quest:unlock", dbName: "UNLOCK")
            .AddCharacter("char:vendor")
            .AddUnlockPredicate("char:vendor", "quest:unlock")
            .Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(Array.Empty<string>(), Array.Empty<string>(), new Dictionary<string, int>(), Array.Empty<string>());
        var evaluator = new UnlockPredicateEvaluator(guide, tracker);

        guide.TryGetNodeId("char:vendor", out int nodeId);
        Assert.Equal(UnlockResult.Blocked, evaluator.Evaluate(nodeId));
    }
}
