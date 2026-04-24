using AdventureGuide.CompiledGuide;
using AdventureGuide.Graph;
using AdventureGuide.Tests.Helpers;
using Xunit;
using CompiledGuideModel = AdventureGuide.CompiledGuide.CompiledGuide;

namespace AdventureGuide.Tests;

public sealed class CompiledGuideTypesTests
{
    [Fact]
    public void CompiledGuide_exposes_counts_and_string_lookup()
    {
        var data = new CompiledGuideData
        {
            Nodes = new[]
            {
                new CompiledNodeData
                {
                    NodeId = 0,
                    Key = "quest:a",
                    NodeType = 0,
                    DisplayName = "Quest A",
                },
            },
            Edges = Array.Empty<CompiledEdgeData>(),
            ForwardAdjacency = new[] { Array.Empty<int>() },
            ReverseAdjacency = new[] { Array.Empty<int>() },
            QuestNodeIds = new[] { 0 },
            ItemNodeIds = Array.Empty<int>(),
            QuestSpecs = new[]
            {
                new CompiledQuestSpecData { QuestId = 0, QuestIndex = 0 },
            },
            ItemSources = Array.Empty<CompiledSourceSiteData[]>(),
            UnlockPredicates = Array.Empty<CompiledUnlockPredicateData>(),
            TopoOrder = new[] { 0 },
            ItemToQuestIndices = Array.Empty<int[]>(),
            QuestToDependentQuestIndices = new[] { Array.Empty<int>() },
            ZoneNodeIds = Array.Empty<int>(),
            ZoneAdjacency = Array.Empty<int[]>(),
            GiverBlueprints = Array.Empty<CompiledGiverBlueprintData>(),
            CompletionBlueprints = Array.Empty<CompiledCompletionBlueprintData>(),
            InfeasibleNodeIds = Array.Empty<int>(),
        };
        var guide = new CompiledGuideModel(data);

        Assert.Equal(1, guide.NodeCount);
        Assert.Equal(0, guide.EdgeCount);
        Assert.Equal(1, guide.QuestCount);
        Assert.Equal(0, guide.ItemCount);
        Assert.Equal("quest:a", guide.GetNodeKey(0));
        Assert.Equal("Quest A", guide.GetDisplayName(0));
        Assert.True(guide.TryGetNodeId("quest:a", out int id));
        Assert.Equal(0, id);
    }

    [Fact]
    public void CompiledGuide_loads_detail_dependency_summaries()
    {
        var data = new CompiledGuideData
        {
            Nodes = new[]
            {
                new CompiledNodeData
                {
                    NodeId = 0,
                    Key = "item:note",
                    NodeType = 1,
                    DisplayName = "Torn Note",
                },
            },
            Edges = Array.Empty<CompiledEdgeData>(),
            ForwardAdjacency = new[] { Array.Empty<int>() },
            ReverseAdjacency = new[] { Array.Empty<int>() },
            QuestNodeIds = Array.Empty<int>(),
            ItemNodeIds = new[] { 0 },
            QuestSpecs = Array.Empty<CompiledQuestSpecData>(),
            ItemSources = new[] { Array.Empty<CompiledSourceSiteData>() },
            UnlockPredicates = Array.Empty<CompiledUnlockPredicateData>(),
            DetailGoals = new[]
            {
                new CompiledDetailGoalData
                {
                    GoalKind = 0,
                    NodeId = 0,
                    DependencyIndices = new[] { 0 },
                },
            },
            DetailDependencies = new[]
            {
                new CompiledDetailDependencyData
                {
                    GoalKind = 0,
                    NodeId = 0,
                    Semantics = 1,
                    ChildGoalIndices = new[] { 0 },
                    UnlockGroup = 2,
                },
            },
            TopoOrder = Array.Empty<int>(),
            ItemToQuestIndices = Array.Empty<int[]>(),
            QuestToDependentQuestIndices = Array.Empty<int[]>(),
            ZoneNodeIds = Array.Empty<int>(),
            ZoneAdjacency = Array.Empty<int[]>(),
            GiverBlueprints = Array.Empty<CompiledGiverBlueprintData>(),
            CompletionBlueprints = Array.Empty<CompiledCompletionBlueprintData>(),
            InfeasibleNodeIds = Array.Empty<int>(),
        };

        var guide = new CompiledGuideModel(data);

        var goal = guide.DetailGoals[0];
        Assert.Equal(0, goal.GoalKind);
        Assert.Equal(0, goal.NodeId);
        Assert.Equal(new[] { 0 }, goal.DependencyIndices.ToArray());

        var dependency = guide.DetailDependencies[0];
        Assert.Equal(0, dependency.GoalKind);
        Assert.Equal(0, dependency.NodeId);
        Assert.Equal(1, dependency.Semantics);
        Assert.Equal(new[] { 0 }, dependency.ChildGoalIndices.ToArray());
        Assert.Equal(2, dependency.UnlockGroup);
    }

    [Fact]
    public void CompiledGuideBuilder_generates_detail_dependency_summaries()
    {
        var guide = new CompiledGuideBuilder()
            .AddItem("item:note")
            .AddCharacter("npc:source")
            .AddItemSource("item:note", "npc:source")
            .Build();

        Assert.True(guide.TryGetNodeId("item:note", out int itemNodeId));
        Assert.True(guide.TryGetNodeId("npc:source", out int sourceNodeId));
        var goal = Assert.Single(
            guide.DetailGoals.ToArray(),
            goal => goal.GoalKind == 0 && goal.NodeId == itemNodeId
        );
        var dependencyIndex = Assert.Single(goal.DependencyIndices);
        var dependency = guide.DetailDependencies[dependencyIndex];

        Assert.Equal(0, dependency.GoalKind);
        Assert.Equal(itemNodeId, dependency.NodeId);
        Assert.Equal(0, dependency.Semantics);
        var childGoalIndex = Assert.Single(dependency.ChildGoalIndices);
        var childGoal = guide.DetailGoals[childGoalIndex];
        Assert.Equal(2, childGoal.GoalKind);
        Assert.Equal(sourceNodeId, childGoal.NodeId);
    }

    [Fact]
    public void NodeFlags_bit_values_are_stable()
    {
        Assert.Equal((ushort)1, (ushort)NodeFlags.IsFriendly);
        Assert.Equal((ushort)2, (ushort)NodeFlags.IsVendor);
        Assert.Equal((ushort)4, (ushort)NodeFlags.NightSpawn);
        Assert.Equal((ushort)8, (ushort)NodeFlags.Implicit);
        Assert.Equal((ushort)16, (ushort)NodeFlags.Repeatable);
        Assert.Equal((ushort)32, (ushort)NodeFlags.Disabled);
        Assert.Equal((ushort)64, (ushort)NodeFlags.IsDirectlyPlaced);
        Assert.Equal((ushort)128, (ushort)NodeFlags.IsEnabled);
        Assert.Equal((ushort)256, (ushort)NodeFlags.Invulnerable);
        Assert.Equal((ushort)512, (ushort)NodeFlags.IsRare);
        Assert.Equal((ushort)1024, (ushort)NodeFlags.IsTriggerSpawn);
    }
}
