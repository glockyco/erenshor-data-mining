using AdventureGuide.Frontier;
using AdventureGuide.Graph;
using AdventureGuide.Plan;
using AdventureGuide.Resolution;
using AdventureGuide.State;
using AdventureGuide.Tests.Helpers;
using AdventureGuide.UI;
using AdventureGuide.UI.Tree;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class ViewRendererTextTests
{
    [Fact]
    public void GetCompletionFallbackNotice_NoCompletionEdges_ReturnsScriptedNotice()
    {
        var guide = new CompiledGuideBuilder().AddQuest("quest:root", dbName: "RootQuest").Build();
        var quest = guide.GetNode("quest:root")!;

        string? notice = ViewRenderer.GetCompletionFallbackNotice(guide, quest);

        Assert.Equal(
            "Completion method not in guide data. Quest may be scripted or not yet completable.",
            notice
        );
    }

    [Fact]
    public void GetCompletionFallbackNotice_WithCompletionEdges_ReturnsNull()
    {
        var guide = new CompiledGuideBuilder()
            .AddQuest("quest:root", dbName: "RootQuest")
            .AddCharacter("character:turnin")
            .AddEdge("quest:root", "character:turnin", EdgeType.CompletedBy)
            .Build();
        var quest = guide.GetNode("quest:root")!;

        string? notice = ViewRenderer.GetCompletionFallbackNotice(guide, quest);

        Assert.Null(notice);
    }

    [Fact]
    public void BuildDetailSections_SplitsAcceptObjectivesAndTurnInGroups()
    {
        var roots = new SpecTreeRef[]
        {
            SpecTreeRef.ForGraphNode(
                1,
                SpecTreeKind.Giver,
                0,
                "Torn Note",
                "Read Torn Note",
                false,
                false
            ),
            SpecTreeRef.ForGraphNode(
                2,
                SpecTreeKind.Giver,
                0,
                "Marching Orders",
                "Read Marching Orders",
                false,
                false
            ),
            SpecTreeRef.ForGraphNode(
                3,
                SpecTreeKind.Item,
                0,
                "Torn Note",
                "Collect: Torn Note",
                false,
                false
            ),
            SpecTreeRef.ForGraphNode(
                4,
                SpecTreeKind.Step,
                0,
                "Ritual",
                "Talk to Elder Brother",
                false,
                false
            ),
            SpecTreeRef.ForGraphNode(
                5,
                SpecTreeKind.Completer,
                0,
                "Lucian Revald",
                "Turn in to Lucian Revald",
                false,
                false
            ),
            SpecTreeRef.ForGraphNode(
                6,
                SpecTreeKind.Completer,
                0,
                "Lucian Revald",
                "Turn in to Lucian Revald",
                false,
                true
            ),
        };

        var sections = ViewRenderer.BuildDetailSections(roots);

        Assert.Collection(
            sections,
            section =>
            {
                Assert.Equal("Accept", section.Label);
                Assert.True(section.ShowAlternativesLabel);
                Assert.Equal(2, section.Roots.Count);
            },
            section =>
            {
                Assert.Equal("Objectives", section.Label);
                Assert.False(section.ShowAlternativesLabel);
                Assert.Equal(2, section.Roots.Count);
            },
            section =>
            {
                Assert.Equal("Turn in", section.Label);
                Assert.True(section.ShowAlternativesLabel);
                Assert.Equal(2, section.Roots.Count);
            }
        );
    }

    [Fact]
    public void GetRootChildrenForDetail_ReusesProjectionUntilTrackerVersionChanges()
    {
        var guide = new CompiledGuideBuilder()
            .AddCharacter("char:giver")
            .AddQuest("quest:root", dbName: "ROOT", givers: new[] { "char:giver" })
            .Build();
        var dependencies = new GuideDependencyEngine();
        var tracker = new QuestStateTracker(guide, dependencies);
        tracker.LoadState(
            currentZone: string.Empty,
            activeQuests: Array.Empty<string>(),
            completedQuests: Array.Empty<string>(),
            inventoryCounts: new Dictionary<string, int>(),
            keyringItemKeys: Array.Empty<string>()
        );
        var phases = new QuestPhaseTracker(guide);
        phases.Initialize(
            Array.Empty<string>(),
            Array.Empty<string>(),
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        var projector = new SpecTreeProjector(
            guide,
            phases,
            new UnlockPredicateEvaluator(guide, phases),
            null,
            () => string.Empty
        );
        var renderer = new ViewRenderer(
            guide,
            new GameState(guide),
            new NavigationSet(),
            tracker,
            new TrackerState(),
            projector
        );

        var first = renderer.GetRootChildrenForDetail(0);
        var second = renderer.GetRootChildrenForDetail(0);
        Assert.Same(first, second);

        tracker.OnQuestAssigned("ROOT");
        var afterVersionChange = renderer.GetRootChildrenForDetail(0);
        Assert.NotSame(first, afterVersionChange);
    }

    [Fact]
    public void GetChildrenForDetail_ReusesProjectionUntilTrackerVersionChanges()
    {
        var guide = new CompiledGuideBuilder()
            .AddCharacter("char:gate-giver")
            .AddQuest("quest:gate", dbName: "GATE", givers: new[] { "char:gate-giver" })
            .AddQuest("quest:root", dbName: "ROOT", prereqs: new[] { "quest:gate" })
            .Build();
        var fixture = CreateRendererFixture(guide);
        int questIndex = FindQuestIndex(guide, "ROOT");
        var prerequisiteRef = fixture
            .Renderer.GetRootChildrenForDetail(questIndex)
            .Single(r => r.Kind == SpecTreeKind.Prerequisite);

        var first = fixture.Renderer.GetChildrenForDetail(prerequisiteRef);
        var second = fixture.Renderer.GetChildrenForDetail(prerequisiteRef);
        Assert.Same(first, second);

        fixture.Tracker.OnQuestAssigned("ROOT");
        var afterVersionChange = fixture.Renderer.GetChildrenForDetail(prerequisiteRef);
        Assert.NotSame(first, afterVersionChange);
    }

    [Fact]
    public void GetUnlockChildrenForDetail_ReusesProjectionUntilTrackerVersionChanges()
    {
        var guide = new CompiledGuideBuilder()
            .AddItem("item:key")
            .AddCharacter("char:enemy", isFriendly: false)
            .AddCharacter("char:npc")
            .AddItemSource(
                "item:key",
                "char:enemy",
                edgeType: (byte)EdgeType.DropsItem,
                sourceType: (byte)NodeType.Character
            )
            .AddUnlockPredicate("char:npc", "item:key", checkType: 1)
            .AddQuest("quest:a", dbName: "QUESTA", completers: new[] { "char:npc" })
            .Build();
        var fixture = CreateRendererFixture(guide, activeQuestDbNames: new[] { "QUESTA" });
        int questIndex = FindQuestIndex(guide, "QUESTA");
        var completerRef = fixture
            .Renderer.GetRootChildrenForDetail(questIndex)
            .Single(r => r.Kind == SpecTreeKind.Completer);

        var first = fixture.Renderer.GetUnlockChildrenForDetail(completerRef);
        var second = fixture.Renderer.GetUnlockChildrenForDetail(completerRef);
        Assert.Same(first, second);

        fixture.Tracker.OnQuestCompleted("QUESTA");
        var afterVersionChange = fixture.Renderer.GetUnlockChildrenForDetail(completerRef);
        Assert.NotSame(first, afterVersionChange);
    }

    private static (QuestStateTracker Tracker, ViewRenderer Renderer) CreateRendererFixture(
        AdventureGuide.CompiledGuide.CompiledGuide guide,
        string[]? activeQuestDbNames = null,
        string[]? completedQuestDbNames = null
    )
    {
        var dependencies = new GuideDependencyEngine();
        var tracker = new QuestStateTracker(guide, dependencies);
        tracker.LoadState(
            currentZone: string.Empty,
            activeQuests: activeQuestDbNames ?? Array.Empty<string>(),
            completedQuests: completedQuestDbNames ?? Array.Empty<string>(),
            inventoryCounts: new Dictionary<string, int>(),
            keyringItemKeys: Array.Empty<string>()
        );
        var phases = new QuestPhaseTracker(guide);
        phases.Initialize(
            completedQuestDbNames ?? Array.Empty<string>(),
            activeQuestDbNames ?? Array.Empty<string>(),
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        var projector = new SpecTreeProjector(
            guide,
            phases,
            new UnlockPredicateEvaluator(guide, phases),
            null,
            () => string.Empty
        );
        var renderer = new ViewRenderer(
            guide,
            new GameState(guide),
            new NavigationSet(),
            tracker,
            new TrackerState(),
            projector
        );
        return (tracker, renderer);
    }

    private static int FindQuestIndex(
        AdventureGuide.CompiledGuide.CompiledGuide guide,
        string dbName
    )
    {
        for (int questIndex = 0; questIndex < guide.QuestCount; questIndex++)
        {
            int nodeId = guide.QuestNodeId(questIndex);
            if (string.Equals(guide.GetDbName(nodeId), dbName, StringComparison.OrdinalIgnoreCase))
                return questIndex;
        }

        throw new InvalidOperationException($"Quest '{dbName}' not found.");
    }

    [Fact]
    public void ResolveGraphNode_SyntheticRef_ReturnsNull()
    {
        var guide = new CompiledGuideBuilder().AddQuest("quest:root", dbName: "ROOT").Build();
        var fixture = CreateRendererFixture(guide);
        var syntheticRef = SpecTreeRef.ForSynthetic(
            "group:test",
            SpecTreeKind.Group,
            questIndex: 0,
            displayName: "Any of:",
            label: "Any of:",
            isCompleted: false,
            isBlocked: false,
            syntheticChildren: Array.Empty<SpecTreeRef>(),
            requiresVisibleChildren: true
        );

        Assert.Null(fixture.Renderer.ResolveGraphNode(syntheticRef));
    }
}
