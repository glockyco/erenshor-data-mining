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
        tracker.Initialize(
            Array.Empty<string>(),
            Array.Empty<string>(),
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );

        var summary = TrackerSummaryBuilder.Build(
            guide,
            tracker,
            new FrontierEntry(0, QuestPhase.ReadyToAccept, -1)
        );

        Assert.Contains(
            "char:guard",
            summary.PrimaryText,
            System.StringComparison.OrdinalIgnoreCase
        );
    }

    [Fact]
    public void Accepted_with_missing_items_shows_collect_progress()
    {
        var guide = new CompiledGuideBuilder()
            .AddItem("item:x")
            .AddQuest("quest:a", dbName: "QUESTA", requiredItems: new[] { ("item:x", 3) })
            .Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(
            Array.Empty<string>(),
            new[] { "QUESTA" },
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );

        var summary = TrackerSummaryBuilder.Build(
            guide,
            tracker,
            new FrontierEntry(0, QuestPhase.Accepted, -1)
        );

        Assert.Contains("Collect", summary.PrimaryText, System.StringComparison.OrdinalIgnoreCase);
        Assert.Contains("0/3", summary.PrimaryText, System.StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public void Prerequisite_entry_shows_required_for_context()
    {
        var guide = new CompiledGuideBuilder()
            .AddQuest("quest:b", dbName: "QUESTB")
            .AddQuest(
                "quest:a",
                dbName: "QUESTA",
                prereqs: new[] { "quest:b" },
                givers: new[] { "char:guard" }
            )
            .AddCharacter("char:guard")
            .Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(
            Array.Empty<string>(),
            Array.Empty<string>(),
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );

        // quest:b is index 0, quest:a is index 1.
        // Frontier entry for quest:b that is needed for quest:a.
        int questBIndex = 0;
        int questAIndex = 1;
        string parentName = guide.GetDisplayName(guide.QuestNodeId(questAIndex));

        var entry = new FrontierEntry(
            questBIndex,
            QuestPhase.ReadyToAccept,
            requiredForQuestIndex: questAIndex
        );
        var summary = TrackerSummaryBuilder.Build(guide, tracker, entry);

        Assert.NotNull(summary.RequiredForContext);
        Assert.Contains("Needed for:", summary.RequiredForContext);
        Assert.Contains(parentName, summary.RequiredForContext, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public void Non_prerequisite_entry_has_no_required_for_context()
    {
        var guide = new CompiledGuideBuilder()
            .AddCharacter("char:guard")
            .AddQuest("quest:a", dbName: "QUESTA", givers: new[] { "char:guard" })
            .Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(
            Array.Empty<string>(),
            Array.Empty<string>(),
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );

        var entry = new FrontierEntry(0, QuestPhase.ReadyToAccept, requiredForQuestIndex: -1);
        var summary = TrackerSummaryBuilder.Build(guide, tracker, entry);

        Assert.Null(summary.RequiredForContext);
    }

    [Fact]
    public void Accepted_travel_step_shows_travel_to_prefix()
    {
        var guide = new CompiledGuideBuilder()
            .AddCharacter("char:zone")
            .AddQuest("quest:a", dbName: "QUESTA")
            .AddStep("quest:a", stepType: 4, targetKey: "char:zone") // 4 = Travel
            .Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(
            Array.Empty<string>(),
            new[] { "QUESTA" },
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );

        var summary = TrackerSummaryBuilder.Build(
            guide,
            tracker,
            new FrontierEntry(0, QuestPhase.Accepted, -1)
        );

        Assert.StartsWith("Travel to ", summary.PrimaryText);
    }

    [Fact]
    public void Accepted_kill_step_shows_kill_prefix()
    {
        var guide = new CompiledGuideBuilder()
            .AddCharacter("char:wolf")
            .AddQuest("quest:a", dbName: "QUESTA")
            .AddStep("quest:a", stepType: 3, targetKey: "char:wolf") // 3 = Kill
            .Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(
            Array.Empty<string>(),
            new[] { "QUESTA" },
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );

        var summary = TrackerSummaryBuilder.Build(
            guide,
            tracker,
            new FrontierEntry(0, QuestPhase.Accepted, -1)
        );

        Assert.StartsWith("Kill ", summary.PrimaryText);
    }

    [Fact]
    public void Accepted_talk_step_shows_talk_to_prefix()
    {
        var guide = new CompiledGuideBuilder()
            .AddCharacter("char:npc")
            .AddQuest("quest:a", dbName: "QUESTA")
            .AddStep("quest:a", stepType: 2, targetKey: "char:npc") // 2 = Talk
            .Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(
            Array.Empty<string>(),
            new[] { "QUESTA" },
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );

        var summary = TrackerSummaryBuilder.Build(
            guide,
            tracker,
            new FrontierEntry(0, QuestPhase.Accepted, -1)
        );

        Assert.StartsWith("Talk to", summary.PrimaryText);
    }
}
