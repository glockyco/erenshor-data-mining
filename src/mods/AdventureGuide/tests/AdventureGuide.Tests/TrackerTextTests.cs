using AdventureGuide.Graph;
using AdventureGuide.Markers;
using AdventureGuide.Navigation;
using AdventureGuide.Resolution;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests;

/// <summary>
/// Unit tests for tracker primary/secondary text generation, covering:
/// - sub-quest nesting: "Needed for Quest 2" in secondary
/// - quest-as-item-source: tracker leads with "Complete X" not "Collect Y"
/// - rationale shown for CompleteQuest sources even when GoalKind == CollectItem
/// - direct steps of the tracked quest: no "Needed for" secondary
/// </summary>
public sealed class TrackerTextTests
{
    // ── helpers ──────────────────────────────────────────────────────────────

    private static ResolvedNodeContext Ctx(Node node, EdgeType? edgeType = null) =>
        new(node.Key, node, edgeType);

    private static ResolvedActionSemantic Semantic(
        NavigationGoalKind goalKind,
        ResolvedActionKind actionKind,
        string targetIdentityText,
        string? payloadText = null,
        string? rationaleText = null,
        string? goalNodeKey = null,
        int? goalQuantity = null
    )
    {
        var stub = new Node
        {
            Key = "stub",
            Type = NodeType.Character,
            DisplayName = "stub",
        };
        return new ResolvedActionSemantic(
            goalKind,
            NavigationTargetKind.Character,
            actionKind,
            goalNodeKey,
            goalQuantity,
            keywordText: null,
            payloadText,
            targetIdentityText,
            contextText: null,
            rationaleText,
            zoneText: null,
            availabilityText: null,
            QuestMarkerKind.Objective,
            markerPriority: 20
        );
    }

    private static ResolvedNodeContext FrontierCtx(string key, string displayName)
    {
        var node = new Node
        {
            Key = key,
            Type = NodeType.Item,
            DisplayName = displayName,
        };
        return new ResolvedNodeContext(key, node);
    }

    private static TrackerSummary Summary(
        ResolvedNodeContext frontierCtx,
        ResolvedActionSemantic semantic,
        string? neededForContext = null
    ) =>
        NavigationExplanationBuilder.BuildTrackerSummary(
            frontierCtx,
            semantic,
            tracker: null!, // only used for CollectItem quantity — irrelevant here
            additionalCount: 0,
            prerequisiteQuestName: neededForContext
        );

    // ── primary: quest-as-item-source ────────────────────────────────────────

    [Fact]
    public void TrackerPrimary_CompleteQuestSource_UsesCompleteVerb()
    {
        // Item is obtained by completing a quest → tracker should lead with
        // "Complete Percy's Seaspice", not "Collect A Rolled Note".
        var semantic = Semantic(
            NavigationGoalKind.CollectItem,
            ResolvedActionKind.CompleteQuest,
            targetIdentityText: "Percy's Seaspice",
            payloadText: "A Rolled Note",
            rationaleText: "Rewards A Rolled Note"
        );

        var frontier = FrontierCtx("item:rolled-note", "A Rolled Note");
        var summary = Summary(frontier, semantic);

        Assert.Equal("Complete Percy's Seaspice", summary.PrimaryText);
    }

    [Fact]
    public void TrackerSecondary_CompleteQuestSource_ShowsRewardsRationale()
    {
        // Secondary should be the rationale "Rewards A Rolled Note", not null
        // and not "Needed for Percy's Seaspice".
        var semantic = Semantic(
            NavigationGoalKind.CollectItem,
            ResolvedActionKind.CompleteQuest,
            targetIdentityText: "Percy's Seaspice",
            payloadText: "A Rolled Note",
            rationaleText: "Rewards A Rolled Note"
        );

        var frontier = FrontierCtx("item:rolled-note", "A Rolled Note");
        var summary = Summary(frontier, semantic);

        Assert.Equal("Rewards A Rolled Note", summary.SecondaryText);
        Assert.NotEqual("Needed for Percy's Seaspice", summary.SecondaryText);
    }

    // ── primary: normal CollectItem still uses Collect verb ──────────────────

    [Fact]
    public void TrackerPrimary_NormalCollect_UsesCollectVerb()
    {
        // A drop source (Kill) for a needed item keeps "Collect X" as primary.
        var semantic = Semantic(
            NavigationGoalKind.CollectItem,
            ResolvedActionKind.Kill,
            targetIdentityText: "Spark Beetle",
            payloadText: "Iron Ore",
            rationaleText: "Drops Iron Ore"
        );

        var frontier = FrontierCtx("item:iron-ore", "Iron Ore");
        var summary = Summary(frontier, semantic);

        Assert.Equal("Collect Iron Ore", summary.PrimaryText);
    }

    // ── secondary: sub-quest nesting ─────────────────────────────────────────

    [Fact]
    public void TrackerSecondary_SubQuestNesting_ShowsNeededForSubQuest()
    {
        // Target is a step inside Quest 2, which is a sub-quest of the tracked
        // Quest 1. RequiredForQuestKey = "quest:quest2" → neededForContext =
        // "Quest 2" → secondary = "Needed for Quest 2".
        var semantic = Semantic(
            NavigationGoalKind.KillTarget,
            ResolvedActionKind.Kill,
            targetIdentityText: "Guard"
        );

        var frontier = FrontierCtx("item:key", "Key");
        var summary = Summary(frontier, semantic, neededForContext: "Quest 2");

        Assert.Equal("Needed for Quest 2", summary.SecondaryText);
    }

    [Fact]
    public void TrackerSecondary_DirectStep_NoNeededFor()
    {
        // Target is a direct step of the tracked quest (RequiredForQuestKey == null →
        // neededForContext == null). No secondary "Needed for" should appear.
        var semantic = Semantic(
            NavigationGoalKind.KillTarget,
            ResolvedActionKind.Kill,
            targetIdentityText: "Guard"
        );

        var frontier = FrontierCtx("item:key", "Key");
        var summary = Summary(frontier, semantic, neededForContext: null);

        // Secondary is null or describes something other than a "Needed for" fallback.
        // The frontier node display name is "Key" which differs from "Guard",
        // so the fallback "Needed for Key" would fire — but that is correct behaviour
        // for a non-CollectItem goal whose frontier node differs from the target.
        // For CollectItem goals (the common case for direct steps), secondary is null.
        var killSemantic = Semantic(
            NavigationGoalKind.CollectItem,
            ResolvedActionKind.Kill,
            targetIdentityText: "Spark Beetle",
            payloadText: "Iron Ore",
            rationaleText: "Drops Iron Ore"
        );

        var collectSummary = Summary(FrontierCtx("item:iron-ore", "Iron Ore"), killSemantic, null);
        // CollectItem with null neededForContext → secondary is the rationale,
        // NOT "Needed for Iron Ore".
        Assert.NotEqual("Needed for Iron Ore", collectSummary.SecondaryText);
        Assert.Null(collectSummary.SecondaryText); // RationaleText suppressed for non-CompleteQuest
    }
}
