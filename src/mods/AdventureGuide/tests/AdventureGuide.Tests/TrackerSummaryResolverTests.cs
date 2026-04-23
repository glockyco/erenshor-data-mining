using AdventureGuide.Diagnostics;
using AdventureGuide.Graph;
using AdventureGuide.Frontier;
using AdventureGuide.Resolution;
using AdventureGuide.State;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class TrackerSummaryResolverTests
{
    [Fact]
    public void WarmBatch_MemoisesSubsequentResolves()
    {
        var (service, harness) = ResolutionTestFactory.BuildInvalidationHarness();
        var resolver = new TrackerSummaryResolver(harness.Guide, harness.Phases, service);
        var keys = new[] { "quest:fetch-water", "quest:slay-wolves" };

        // WarmBatch pre-populates the engine's resolution cache; subsequent Resolve
        // calls hit memoised entries. The incremental engine verifies memoisation in
        // QuestResolutionQueryTests; here we just verify WarmBatch + Resolve return
        // consistent results without throwing.
        resolver.WarmBatch(keys, harness.Scene);
        var first = resolver.Resolve("quest:fetch-water", "FETCHWATER", harness.Scene);
        var second = resolver.Resolve("quest:fetch-water", "FETCHWATER", harness.Scene);
        Assert.Equal(first?.PrimaryText, second?.PrimaryText);
    }

    [Fact]
    public void Resolve_UsesCompiledFrontierSummaryWhenQuestIsPresent()
    {
        var guide = new CompiledGuideBuilder()
            .AddCharacter("char:giver", scene: "Forest", x: 10f, y: 20f, z: 30f)
            .AddQuest("quest:a", dbName: "QUESTA", givers: new[] { "char:giver" })
            .Build();
        var phases = new QuestPhaseTracker(guide);
        phases.Initialize(
            Array.Empty<string>(),
            Array.Empty<string>(),
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        var frontier = new EffectiveFrontier(guide, phases);
        var sourceResolver = new SourceResolver(
            guide,
            phases,
            new UnlockPredicateEvaluator(guide, phases),
            new StubLivePositionProvider(),
            TestPositionResolvers.Create(guide)
        );
        var resolver = new TrackerSummaryResolver(guide, phases, ResolutionTestFactory.BuildService(guide, frontier, sourceResolver, zoneRouter: null));

        var summary = resolver.Resolve("quest:a", "QUESTA", "Forest");

        var resolved = Assert.IsType<TrackerSummary>(summary);
        Assert.Equal("Talk to char:giver", resolved.PrimaryText);
        Assert.Null(resolved.SecondaryText);
    }

    [Fact]
    public void Resolve_ReadyToAcceptItemGiverWithoutItem_UsesAcquisitionSummary()
    {
        var guide = new CompiledGuideBuilder()
            .AddItem("item:note")
            .AddCharacter("char:ghost", scene: "Tutorial", x: 10f, y: 20f, z: 30f)
            .AddItemSource("item:note", "char:ghost")
            .AddQuest("quest:a", dbName: "QUESTA", givers: new[] { "item:note" })
            .Build();
        var phases = new QuestPhaseTracker(guide);
        phases.Initialize(
            Array.Empty<string>(),
            Array.Empty<string>(),
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        var frontier = new EffectiveFrontier(guide, phases);
        var sourceResolver = new SourceResolver(
            guide,
            phases,
            new UnlockPredicateEvaluator(guide, phases),
            new StubLivePositionProvider(),
            TestPositionResolvers.Create(guide)
        );
        var resolver = new TrackerSummaryResolver(guide, phases, ResolutionTestFactory.BuildService(guide, frontier, sourceResolver, zoneRouter: null));

        var summary = resolver.Resolve("quest:a", "QUESTA", "Tutorial");

        var resolved = Assert.IsType<TrackerSummary>(summary);
        Assert.Equal("Kill char:ghost", resolved.PrimaryText);
        Assert.Equal("Drops item:note", resolved.SecondaryText);
    }

    [Fact]
    public void Resolve_AcceptedUnreadStepItem_UsesAcquisitionSummary()
    {
        var guide = new CompiledGuideBuilder()
            .AddItem("item:note")
            .AddCharacter("char:ghost", scene: "Forest", x: 40f, y: 50f, z: 60f)
            .AddItemSource("item:note", "char:ghost")
            .AddQuest("quest:a", dbName: "QUESTA")
            .AddStep("quest:a", StepLabels.Read, "item:note")
            .Build();
        var phases = new QuestPhaseTracker(guide);
        phases.Initialize(
            Array.Empty<string>(),
            new[] { "QUESTA" },
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        var frontier = new EffectiveFrontier(guide, phases);
        var sourceResolver = new SourceResolver(
            guide,
            phases,
            new UnlockPredicateEvaluator(guide, phases),
            new StubLivePositionProvider(),
            TestPositionResolvers.Create(guide)
        );
        var resolver = new TrackerSummaryResolver(guide, phases, ResolutionTestFactory.BuildService(guide, frontier, sourceResolver, zoneRouter: null));

        var summary = resolver.Resolve("quest:a", "QUESTA", "Forest");

        var resolved = Assert.IsType<TrackerSummary>(summary);
        Assert.Equal("Kill char:ghost", resolved.PrimaryText);
        Assert.Equal("Drops item:note", resolved.SecondaryText);
    }

    [Fact]
    public void Resolve_MixedDirectAndBlockedSources_UsesDirectSummaryWithoutPreferredTarget()
    {
        var guide = new CompiledGuideBuilder()
            .AddItem("item:spice")
            .AddCharacter("char:elder", scene: "Forest", x: 5f, y: 6f, z: 7f)
            .AddQuest("quest:key", dbName: "KEY", givers: new[] { "char:elder" })
            .AddCharacter("char:crypt", scene: "Vault", x: 10f, y: 20f, z: 30f)
            .AddItemSource("item:spice", "char:crypt")
            .AddUnlockPredicate("char:crypt", "quest:key")
            .AddCharacter("char:plax", scene: "Forest", x: 40f, y: 50f, z: 60f)
            .AddItemSource("item:spice", "char:plax")
            .AddQuest("quest:root", dbName: "ROOT", requiredItems: new[] { ("item:spice", 1) })
            .Build();
        var phases = new QuestPhaseTracker(guide);
        phases.Initialize(
            Array.Empty<string>(),
            new[] { "ROOT" },
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        var frontier = new EffectiveFrontier(guide, phases);
        var sourceResolver = new SourceResolver(
            guide,
            phases,
            new UnlockPredicateEvaluator(guide, phases),
            new StubLivePositionProvider(),
            TestPositionResolvers.Create(guide)
        );
        var resolver = new TrackerSummaryResolver(guide, phases, ResolutionTestFactory.BuildService(guide, frontier, sourceResolver, zoneRouter: null));

        var summary = resolver.Resolve("quest:root", "ROOT", "Forest");
        var resolved = Assert.IsType<TrackerSummary>(summary);

        Assert.Equal("Kill char:plax", resolved.PrimaryText);
        Assert.Null(resolved.RequiredForContext);
    }

    [Fact]
    public void Resolve_Quest_with_quest_giver_uses_nested_quest_frontier_summary()
    {
        var guide = new CompiledGuideBuilder()
            .AddCharacter("char:percy")
            .AddQuest("quest:percy", dbName: "PERCY", givers: new[] { "char:percy" })
            .AddQuest("quest:root", dbName: "ROOT", givers: new[] { "quest:percy" })
            .Build();
        var phases = new QuestPhaseTracker(guide);
        phases.Initialize(
            Array.Empty<string>(),
            Array.Empty<string>(),
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        var frontier = new EffectiveFrontier(guide, phases);
        var sourceResolver = new SourceResolver(
            guide,
            phases,
            new UnlockPredicateEvaluator(guide, phases),
            new StubLivePositionProvider(),
            TestPositionResolvers.Create(guide)
        );
        var resolver = new TrackerSummaryResolver(guide, phases, ResolutionTestFactory.BuildService(guide, frontier, sourceResolver, zoneRouter: null));

        var summary = resolver.Resolve("quest:root", "ROOT", "");

        var resolved = Assert.IsType<TrackerSummary>(summary);
        Assert.Equal("Talk to char:percy", resolved.PrimaryText);
    }

    [Fact]
    public void Resolve_Blocked_item_source_uses_unlock_quest_summary()
    {
        var guide = new CompiledGuideBuilder()
            .AddItem("item:crystal")
            .AddCharacter("char:keeper", scene: "Vault", x: 40f, y: 50f, z: 60f)
            .AddItemSource("item:crystal", "char:keeper")
            .AddCharacter("char:elder", scene: "Town", x: 5f, y: 6f, z: 7f)
            .AddQuest("quest:gate", dbName: "GATE", givers: new[] { "char:elder" })
            .AddUnlockPredicate("char:keeper", "quest:gate")
            .AddQuest("quest:root", dbName: "ROOT", requiredItems: new[] { ("item:crystal", 1) })
            .Build();
        var phases = new QuestPhaseTracker(guide);
        phases.Initialize(
            Array.Empty<string>(),
            new[] { "ROOT" },
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        var frontier = new EffectiveFrontier(guide, phases);
        var sourceResolver = new SourceResolver(
            guide,
            phases,
            new UnlockPredicateEvaluator(guide, phases),
            new StubLivePositionProvider(),
            TestPositionResolvers.Create(guide)
        );
        var resolver = new TrackerSummaryResolver(guide, phases, ResolutionTestFactory.BuildService(guide, frontier, sourceResolver, zoneRouter: null));

        var summary = resolver.Resolve("quest:root", "ROOT", "Town");

        var resolved = Assert.IsType<TrackerSummary>(summary);
        Assert.Equal("Talk to char:elder", resolved.PrimaryText);
    }

    [Fact]
    public void Resolve_IgnoresStalePreferredTarget_WhenCurrentResolutionHasMovedPastPrerequisiteItem()
    {
        var guide = new CompiledGuideBuilder()
            .AddItem("item:ore")
            .AddItem("item:note")
            .AddCharacter("char:miner", scene: "Stowaway", x: 10f, y: 20f, z: 30f)
            .AddItemSource("item:ore", "char:miner")
            .AddCharacter("char:scribe", scene: "Stowaway", x: 40f, y: 50f, z: 60f)
            .AddQuest("quest:prereq", dbName: "PREREQ", requiredItems: new[] { ("item:ore", 1) }, completers: new[] { "char:scribe" })
            .AddEdge("quest:prereq", "item:note", EdgeType.RewardsItem)
            .AddQuest("quest:root", dbName: "ROOT", requiredItems: new[] { ("item:note", 1) })
            .Build();
        var state = new QuestStateTracker(guide);
        state.LoadState(
            currentZone: "Stowaway",
            activeQuests: new[] { "PREREQ", "ROOT" },
            completedQuests: Array.Empty<string>(),
            inventoryCounts: new Dictionary<string, int> { ["item:ore"] = 1 },
            keyringItemKeys: Array.Empty<string>()
        );
        var phases = new QuestPhaseTracker(guide, state);
        var frontier = new EffectiveFrontier(guide, phases);
        var sourceResolver = new SourceResolver(
            guide,
            phases,
            new UnlockPredicateEvaluator(guide, phases),
            new StubLivePositionProvider(),
            TestPositionResolvers.Create(guide)
        );
        var reader = ResolutionTestFactory.BuildService(
            guide,
            frontier,
            sourceResolver,
            zoneRouter: null,
            questTracker: state);
        var resolver = new TrackerSummaryResolver(guide, phases, reader);
        var current = Assert.IsType<TrackerSummary>(resolver.Resolve("quest:root", "ROOT", "Stowaway"));
        var stalePreferredTarget = BuildPreferredTarget(
            goalNodeKey: "item:ore",
            goalDisplayName: "Iron Ore",
            targetNodeKey: "char:miner",
            targetDisplayName: "Ore Vein",
            actionKind: ResolvedActionKind.Mine,
            targetIdentityText: "Ore Vein",
            payloadText: "Iron Ore");

        var summary = Assert.IsType<TrackerSummary>(
            resolver.Resolve("quest:root", "ROOT", "Stowaway", stalePreferredTarget, state));

        Assert.Equal(current.PrimaryText, summary.PrimaryText);
        Assert.Equal(current.SecondaryText, summary.SecondaryText);
        Assert.Equal(current.RequiredForContext, summary.RequiredForContext);
        Assert.NotEqual("Collect Iron Ore", summary.PrimaryText);
    }

    [Fact]
    public void Resolve_WithPreferredZoneReentryTarget_ShowsReenterZoneGuidance()
    {
        var guide = new CompiledGuideBuilder()
            .AddItem("item:note")
            .AddQuest("quest:root", dbName: "ROOT", requiredItems: new[] { ("item:note", 1) })
            .Build();
        var phases = new QuestPhaseTracker(guide);
        phases.Initialize(
            Array.Empty<string>(),
            new[] { "ROOT" },
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        var frontier = new EffectiveFrontier(guide, phases);
        var sourceResolver = new SourceResolver(
            guide,
            phases,
            new UnlockPredicateEvaluator(guide, phases),
            new StubLivePositionProvider(),
            TestPositionResolvers.Create(guide)
        );
        var resolver = new TrackerSummaryResolver(guide, phases, ResolutionTestFactory.BuildService(guide, frontier, sourceResolver, zoneRouter: null));
        var tracker = new QuestStateTracker(guide);
        tracker.LoadState(
            "Forest",
            new[] { "ROOT" },
            Array.Empty<string>(),
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        var preferredTarget = BuildPreferredTarget(
            goalNodeKey: "item:note",
            goalDisplayName: "Note",
            targetNodeKey: "char:ghost",
            targetDisplayName: "Ghost",
            actionKind: ResolvedActionKind.Kill,
            targetIdentityText: "Ghost",
            payloadText: "Note",
            explanationPrimaryText: "Re-enter zone",
            explanationSecondaryText: "Ghost");

        var summary = resolver.Resolve("quest:root", "ROOT", "Forest", preferredTarget, tracker);

        var resolved = Assert.IsType<TrackerSummary>(summary);
        Assert.Equal("Re-enter zone", resolved.PrimaryText);
        Assert.Equal("Ghost", resolved.SecondaryText);
    }

    [Fact]
    public void Resolve_WithPreferredZoneReentryTargetMatchingCurrentRecord_KeepsReenterZoneGuidance()
    {
        var guide = new CompiledGuideBuilder()
            .AddItem("item:note")
            .AddCharacter("char:ghost", scene: "Forest", x: 1f, y: 2f, z: 3f)
            .AddSpawnPoint("spawn:ghost", scene: "Forest", x: 1f, y: 2f, z: 3f)
            .AddItemSource("item:note", "char:ghost", positionKeys: new[] { "spawn:ghost" })
            .AddQuest("quest:root", dbName: "ROOT", requiredItems: new[] { ("item:note", 1) })
            .Build();
        var phases = new QuestPhaseTracker(guide);
        phases.Initialize(
            Array.Empty<string>(),
            new[] { "ROOT" },
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        var frontier = new EffectiveFrontier(guide, phases);
        var sourceResolver = new SourceResolver(
            guide,
            phases,
            new UnlockPredicateEvaluator(guide, phases),
            new StubLivePositionProvider(),
            TestPositionResolvers.Create(guide)
        );
        var resolver = new TrackerSummaryResolver(guide, phases, ResolutionTestFactory.BuildService(guide, frontier, sourceResolver, zoneRouter: null));
        var tracker = new QuestStateTracker(guide);
        tracker.LoadState(
            "Forest",
            new[] { "ROOT" },
            Array.Empty<string>(),
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        var preferredTarget = BuildPreferredTarget(
            goalNodeKey: "item:note",
            goalDisplayName: "Note",
            targetNodeKey: "char:ghost",
            targetDisplayName: "Ghost",
            actionKind: ResolvedActionKind.Kill,
            targetIdentityText: "Ghost",
            payloadText: "Note",
            explanationPrimaryText: "Re-enter zone",
            explanationSecondaryText: "Ghost",
            sourceKey: "spawn:ghost");

        var summary = resolver.Resolve("quest:root", "ROOT", "Forest", preferredTarget, tracker);

        var resolved = Assert.IsType<TrackerSummary>(summary);
        Assert.Equal("Re-enter zone", resolved.PrimaryText);
        Assert.Equal("Ghost", resolved.SecondaryText);
    }

    [Fact]
    public void Resolve_WithPreferredSelectedTarget_UsesSelectedTargetSummary()
    {
        var guide = new CompiledGuideBuilder()
            .AddItem("item:ore")
            .AddQuest("quest:root", dbName: "ROOT", requiredItems: new[] { ("item:ore", 1) })
            .Build();
        var phases = new QuestPhaseTracker(guide);
        phases.Initialize(
            Array.Empty<string>(),
            new[] { "ROOT" },
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        var frontier = new EffectiveFrontier(guide, phases);
        var sourceResolver = new SourceResolver(
            guide,
            phases,
            new UnlockPredicateEvaluator(guide, phases),
            new StubLivePositionProvider(),
            TestPositionResolvers.Create(guide)
        );
        var resolver = new TrackerSummaryResolver(guide, phases, ResolutionTestFactory.BuildService(guide, frontier, sourceResolver, zoneRouter: null));
        var tracker = new QuestStateTracker(guide);
        tracker.LoadState(
            "Forest",
            new[] { "ROOT" },
            Array.Empty<string>(),
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        var preferredTarget = BuildPreferredTarget(
            goalNodeKey: "item:ore",
            goalDisplayName: "Iron Ore",
            targetNodeKey: "mine:ore",
            targetDisplayName: "Mineral Deposit",
            actionKind: ResolvedActionKind.Mine,
            targetIdentityText: "Mineral Deposit",
            payloadText: "Iron Ore");

        var summary = resolver.Resolve("quest:root", "ROOT", "Forest", preferredTarget, tracker);

        var resolved = Assert.IsType<TrackerSummary>(summary);
        Assert.Equal("Collect Iron Ore", resolved.PrimaryText);
        Assert.NotEqual("Mine Mineral Deposit", resolved.PrimaryText);
    }

    [Fact]
    public void Resolve_ReturnsNullWhenCompiledQuestIsMissing()
    {
        var guide = new CompiledGuideBuilder().AddQuest("quest:other", dbName: "OTHER").Build();
        var phases = new QuestPhaseTracker(guide);
        phases.Initialize(
            Array.Empty<string>(),
            Array.Empty<string>(),
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        var frontier = new EffectiveFrontier(guide, phases);
        var sourceResolver = new SourceResolver(
            guide,
            phases,
            new UnlockPredicateEvaluator(guide, phases),
            new StubLivePositionProvider(),
            TestPositionResolvers.Create(guide)
        );
        var resolver = new TrackerSummaryResolver(guide, phases, ResolutionTestFactory.BuildService(guide, frontier, sourceResolver, zoneRouter: null));

        var summary = resolver.Resolve("quest:missing", "MISSING", "");

        Assert.Null(summary);
    }

    private static ResolvedQuestTarget BuildPreferredTarget(
        string goalNodeKey,
        string goalDisplayName,
        string targetNodeKey,
        string targetDisplayName,
        ResolvedActionKind actionKind,
        string targetIdentityText,
        string? payloadText,
        string? explanationPrimaryText = null,
        string? explanationSecondaryText = null,
        string? sourceKey = null)
    {
        var goalNode = new ResolvedNodeContext(
            goalNodeKey,
            new Node
            {
                Key = goalNodeKey,
                Type = NodeType.Item,
                DisplayName = goalDisplayName,
            }
        );
        var targetNode = new ResolvedNodeContext(
            targetNodeKey,
            new Node
            {
                Key = targetNodeKey,
                Type = actionKind == ResolvedActionKind.Mine ? NodeType.MiningNode : NodeType.Character,
                DisplayName = targetDisplayName,
            }
        );
        var semantic = new ResolvedActionSemantic(
            NavigationGoalKind.CollectItem,
            NavigationTargetKind.Object,
            actionKind,
            goalNodeKey: goalNodeKey,
            goalQuantity: 1,
            keywordText: null,
            payloadText: payloadText,
            targetIdentityText: targetIdentityText,
            contextText: null,
            rationaleText: null,
            zoneText: null,
            availabilityText: null,
            preferredMarkerKind: QuestMarkerKind.Objective,
            markerPriority: 10
        );
        return new ResolvedQuestTarget(
            targetNodeKey,
            scene: "Forest",
            sourceKey: sourceKey ?? targetNodeKey,
            goalNode,
            targetNode,
            semantic,
            explanationPrimaryText == null && explanationSecondaryText == null
                ? NavigationExplanationBuilder.Build(semantic, goalNode, targetNode)
                : new NavigationExplanation(
                    semantic.GoalKind,
                    semantic.TargetKind,
                    goalNode,
                    targetNode,
                    explanationPrimaryText ?? semantic.TargetIdentityText,
                    semantic.TargetIdentityText,
                    semantic.ZoneText,
                    explanationSecondaryText,
                    tertiaryText: null),
            x: 1f,
            y: 2f,
            z: 3f,
            isActionable: true
        );
    }
}
