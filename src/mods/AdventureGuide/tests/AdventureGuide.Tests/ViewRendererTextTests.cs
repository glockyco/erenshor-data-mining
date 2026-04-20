using AdventureGuide.Frontier;
using AdventureGuide.Incremental;
using AdventureGuide.Graph;
using AdventureGuide.Navigation;
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
    public void GetRootChildrenForDetail_ReusesProjectionUntilCompiledQuestStateChanges()
    {
        var guide = new CompiledGuideBuilder()
            .AddCharacter("char:giver")
            .AddQuest("quest:root", dbName: "ROOT", givers: new[] { "char:giver" })
            .Build();
        var tracker = new QuestStateTracker(guide);
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
        var (reader, projector) = ResolutionTestFactory.BuildSpecTreeProjector(
            guide, phases, currentSceneProvider: () => string.Empty);
        var renderer = new ViewRenderer(
            guide, new GameState(guide), new NavigationSet(), tracker,
            new TrackerState(), projector);

        var first = renderer.GetRootChildrenForDetail(0);
        var second = renderer.GetRootChildrenForDetail(0);
        Assert.Same(first, second);

        // Simulate Plugin.Update: tracker mutation flows into the engine via the
        // emitted ChangeSet's facts. Backdating preserves the cached projection
        // because the compiled phases tracker has not been advanced yet, so the
        // recomputed value equals the previous one.
        tracker.OnQuestAssigned("ROOT");
        reader.Engine.InvalidateFacts(tracker.LastChangeSet.ChangedFacts);
        var beforeCompiledSync = renderer.GetRootChildrenForDetail(0);
        Assert.Same(first, beforeCompiledSync);

        // Phases.Initialize bypasses the change-tracking path. Mimic Plugin's
        // invalidation by emitting the QuestActive/QuestCompleted wildcards so
        // the engine recomputes; the phase change shifts the resolved children.
        phases.Initialize(
            Array.Empty<string>(),
            new[] { "ROOT" },
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        reader.Engine.InvalidateFacts(new[]
        {
            new FactKey(FactKind.QuestActive, "*"),
            new FactKey(FactKind.QuestCompleted, "*"),
        });

        var afterCompiledChange = renderer.GetRootChildrenForDetail(0);
        Assert.NotSame(first, afterCompiledChange);
    }

    [Fact]
    public void GetRootChildrenForDetail_RefreshesWhenCompiledQuestStateCatchesUp()
    {
        var guide = new CompiledGuideBuilder()
            .AddCharacter("char:giver")
            .AddQuest("quest:root", dbName: "ROOT", givers: new[] { "char:giver" })
            .Build();
        var tracker = new QuestStateTracker(guide);
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
        var (reader, projector) = ResolutionTestFactory.BuildSpecTreeProjector(
            guide, phases, currentSceneProvider: () => string.Empty);
        var renderer = new ViewRenderer(
            guide, new GameState(guide), new NavigationSet(), tracker,
            new TrackerState(), projector);

        var initial = renderer.GetRootChildrenForDetail(0);
        var initialGiver = Assert.Single(initial, root => root.Kind == SpecTreeKind.Giver);
        Assert.False(initialGiver.IsCompleted);

        tracker.OnQuestAssigned("ROOT");
        reader.Engine.InvalidateFacts(tracker.LastChangeSet.ChangedFacts);
        var stale = renderer.GetRootChildrenForDetail(0);
        var staleGiver = Assert.Single(stale, root => root.Kind == SpecTreeKind.Giver);
        Assert.False(staleGiver.IsCompleted);

        phases.Initialize(
            Array.Empty<string>(),
            new[] { "ROOT" },
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        reader.Engine.InvalidateFacts(new[]
        {
            new FactKey(FactKind.QuestActive, "*"),
            new FactKey(FactKind.QuestCompleted, "*"),
        });

        var refreshed = renderer.GetRootChildrenForDetail(0);
        var refreshedGiver = Assert.Single(refreshed, root => root.Kind == SpecTreeKind.Giver);

        Assert.NotSame(stale, refreshed);
        Assert.True(refreshedGiver.IsCompleted);
    }

    [Fact]
    public void GetRootChildrenForDetail_ReusesQuestRootAfterSwitchingBack()
    {
        var guide = new CompiledGuideBuilder()
            .AddCharacter("char:giver-a")
            .AddCharacter("char:giver-b")
            .AddQuest("quest:first", dbName: "FIRST", givers: new[] { "char:giver-a" })
            .AddQuest("quest:second", dbName: "SECOND", givers: new[] { "char:giver-b" })
            .Build();
        var fixture = CreateRendererFixture(guide);
        int firstQuestIndex = FindQuestIndex(guide, "FIRST");
        int secondQuestIndex = FindQuestIndex(guide, "SECOND");

        var first = fixture.Renderer.GetRootChildrenForDetail(firstQuestIndex);
        var second = fixture.Renderer.GetRootChildrenForDetail(secondQuestIndex);
        var firstAgain = fixture.Renderer.GetRootChildrenForDetail(firstQuestIndex);

        Assert.NotSame(first, second);
        Assert.Same(first, firstAgain);
    }

    [Fact]
    public void GetChildrenForDetail_ReusesProjectionUntilCompiledQuestStateChanges()
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
                fixture.Engine.InvalidateFacts(fixture.Tracker.LastChangeSet.ChangedFacts);
                var beforeCompiledSync = fixture.Renderer.GetChildrenForDetail(prerequisiteRef);
        Assert.Same(first, beforeCompiledSync);

        fixture.Phases.Initialize(
                    Array.Empty<string>(),
                    new[] { "ROOT" },
                    new Dictionary<string, int>(),
                    Array.Empty<string>()
                );
                fixture.Engine.InvalidateFacts(new[]
                {
                    new FactKey(FactKind.QuestActive, "*"),
                    new FactKey(FactKind.QuestCompleted, "*"),
                });

                var afterCompiledChange = fixture.Renderer.GetChildrenForDetail(prerequisiteRef);
        Assert.NotSame(first, afterCompiledChange);
    }

    [Fact]
    public void GetUnlockChildrenForDetail_ReusesProjectionUntilCompiledQuestStateChanges()
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
                fixture.Engine.InvalidateFacts(fixture.Tracker.LastChangeSet.ChangedFacts);
                var beforeCompiledSync = fixture.Renderer.GetUnlockChildrenForDetail(completerRef);
        Assert.Same(first, beforeCompiledSync);

        fixture.Phases.Initialize(
                    new[] { "QUESTA" },
                    Array.Empty<string>(),
                    new Dictionary<string, int>(),
                    Array.Empty<string>()
                );
                fixture.Engine.InvalidateFacts(new[]
                {
                    new FactKey(FactKind.QuestActive, "*"),
                    new FactKey(FactKind.QuestCompleted, "*"),
                });

                var afterCompiledChange = fixture.Renderer.GetUnlockChildrenForDetail(completerRef);
        Assert.NotSame(first, afterCompiledChange);
    }

    private static (
        QuestStateTracker Tracker,
        QuestPhaseTracker Phases,
        ViewRenderer Renderer,
        Engine<FactKey> Engine
    ) CreateRendererFixture(
        AdventureGuide.CompiledGuide.CompiledGuide guide,
        string[]? activeQuestDbNames = null,
        string[]? completedQuestDbNames = null
    )
    {
        var tracker = new QuestStateTracker(guide);
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
        var (reader, projector) = ResolutionTestFactory.BuildSpecTreeProjector(
            guide, phases, currentSceneProvider: () => string.Empty);
        var renderer = new ViewRenderer(
            guide, new GameState(guide), new NavigationSet(), tracker,
            new TrackerState(), projector);
        return (tracker, phases, renderer, reader.Engine);
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
