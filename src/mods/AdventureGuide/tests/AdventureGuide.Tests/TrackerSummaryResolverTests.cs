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
            frontier,
            _ => null);

        var summary = resolver.Resolve("quest:a", "QUESTA");

        var resolved = Assert.IsType<TrackerSummary>(summary);
        Assert.Equal("Talk to char:giver", resolved.PrimaryText);
        Assert.Null(resolved.SecondaryText);
    }

    [Fact]
    public void Resolve_FallsBackToLegacySummaryWhenCompiledQuestIsMissing()
    {
        var resolver = new TrackerSummaryResolver(
            guide: null,
            phases: null,
            frontier: null,
            legacyResolver: key => key == "quest:legacy"
                ? new TrackerSummary("Legacy summary", "Legacy detail")
                : null);

        var summary = resolver.Resolve("quest:legacy", "LEGACY");

        var resolved = Assert.IsType<TrackerSummary>(summary);
        Assert.Equal("Legacy summary", resolved.PrimaryText);
        Assert.Equal("Legacy detail", resolved.SecondaryText);
    }
}
