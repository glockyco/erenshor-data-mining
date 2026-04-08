using System.Collections.Generic;
using System.Text;
using AdventureGuide.CompiledGuide;
using CompiledGuideModel = AdventureGuide.CompiledGuide.CompiledGuide;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class CompiledGuideTypesTests
{
    [Fact]
    public void BinaryFormat_constants_match_expected_values()
    {
        Assert.Equal(0x47434741u, BinaryFormat.Magic);
        Assert.Equal((ushort)1, BinaryFormat.Version);
        Assert.Equal((byte)0, (byte)SectionId.StringTable);
        Assert.Equal((byte)13, (byte)SectionId.Feasibility);
    }

    [Fact]
    public void CompiledGuide_exposes_counts_and_string_lookup()
    {
        byte[] strings = Encoding.UTF8.GetBytes("\0quest:a\0Quest A\0");
        var nodes = new[]
        {
            new NodeRecord(
                keyOffset: 1,
                nodeType: 0,
                displayNameOffset: 9,
                sceneOffset: 0,
                x: float.NaN,
                y: float.NaN,
                z: float.NaN,
                flags: 0,
                level: 0,
                zoneKeyOffset: 0,
                dbNameOffset: 0),
        };

        var guide = new CompiledGuideModel(
            strings,
            nodes,
            new Dictionary<string, int> { ["quest:a"] = 0 },
            System.Array.Empty<EdgeRecord>(),
            new[] { 0, 0 },
            System.Array.Empty<int>(),
            new[] { 0, 0 },
            System.Array.Empty<int>(),
            new[] { 0 },
            new[] { System.Array.Empty<int>() },
            new[] { System.Array.Empty<ItemReq>() },
            System.Array.Empty<StepEntry>(),
            new[] { 0 },
            new[] { System.Array.Empty<int>() },
            new[] { System.Array.Empty<int>() },
            new[] { System.Array.Empty<int>() },
            new byte[] { 0 },
            System.Array.Empty<int>(),
            System.Array.Empty<SourceSiteEntry[]>(),
            new Dictionary<int, UnlockPredicateEntry>(),
            new[] { 0 },
            new[] { 0 },
            System.Array.Empty<int>(),
            new[] { 0 },
            System.Array.Empty<int>(),
            System.Array.Empty<int>(),
            new[] { 0 },
            System.Array.Empty<int>(),
            System.Array.Empty<QuestGiverEntry>(),
            System.Array.Empty<QuestCompletion>(),
            new[] { false });

        Assert.Equal(1, guide.NodeCount);
        Assert.Equal(0, guide.EdgeCount);
        Assert.Equal(1, guide.QuestCount);
        Assert.Equal(0, guide.ItemCount);
        Assert.Equal("quest:a", guide.GetNodeKey(0));
        Assert.Equal("Quest A", guide.GetDisplayName(0));
        Assert.True(guide.TryGetNodeId("quest:a", out int id));
        Assert.Equal(0, id);
    }
}
