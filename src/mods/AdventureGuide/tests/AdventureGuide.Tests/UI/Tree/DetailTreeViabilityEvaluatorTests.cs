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
