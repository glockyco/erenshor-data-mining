using System.Collections.Generic;
using System.IO;
using System.Text;
using AdventureGuide.CompiledGuide;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class CompiledGuideLoaderTests
{
    [Fact]
    public void Builder_creates_dense_quest_lookup()
    {
        var guide = new CompiledGuideBuilder()
            .AddQuest("quest:a", dbName: "QUESTA")
            .AddQuest("quest:b", dbName: "QUESTB", prereqs: new[] { "quest:a" })
            .Build();

        Assert.Equal(2, guide.NodeCount);
        Assert.Equal(2, guide.QuestCount);
        Assert.True(guide.TryGetNodeId("quest:a", out int questA));
        Assert.True(guide.TryGetNodeId("quest:b", out int questB));
        Assert.Equal("quest:a", guide.GetNodeKey(questA));
        Assert.Equal("quest:b", guide.GetNodeKey(questB));
        Assert.Equal(questA, guide.PrereqQuestIds(1)[0]);
    }

    [Fact]
    public void Parse_reads_minimal_binary()
    {
        byte[] binary = BuildMinimalBinary();

        var guide = CompiledGuideLoader.Parse(binary);

        Assert.Equal(1, guide.NodeCount);
        Assert.Equal(0, guide.EdgeCount);
        Assert.Equal(1, guide.QuestCount);
        Assert.True(guide.TryGetNodeId("quest:a", out int nodeId));
        Assert.Equal("Quest A", guide.GetDisplayName(nodeId));
        Assert.Equal(0, guide.TopologicalOrder[0]);
    }

    [Fact]
    public void Builder_creates_giver_blueprints_for_compiled_marker_flow()
    {
        var guide = new CompiledGuideBuilder()
            .AddCharacter("char:giver", scene: "Town", x: 1f, y: 2f, z: 3f)
            .AddQuest("quest:pre", dbName: "PRE")
            .AddQuest("quest:root", dbName: "ROOT", prereqs: new[] { "quest:pre" }, givers: new[] { "char:giver" })
            .Build();

        Assert.Equal(1, guide.GiverBlueprints.Length);
        Assert.True(guide.TryGetNodeId("quest:root", out int questId));
        Assert.True(guide.TryGetNodeId("char:giver", out int giverId));

        QuestGiverEntry blueprint = guide.GiverBlueprints[0];
        Assert.Equal(questId, blueprint.QuestId);
        Assert.Equal(giverId, blueprint.CharacterId);
        Assert.Equal(giverId, blueprint.PositionId);
        Assert.Equal(0, blueprint.InteractionType);
        Assert.Null(blueprint.Keyword);
        Assert.Equal(new[] { "PRE" }, blueprint.RequiredQuestDbNames);
    }

    [Fact]
    public void Builder_creates_completion_blueprints_for_compiled_marker_flow()
    {
        var guide = new CompiledGuideBuilder()
            .AddCharacter("char:turnin", scene: "Town", x: 4f, y: 5f, z: 6f)
            .AddQuest("quest:root", dbName: "ROOT", completers: new[] { "char:turnin" })
            .Build();

        Assert.Equal(1, guide.CompletionBlueprints.Length);
        Assert.True(guide.TryGetNodeId("quest:root", out int questId));
        Assert.True(guide.TryGetNodeId("char:turnin", out int turnInId));

        QuestCompletion blueprint = guide.CompletionBlueprints[0];
        Assert.Equal(questId, blueprint.QuestId);
        Assert.Equal(turnInId, blueprint.CharacterId);
        Assert.Equal(turnInId, blueprint.PositionId);
        Assert.Equal(0, blueprint.InteractionType);
        Assert.Null(blueprint.Keyword);
    }


    [Fact]
    public void Parse_reads_blueprint_metadata()
    {
        byte[] binary = BuildBlueprintBinary();

        var guide = CompiledGuideLoader.Parse(binary);

        Assert.True(guide.TryGetNodeId("quest:root", out int questId));
        Assert.True(guide.TryGetNodeId("char:npc", out int npcId));
        Assert.Equal(1, guide.GiverBlueprints.Length);
        Assert.Equal(1, guide.CompletionBlueprints.Length);

        QuestGiverEntry giver = guide.GiverBlueprints[0];
        Assert.Equal(questId, giver.QuestId);
        Assert.Equal(npcId, giver.CharacterId);
        Assert.Equal(npcId, giver.PositionId);
        Assert.Equal(1, giver.InteractionType);
        Assert.Equal("hail", giver.Keyword);
        Assert.Equal(new[] { "PRE", "CHAIN" }, giver.RequiredQuestDbNames);

        QuestCompletion completion = guide.CompletionBlueprints[0];
        Assert.Equal(questId, completion.QuestId);
        Assert.Equal(npcId, completion.CharacterId);
        Assert.Equal(npcId, completion.PositionId);
        Assert.Equal(1, completion.InteractionType);
        Assert.Equal("done", completion.Keyword);
    }

    private static byte[] BuildBlueprintBinary()
    {
        var strings = new List<byte> { 0 };
        var offsets = new Dictionary<string, uint>(StringComparer.Ordinal)
        {
            [string.Empty] = 0,
        };

        uint Intern(string value)
        {
            if (offsets.TryGetValue(value, out uint offset))
                return offset;

            offset = (uint)strings.Count;
            offsets[value] = offset;
            strings.AddRange(Encoding.UTF8.GetBytes(value));
            strings.Add(0);
            return offset;
        }

        uint questKey = Intern("quest:root");
        uint questDisplay = Intern("Quest Root");
        uint questDbName = Intern("ROOT");
        uint npcKey = Intern("char:npc");
        uint npcDisplay = Intern("NPC");
        uint townScene = Intern("Town");
        uint hailKeyword = Intern("hail");
        uint doneKeyword = Intern("done");
        uint preReq = Intern("PRE");
        uint chainReq = Intern("CHAIN");

        byte[] nodeSection;
        using (var ms = new MemoryStream())
        using (var bw = new BinaryWriter(ms))
        {
            bw.Write(questKey);
            bw.Write((byte)0);
            bw.Write(questDisplay);
            bw.Write((uint)0);
            bw.Write(float.NaN);
            bw.Write(float.NaN);
            bw.Write(float.NaN);
            bw.Write((ushort)0);
            bw.Write((ushort)0);
            bw.Write((uint)0);
            bw.Write(questDbName);

            bw.Write(npcKey);
            bw.Write((byte)2);
            bw.Write(npcDisplay);
            bw.Write(townScene);
            bw.Write(10f);
            bw.Write(20f);
            bw.Write(30f);
            bw.Write((ushort)0);
            bw.Write((ushort)0);
            bw.Write((uint)0);
            bw.Write((uint)0);
            nodeSection = ms.ToArray();
        }

        byte[] emptyAdj = BuildCsr(2, System.Array.Empty<int>());
        byte[] questSpecs;
        using (var ms = new MemoryStream())
        using (var bw = new BinaryWriter(ms))
        {
            bw.Write((ushort)0);
            bw.Write((byte)0);
            bw.Write((byte)0);
            bw.Write((byte)0);
            bw.Write((byte)0);
            bw.Write((byte)0);
            bw.Write((byte)0);
            bw.Write((byte)0);
            questSpecs = ms.ToArray();
        }

        byte[] unlocks;
        using (var ms = new MemoryStream())
        using (var bw = new BinaryWriter(ms))
        {
            bw.Write((ushort)0);
            unlocks = ms.ToArray();
        }

        byte[] topo;
        using (var ms = new MemoryStream())
        using (var bw = new BinaryWriter(ms))
        {
            bw.Write((ushort)0);
            topo = ms.ToArray();
        }

        byte[] reverseDeps = BuildCsr(0, System.Array.Empty<int>());
        reverseDeps = Combine(reverseDeps, BuildCsr(1, System.Array.Empty<int>()));

        byte[] zones;
        using (var ms = new MemoryStream())
        using (var bw = new BinaryWriter(ms))
        {
            bw.Write((ushort)0);
            bw.Write(BuildCsr(0, System.Array.Empty<int>()));
            zones = ms.ToArray();
        }

        byte[] giverBps;
        using (var ms = new MemoryStream())
        using (var bw = new BinaryWriter(ms))
        {
            bw.Write((ushort)1);
            bw.Write((ushort)0);
            bw.Write((ushort)1);
            bw.Write((ushort)1);
            bw.Write((byte)1);
            bw.Write(hailKeyword);
            bw.Write((byte)2);
            bw.Write(preReq);
            bw.Write(chainReq);
            giverBps = ms.ToArray();
        }

        byte[] completionBps;
        using (var ms = new MemoryStream())
        using (var bw = new BinaryWriter(ms))
        {
            bw.Write((ushort)1);
            bw.Write((ushort)0);
            bw.Write((ushort)1);
            bw.Write((ushort)1);
            bw.Write((byte)1);
            bw.Write(doneKeyword);
            completionBps = ms.ToArray();
        }

        var sections = new Dictionary<SectionId, byte[]>
        {
            [SectionId.StringTable] = strings.ToArray(),
            [SectionId.NodeTable] = nodeSection,
            [SectionId.EdgeTable] = System.Array.Empty<byte>(),
            [SectionId.ForwardAdjacency] = emptyAdj,
            [SectionId.ReverseAdjacency] = emptyAdj,
            [SectionId.QuestSpecs] = questSpecs,
            [SectionId.ItemSourceIndex] = System.Array.Empty<byte>(),
            [SectionId.UnlockPredicates] = unlocks,
            [SectionId.TopologicalOrder] = topo,
            [SectionId.ReverseDeps] = reverseDeps,
            [SectionId.ZoneConnectivity] = zones,
            [SectionId.QuestGiverBlueprints] = giverBps,
            [SectionId.QuestCompletionBlueprints] = completionBps,
            [SectionId.Feasibility] = new byte[] { 0 },
        };

        const int fixedHeaderSize = 17;
        int sectionCount = System.Enum.GetValues<SectionId>().Length;
        int headerSize = fixedHeaderSize + sectionCount * 9;
        int cursor = headerSize;
        var sectionOffsets = new Dictionary<SectionId, int>();
        foreach (SectionId section in System.Enum.GetValues<SectionId>())
        {
            sectionOffsets[section] = cursor;
            cursor += sections[section].Length;
        }

        using var outStream = new MemoryStream();
        using var writer = new BinaryWriter(outStream);
        writer.Write(BinaryFormat.Magic);
        writer.Write(BinaryFormat.Version);
        writer.Write((ushort)2);
        writer.Write((uint)0);
        writer.Write((ushort)1);
        writer.Write((ushort)0);
        writer.Write((byte)sectionCount);
        foreach (SectionId section in System.Enum.GetValues<SectionId>())
        {
            writer.Write((byte)section);
            writer.Write(sectionOffsets[section]);
            writer.Write(sections[section].Length);
        }

        foreach (SectionId section in System.Enum.GetValues<SectionId>())
            writer.Write(sections[section]);

        return outStream.ToArray();
    }


    private static byte[] BuildMinimalBinary()
    {
        // String table: \0quest:a\0Quest A\0
        byte[] strings = Encoding.UTF8.GetBytes("\0quest:a\0Quest A\0");

        byte[] nodeSection;
        using (var ms = new MemoryStream())
        using (var bw = new BinaryWriter(ms))
        {
            bw.Write((uint)1); // key offset
            bw.Write((byte)0); // node type
            bw.Write((uint)9); // display name offset
            bw.Write((uint)0); // scene offset
            bw.Write(float.NaN);
            bw.Write(float.NaN);
            bw.Write(float.NaN);
            bw.Write((ushort)0);
            bw.Write((ushort)0);
            bw.Write((uint)0);
            bw.Write((uint)0);
            nodeSection = ms.ToArray();
        }

        byte[] emptyAdj = BuildCsr(1, System.Array.Empty<int>());
        byte[] questSpecs;
        using (var ms = new MemoryStream())
        using (var bw = new BinaryWriter(ms))
        {
            bw.Write((ushort)0); // quest node id map entry
            bw.Write((byte)0);   // prereq count
            bw.Write((byte)0);   // item count
            bw.Write((byte)0);   // step count
            bw.Write((byte)0);   // giver count
            bw.Write((byte)0);   // completer count
            bw.Write((byte)0);   // chains_to count
            bw.Write((byte)0);   // flags
            questSpecs = ms.ToArray();
        }

        byte[] itemSources = System.Array.Empty<byte>();
        byte[] unlocks;
        using (var ms = new MemoryStream())
        using (var bw = new BinaryWriter(ms))
        {
            bw.Write((ushort)0);
            unlocks = ms.ToArray();
        }

        byte[] topo;
        using (var ms = new MemoryStream())
        using (var bw = new BinaryWriter(ms))
        {
            bw.Write((ushort)0);
            topo = ms.ToArray();
        }

        byte[] reverseDeps = BuildCsr(0, System.Array.Empty<int>()); // item rows
        reverseDeps = Combine(reverseDeps, BuildCsr(1, System.Array.Empty<int>()));

        byte[] zones;
        using (var ms = new MemoryStream())
        using (var bw = new BinaryWriter(ms))
        {
            bw.Write((ushort)0);
            bw.Write(BuildCsr(0, System.Array.Empty<int>()));
            zones = ms.ToArray();
        }

        byte[] giverBps = new byte[] { 0, 0 };
        byte[] completionBps = new byte[] { 0, 0 };
        byte[] feasibility = new byte[] { 0 };

        var sections = new Dictionary<SectionId, byte[]>
        {
            [SectionId.StringTable] = strings,
            [SectionId.NodeTable] = nodeSection,
            [SectionId.EdgeTable] = System.Array.Empty<byte>(),
            [SectionId.ForwardAdjacency] = emptyAdj,
            [SectionId.ReverseAdjacency] = emptyAdj,
            [SectionId.QuestSpecs] = questSpecs,
            [SectionId.ItemSourceIndex] = itemSources,
            [SectionId.UnlockPredicates] = unlocks,
            [SectionId.TopologicalOrder] = topo,
            [SectionId.ReverseDeps] = reverseDeps,
            [SectionId.ZoneConnectivity] = zones,
            [SectionId.QuestGiverBlueprints] = giverBps,
            [SectionId.QuestCompletionBlueprints] = completionBps,
            [SectionId.Feasibility] = feasibility,
        };

        const int fixedHeaderSize = 17;
        int sectionCount = System.Enum.GetValues<SectionId>().Length;
        int headerSize = fixedHeaderSize + sectionCount * 9;
        int cursor = headerSize;
        var offsets = new Dictionary<SectionId, int>();
        foreach (SectionId section in System.Enum.GetValues<SectionId>())
        {
            offsets[section] = cursor;
            cursor += sections[section].Length;
        }

        using var outStream = new MemoryStream();
        using var writer = new BinaryWriter(outStream);
        writer.Write(BinaryFormat.Magic);
        writer.Write(BinaryFormat.Version);
        writer.Write((ushort)1); // node count
        writer.Write((uint)0);   // edge count
        writer.Write((ushort)1); // quest count
        writer.Write((ushort)0); // item count
        writer.Write((byte)sectionCount);
        foreach (SectionId section in System.Enum.GetValues<SectionId>())
        {
            writer.Write((byte)section);
            writer.Write(offsets[section]);
            writer.Write(sections[section].Length);
        }
        foreach (SectionId section in System.Enum.GetValues<SectionId>())
        {
            writer.Write(sections[section]);
        }

        return outStream.ToArray();
    }

    private static byte[] BuildCsr(int rowCount, int[] values)
    {
        using var ms = new MemoryStream();
        using var bw = new BinaryWriter(ms);
        for (int i = 0; i <= rowCount; i++)
        {
            bw.Write((uint)(i == rowCount ? values.Length : 0));
        }
        foreach (int value in values)
        {
            bw.Write((uint)value);
        }
        return ms.ToArray();
    }

    private static byte[] Combine(byte[] first, byte[] second)
    {
        byte[] combined = new byte[first.Length + second.Length];
        first.CopyTo(combined, 0);
        second.CopyTo(combined, first.Length);
        return combined;
    }
}
