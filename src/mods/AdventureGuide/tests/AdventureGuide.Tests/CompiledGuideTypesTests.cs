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
    public void GetQuestsTouchingSource_IncludesRequiredItemSourceChains()
    {
        var guide = new CompiledGuideBuilder()
            .AddItem("item:coal")
            .AddMiningNode("mine:azure", scene: "Azure", x: 1f, y: 2f, z: 3f)
            .AddItemSource(
                "item:coal",
                "mine:azure",
                edgeType: (byte)EdgeType.YieldsItem,
                sourceType: (byte)NodeType.MiningNode
            )
            .AddQuest("quest:root", dbName: "ROOT", requiredItems: new[] { ("item:coal", 1) })
            .Build();

        var quests = guide.GetQuestsTouchingSource("mine:azure");

        Assert.Contains("quest:root", quests);
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
