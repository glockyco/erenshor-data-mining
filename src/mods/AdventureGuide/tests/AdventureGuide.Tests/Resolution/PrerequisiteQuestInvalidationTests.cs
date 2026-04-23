using AdventureGuide.Graph;
using AdventureGuide.Frontier;
using AdventureGuide.Incremental;
using AdventureGuide.Navigation;
using AdventureGuide.Resolution;
using AdventureGuide.Resolution.Queries;
using AdventureGuide.State;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests.Resolution;

public sealed class PrerequisiteQuestInvalidationTests
{
    [Fact]
    public void ParentResolution_WithoutSharedBatchScope_PreservesPrerequisiteCycleGuard()
    {
        const string scene = "Forest";
        var guide = new CompiledGuideBuilder()
            .AddItem("item:a-token")
            .AddItem("item:b-token")
            .AddQuest(
                "quest:a",
                dbName: "QUESTA",
                requiredItems: new[] { ("item:b-token", 1) })
            .AddEdge("quest:a", "item:a-token", EdgeType.RewardsItem)
            .AddQuest(
                "quest:b",
                dbName: "QUESTB",
                requiredItems: new[] { ("item:a-token", 1) })
            .AddEdge("quest:b", "item:b-token", EdgeType.RewardsItem)
            .Build();

        var tracker = new QuestStateTracker(guide);
        tracker.LoadState(
            currentZone: scene,
            activeQuests: new[] { "QUESTA", "QUESTB" },
            completedQuests: Array.Empty<string>(),
            inventoryCounts: new Dictionary<string, int>(StringComparer.Ordinal),
            keyringItemKeys: Array.Empty<string>());
        var phases = new QuestPhaseTracker(guide, tracker);
        var engine = new Engine<FactKey>();
        var frontier = new EffectiveFrontier(guide, phases);
        var resolver = new SourceResolver(
            guide,
            phases,
            new UnlockPredicateEvaluator(guide, phases),
            new StubLivePositionProvider(),
            TestPositionResolvers.Create(guide));
        var reader = ResolutionTestFactory.BuildService(
            guide,
            frontier,
            resolver,
            phases,
            engine: engine,
            trackerState: new TrackerState(),
            navSet: new NavigationSet());

        var resolution = reader.ReadQuestResolution("quest:a", scene);

        Assert.Empty(resolution.CompiledTargets);
    }

    [Fact]
    public void FirstParentResolution_InSharedBatchWithColdPrerequisiteQuery_RetainsPrerequisiteTargets()
    {
        const string scene = "Forest";
        var guide = new CompiledGuideBuilder()
            .AddItem("item:ore")
            .AddCharacter("char:ore-vein", scene: scene, x: 10f, y: 20f, z: 30f)
            .AddItemSource(
                "item:ore",
                "char:ore-vein",
                edgeType: (byte)EdgeType.DropsItem,
                sourceType: (byte)NodeType.Character)
            .AddItem("item:note")
            .AddCharacter("char:scribe", scene: scene, x: 40f, y: 50f, z: 60f)
            .AddQuest(
                "quest:prereq",
                dbName: "PREREQ",
                requiredItems: new[] { ("item:ore", 1) },
                completers: new[] { "char:scribe" })
            .AddEdge("quest:prereq", "item:note", EdgeType.RewardsItem)
            .AddQuest(
                "quest:parent-a",
                dbName: "PARENTA",
                prereqs: new[] { "quest:prereq" },
                requiredItems: new[] { ("item:note", 1) })
            .Build();

        var tracker = new QuestStateTracker(guide);
        tracker.LoadState(
            currentZone: scene,
            activeQuests: new[] { "PREREQ", "PARENTA" },
            completedQuests: Array.Empty<string>(),
            inventoryCounts: new Dictionary<string, int>(StringComparer.Ordinal),
            keyringItemKeys: Array.Empty<string>());
        Assert.True(guide.TryGetNodeId("quest:parent-a", out int parentANodeId));
        int parentAIndex = guide.FindQuestIndex(parentANodeId);
        var phases = new QuestPhaseTracker(guide, tracker);
        var engine = new Engine<FactKey>();
        var frontier = new EffectiveFrontier(guide, phases);
        var resolver = new SourceResolver(
            guide,
            phases,
            new UnlockPredicateEvaluator(guide, phases),
            new StubLivePositionProvider(),
            TestPositionResolvers.Create(guide));
        var reader = ResolutionTestFactory.BuildService(
            guide,
            frontier,
            resolver,
            phases,
            engine: engine,
            trackerState: new TrackerState(),
            navSet: new NavigationSet());

        using (CompiledTargetsQuery.BeginSharedResolutionBatchScope())
        {
            var firstParent = reader.ReadQuestResolution("quest:parent-a", scene);

            Assert.True(HasTarget(guide, firstParent.CompiledTargets, "char:ore-vein", requiredForQuestIndex: null));
            Assert.Contains(firstParent.CompiledTargets, target => target.RequiredForQuestIndex == parentAIndex);
        }
    }

    [Fact]
    public void ParentResolution_TracksPrerequisiteQuestInvalidation_AfterSharedBatchReuse()
    {
        const string scene = "Forest";
        var guide = new CompiledGuideBuilder()
            .AddItem("item:ore")
            .AddCharacter("char:ore-vein", scene: scene, x: 10f, y: 20f, z: 30f)
            .AddItemSource(
                "item:ore",
                "char:ore-vein",
                edgeType: (byte)EdgeType.DropsItem,
                sourceType: (byte)NodeType.Character)
            .AddItem("item:note")
            .AddCharacter("char:scribe", scene: scene, x: 40f, y: 50f, z: 60f)
            .AddQuest(
                "quest:prereq",
                dbName: "PREREQ",
                requiredItems: new[] { ("item:ore", 1) },
                completers: new[] { "char:scribe" })
            .AddEdge("quest:prereq", "item:note", EdgeType.RewardsItem)
            .AddQuest(
                "quest:parent-a",
                dbName: "PARENTA",
                prereqs: new[] { "quest:prereq" },
                requiredItems: new[] { ("item:note", 1) })
            .AddQuest(
                "quest:parent-b",
                dbName: "PARENTB",
                prereqs: new[] { "quest:prereq" },
                requiredItems: new[] { ("item:note", 1) })
            .Build();

        var tracker = new QuestStateTracker(guide);
        tracker.LoadState(
            currentZone: scene,
            activeQuests: new[] { "PREREQ", "PARENTA", "PARENTB" },
            completedQuests: Array.Empty<string>(),
            inventoryCounts: new Dictionary<string, int>(StringComparer.Ordinal),
            keyringItemKeys: Array.Empty<string>());
        Assert.True(guide.TryGetNodeId("quest:parent-b", out int parentBNodeId));
        int parentBIndex = guide.FindQuestIndex(parentBNodeId);
        var phases = new QuestPhaseTracker(guide, tracker);
        var engine = new Engine<FactKey>();
        var frontier = new EffectiveFrontier(guide, phases);
        var resolver = new SourceResolver(
            guide,
            phases,
            new UnlockPredicateEvaluator(guide, phases),
            new StubLivePositionProvider(),
            TestPositionResolvers.Create(guide));
        var reader = ResolutionTestFactory.BuildService(
            guide,
            frontier,
            resolver,
            phases,
            engine: engine,
            trackerState: new TrackerState(),
            navSet: new NavigationSet());

        using (CompiledTargetsQuery.BeginSharedResolutionBatchScope())
        {
            _ = reader.ReadQuestResolution("quest:parent-a", scene);
            var secondParent = reader.ReadQuestResolution("quest:parent-b", scene);

            Assert.True(HasTarget(guide, secondParent.CompiledTargets, "char:ore-vein", requiredForQuestIndex: null));
            Assert.Contains(secondParent.CompiledTargets, target => target.RequiredForQuestIndex == parentBIndex);
        }

        tracker.LoadState(
            currentZone: scene,
            activeQuests: new[] { "PREREQ", "PARENTA", "PARENTB" },
            completedQuests: Array.Empty<string>(),
            inventoryCounts: new Dictionary<string, int>(StringComparer.Ordinal) { ["item:ore"] = 1 },
            keyringItemKeys: Array.Empty<string>());
        engine.InvalidateFacts(new[] { new FactKey(FactKind.InventoryItemCount, "item:ore") });

        var updatedPrerequisite = reader.ReadQuestResolution("quest:prereq", scene);
        var updatedParent = reader.ReadQuestResolution("quest:parent-b", scene);

        Assert.False(HasTarget(guide, updatedPrerequisite.CompiledTargets, "char:ore-vein", requiredForQuestIndex: null));
        Assert.False(HasTarget(guide, updatedParent.CompiledTargets, "char:ore-vein", requiredForQuestIndex: null));
    }

    private static bool HasTarget(
        AdventureGuide.CompiledGuide.CompiledGuide guide,
        IReadOnlyList<ResolvedTarget> targets,
        string targetKey,
        int? requiredForQuestIndex)
    {
        for (int i = 0; i < targets.Count; i++)
        {
            if (!string.Equals(guide.GetNodeKey(targets[i].TargetNodeId), targetKey, StringComparison.Ordinal))
                continue;
            if (requiredForQuestIndex.HasValue && targets[i].RequiredForQuestIndex != requiredForQuestIndex.Value)
                continue;
            return true;
        }

        return false;
    }

    private sealed class StubLivePositionProvider : ILivePositionProvider
    {
        public WorldPosition? GetLivePosition(int spawnNodeId) => null;

        public bool IsAlive(int spawnNodeId) => false;
    }
}
