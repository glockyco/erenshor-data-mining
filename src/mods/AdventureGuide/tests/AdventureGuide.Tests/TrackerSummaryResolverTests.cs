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
        var resolver = new TrackerSummaryResolver(
            guide,
            phases,
            frontier);

        var summary = resolver.Resolve("quest:a", "QUESTA");

        var resolved = Assert.IsType<TrackerSummary>(summary);
        Assert.Equal("Talk to char:giver", resolved.PrimaryText);
        Assert.Null(resolved.SecondaryText);
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
        var resolver = new TrackerSummaryResolver(
            guide,
            phases,
            frontier);

        var summary = resolver.Resolve("quest:missing", "MISSING");

        Assert.Null(summary);
    }

}
