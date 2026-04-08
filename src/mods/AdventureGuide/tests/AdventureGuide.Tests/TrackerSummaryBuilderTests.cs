using AdventureGuide.Plan;
using AdventureGuide.Resolution;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class TrackerSummaryBuilderTests
{
    [Fact]
    public void Ready_to_accept_uses_giver_name()
    {
        var guide = new CompiledGuideBuilder()
            .AddCharacter("char:guard")
            .AddQuest("quest:a", dbName: "QUESTA", givers: new[] { "char:guard" })
            .Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(Array.Empty<string>(), Array.Empty<string>(), new Dictionary<string, int>(), Array.Empty<string>());

        var summary = TrackerSummaryBuilder.Build(guide, tracker, new FrontierEntry(0, QuestPhase.ReadyToAccept, -1));

        Assert.Contains("char:guard", summary.PrimaryText, System.StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public void Accepted_with_missing_items_shows_collect_progress()
    {
        var guide = new CompiledGuideBuilder()
            .AddItem("item:x")
            .AddQuest("quest:a", dbName: "QUESTA", requiredItems: new[] { ("item:x", 3) })
            .Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(Array.Empty<string>(), new[] { "QUESTA" }, new Dictionary<string, int>(), Array.Empty<string>());

        var summary = TrackerSummaryBuilder.Build(guide, tracker, new FrontierEntry(0, QuestPhase.Accepted, -1));

        Assert.Contains("Collect", summary.PrimaryText, System.StringComparison.OrdinalIgnoreCase);
        Assert.Contains("0/3", summary.PrimaryText, System.StringComparison.OrdinalIgnoreCase);
    }
}
