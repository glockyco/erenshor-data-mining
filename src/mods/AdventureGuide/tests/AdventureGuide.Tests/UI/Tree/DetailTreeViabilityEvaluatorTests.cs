using AdventureGuide.CompiledGuide;
using AdventureGuide.Frontier;
using AdventureGuide.Graph;
using AdventureGuide.Resolution;
using AdventureGuide.Tests.Helpers;
using AdventureGuide.UI.Tree;
using Xunit;

namespace AdventureGuide.Tests.UI.Tree;

public sealed class DetailTreeViabilityEvaluatorTests
{
    [Fact]
    public void Any_of_item_acquisition_keeps_viable_source_when_cyclic_source_prunes()
    {
        var guide = new CompiledGuideBuilder()
            .AddItem("item:root")
            .AddCharacter("char:locked")
            .AddCharacter("char:vendor")
            .AddQuest("quest:root", dbName: "ROOT", requiredItems: new[] { ("item:root", 1) })
            .AddItemSource(
                "item:root",
                "char:locked",
                edgeType: (byte)EdgeType.DropsItem,
                sourceType: (byte)NodeType.Character
            )
            .AddUnlockPredicate("char:locked", "item:root", checkType: 1)
            .AddItemSource(
                "item:root",
                "char:vendor",
                edgeType: (byte)EdgeType.SellsItem,
                sourceType: (byte)NodeType.Character
            )
            .Build();
        var evaluator = BuildEvaluator(guide, out int rootQuestIndex);
        Assert.True(guide.TryGetNodeId("item:root", out int itemNodeId));

        var result = evaluator.Evaluate(
            new DetailGoal(DetailGoalKind.AcquireItem, itemNodeId),
            new DetailBranchContext(rootQuestIndex, new[] { guide.QuestNodeId(rootQuestIndex) })
        );

        Assert.True(result.IsViable);
        var child = Assert.Single(result.SurvivingChildren);
        Assert.Equal(DetailGoalKind.UnlockSource, child.Kind);
        Assert.True(guide.TryGetNodeId("char:vendor", out int vendorNodeId));
        Assert.Equal(vendorNodeId, child.NodeId);
    }

    [Fact]
    public void All_of_quest_completion_prunes_when_required_item_cycles_to_ancestor()
    {
        var guide = new CompiledGuideBuilder()
            .AddItem("item:root")
            .AddQuest("quest:cyclic", dbName: "CYCLIC", requiredItems: new[] { ("item:root", 1) })
            .AddQuest("quest:root", dbName: "ROOT", requiredItems: new[] { ("item:root", 1) })
            .Build();
        var evaluator = BuildEvaluator(guide, out int rootQuestIndex);
        Assert.True(guide.TryGetNodeId("item:root", out int itemNodeId));
        Assert.True(guide.TryGetNodeId("quest:cyclic", out int cyclicQuestNodeId));

        var result = evaluator.Evaluate(
            new DetailGoal(DetailGoalKind.CompleteQuest, cyclicQuestNodeId),
            new DetailBranchContext(rootQuestIndex, new[] { itemNodeId, cyclicQuestNodeId })
        );

        Assert.False(result.IsViable);
        Assert.Equal(DetailPruneReason.RequiredChildPruned, result.Reason);
        Assert.Empty(result.SurvivingChildren);
    }

    [Fact]
    public void Item_action_prunes_when_no_acquisition_alternative_survives()
    {
        var guide = new CompiledGuideBuilder()
            .AddItem("item:marching-orders")
            .AddCharacter("char:gherist")
            .AddQuest("quest:root", dbName: "ROOT", givers: new[] { "item:marching-orders" })
            .AddItemSource(
                "item:marching-orders",
                "char:gherist",
                edgeType: (byte)EdgeType.DropsItem,
                sourceType: (byte)NodeType.Character
            )
            .AddUnlockPredicate("char:gherist", "quest:root")
            .Build();
        var evaluator = BuildEvaluator(guide, out int rootQuestIndex);
        Assert.True(guide.TryGetNodeId("item:marching-orders", out int itemNodeId));

        var result = evaluator.Evaluate(
            new DetailGoal(DetailGoalKind.UseItemAction, itemNodeId),
            new DetailBranchContext(
                rootQuestIndex,
                new[] { guide.QuestNodeId(rootQuestIndex), itemNodeId }
            )
        );

        Assert.False(result.IsViable);
        Assert.Equal(DetailPruneReason.NoAcquisitionSource, result.Reason);
        Assert.Empty(result.SurvivingChildren);
    }

    [Fact]
    public void Acquire_item_uses_compiled_dependency_children_without_raw_item_sources()
    {
        var guide = BuildCompiledDependencyOnlyGuide();
        var evaluator = BuildEvaluator(guide, out int rootQuestIndex);
        Assert.True(guide.TryGetNodeId("item:note", out int itemNodeId));
        Assert.True(guide.TryGetNodeId("char:source", out int sourceNodeId));

        var result = evaluator.Evaluate(
            new DetailGoal(DetailGoalKind.AcquireItem, itemNodeId),
            new DetailBranchContext(rootQuestIndex, new[] { guide.QuestNodeId(rootQuestIndex) })
        );

        Assert.True(result.IsViable);
        var child = Assert.Single(result.SurvivingChildren);
        Assert.Equal(DetailGoalKind.UnlockSource, child.Kind);
        Assert.Equal(sourceNodeId, child.NodeId);
    }

    [Fact]
    public void Recipe_source_prunes_when_any_required_material_is_not_acquirable()
    {
        var guide = new CompiledGuideBuilder()
            .AddItem("item:ring")
            .AddItem("item:good-material")
            .AddItem("item:blocked-material")
            .AddItem("item:missing-key")
            .AddRecipe("recipe:ring")
            .AddCharacter("char:good-source")
            .AddCharacter("char:blocked-source")
            .AddItemSource(
                "item:ring",
                "recipe:ring",
                edgeType: (byte)EdgeType.Produces,
                sourceType: (byte)NodeType.Recipe
            )
            .AddEdge("recipe:ring", "item:good-material", EdgeType.RequiresMaterial, quantity: 1)
            .AddEdge("recipe:ring", "item:blocked-material", EdgeType.RequiresMaterial, quantity: 1)
            .AddItemSource(
                "item:good-material",
                "char:good-source",
                edgeType: (byte)EdgeType.DropsItem,
                sourceType: (byte)NodeType.Character
            )
            .AddItemSource(
                "item:blocked-material",
                "char:blocked-source",
                edgeType: (byte)EdgeType.DropsItem,
                sourceType: (byte)NodeType.Character
            )
            .AddUnlockPredicate("char:blocked-source", "item:missing-key", checkType: 1)
            .AddQuest("quest:root", dbName: "ROOT", requiredItems: new[] { ("item:ring", 1) })
            .Build();
        var evaluator = BuildEvaluator(guide, out int rootQuestIndex);
        Assert.True(guide.TryGetNodeId("item:ring", out int ringNodeId));

        var result = evaluator.Evaluate(
            new DetailGoal(DetailGoalKind.AcquireItem, ringNodeId),
            new DetailBranchContext(rootQuestIndex, new[] { guide.QuestNodeId(rootQuestIndex) })
        );

        Assert.False(result.IsViable);
        Assert.Equal(DetailPruneReason.NoAcquisitionSource, result.Reason);
    }

    private static AdventureGuide.CompiledGuide.CompiledGuide BuildCompiledDependencyOnlyGuide()
    {
        var data = new CompiledGuideData
        {
            Nodes = new[]
            {
                new CompiledNodeData
                {
                    NodeId = 0,
                    Key = "quest:root",
                    NodeType = (int)NodeType.Quest,
                    DisplayName = "Root Quest",
                    DbName = "ROOT",
                },
                new CompiledNodeData
                {
                    NodeId = 1,
                    Key = "item:note",
                    NodeType = (int)NodeType.Item,
                    DisplayName = "Torn Note",
                },
                new CompiledNodeData
                {
                    NodeId = 2,
                    Key = "char:source",
                    NodeType = (int)NodeType.Character,
                    DisplayName = "Source",
                },
            },
            Edges = Array.Empty<CompiledEdgeData>(),
            ForwardAdjacency = new[] { Array.Empty<int>(), Array.Empty<int>(), Array.Empty<int>() },
            ReverseAdjacency = new[] { Array.Empty<int>(), Array.Empty<int>(), Array.Empty<int>() },
            QuestNodeIds = new[] { 0 },
            ItemNodeIds = new[] { 1 },
            QuestSpecs = new[]
            {
                new CompiledQuestSpecData { QuestId = 0, QuestIndex = 0 },
            },
            ItemSources = new[] { Array.Empty<CompiledSourceSiteData>() },
            UnlockPredicates = Array.Empty<CompiledUnlockPredicateData>(),
            DetailGoals = new[]
            {
                new CompiledDetailGoalData
                {
                    GoalKind = (int)DetailGoalKind.AcquireItem,
                    NodeId = 1,
                    DependencyIndices = new[] { 0 },
                },
                new CompiledDetailGoalData
                {
                    GoalKind = (int)DetailGoalKind.UnlockSource,
                    NodeId = 2,
                    DependencyIndices = Array.Empty<int>(),
                },
            },
            DetailDependencies = new[]
            {
                new CompiledDetailDependencyData
                {
                    GoalKind = (int)DetailGoalKind.AcquireItem,
                    NodeId = 1,
                    Semantics = 0,
                    ChildGoalIndices = new[] { 1 },
                },
            },
            TopoOrder = new[] { 0 },
            QuestToDependentQuestIndices = new[] { Array.Empty<int>() },
            ZoneNodeIds = Array.Empty<int>(),
            ZoneAdjacency = Array.Empty<int[]>(),
            GiverBlueprints = Array.Empty<CompiledGiverBlueprintData>(),
            CompletionBlueprints = Array.Empty<CompiledCompletionBlueprintData>(),
            InfeasibleNodeIds = Array.Empty<int>(),
        };

        return new AdventureGuide.CompiledGuide.CompiledGuide(data);
    }

    private static DetailTreeViabilityEvaluator BuildEvaluator(
        AdventureGuide.CompiledGuide.CompiledGuide guide,
        out int rootQuestIndex
    )
    {
        rootQuestIndex = FindQuestIndex(guide, "quest:root");
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(
            Array.Empty<string>(),
            Array.Empty<string>(),
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        var reader = ResolutionTestFactory
            .BuildSpecTreeProjector(guide, tracker, currentSceneProvider: () => string.Empty)
            .Reader;
        QuestResolutionRecord record = reader.ReadQuestResolution("quest:root", string.Empty);
        return new DetailTreeViabilityEvaluator(guide, record);
    }

    private static int FindQuestIndex(AdventureGuide.CompiledGuide.CompiledGuide guide, string key)
    {
        Assert.True(guide.TryGetNodeId(key, out int nodeId));
        for (int questIndex = 0; questIndex < guide.QuestCount; questIndex++)
        {
            if (guide.QuestNodeId(questIndex) == nodeId)
                return questIndex;
        }

        throw new InvalidOperationException($"Quest '{key}' not found in compiled guide.");
    }
}
