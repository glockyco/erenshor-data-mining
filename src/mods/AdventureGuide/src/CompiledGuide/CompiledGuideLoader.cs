using BepInEx.Logging;
using System.Reflection;
using System.Text;

namespace AdventureGuide.CompiledGuide;

public static class CompiledGuideLoader
{
    private const string ResourceName = "AdventureGuide.guide.bin";

    public static CompiledGuide Load(ManualLogSource log)
    {
        var assembly = Assembly.GetExecutingAssembly();
        using Stream stream = assembly.GetManifestResourceStream(ResourceName)
            ?? throw new InvalidOperationException($"Embedded resource '{ResourceName}' not found.");

        byte[] bytes = new byte[stream.Length];
        _ = stream.Read(bytes, 0, bytes.Length);
        return ParseCore(bytes, message => log.LogInfo(message));
    }

    internal static CompiledGuide Parse(byte[] data) => ParseCore(data, null);

    private static CompiledGuide ParseCore(byte[] data, Action<string>? logInfo)
    {
        using var reader = new BinaryReader(new MemoryStream(data));

        uint magic = reader.ReadUInt32();
        if (magic != BinaryFormat.Magic)
        {
            throw new InvalidDataException($"Expected magic 0x{BinaryFormat.Magic:X8}, got 0x{magic:X8}.");
        }

        ushort version = reader.ReadUInt16();
        if (version != BinaryFormat.Version)
        {
            throw new InvalidDataException($"Expected version {BinaryFormat.Version}, got {version}.");
        }

        int nodeCount = reader.ReadUInt16();
        int edgeCount = (int)reader.ReadUInt32();
        int questCount = reader.ReadUInt16();
        int itemCount = reader.ReadUInt16();
        int sectionCount = reader.ReadByte();

        var sections = new Dictionary<SectionId, (int Offset, int Size)>();
        for (int index = 0; index < sectionCount; index++)
        {
            sections[(SectionId)reader.ReadByte()] = ((int)reader.ReadUInt32(), (int)reader.ReadUInt32());
        }

        BinaryReader Section(SectionId id)
        {
            (int offset, int size) = sections[id];
            return new BinaryReader(new MemoryStream(data, offset, size, writable: false));
        }

        byte[] stringTable = ReadSectionBytes(data, sections[SectionId.StringTable]);
        string ReadString(uint offset)
        {
            if (offset == 0) return string.Empty;
            int end = (int)offset;
            while (end < stringTable.Length && stringTable[end] != 0)
            {
                end++;
            }
            return Encoding.UTF8.GetString(stringTable, (int)offset, end - (int)offset);
        }

        NodeRecord[] nodes = new NodeRecord[nodeCount];
        var keyToId = new Dictionary<string, int>(nodeCount, StringComparer.Ordinal);
        using (BinaryReader s = Section(SectionId.NodeTable))
        {
            for (int nodeId = 0; nodeId < nodeCount; nodeId++)
            {
                nodes[nodeId] = new NodeRecord(
                    s.ReadUInt32(),
                    s.ReadByte(),
                    s.ReadUInt32(),
                    s.ReadUInt32(),
                    s.ReadSingle(),
                    s.ReadSingle(),
                    s.ReadSingle(),
                    s.ReadUInt16(),
                    s.ReadUInt16(),
                    s.ReadUInt32(),
                    s.ReadUInt32());
                keyToId[ReadString(nodes[nodeId].KeyOffset)] = nodeId;
            }
        }

        EdgeRecord[] edges = new EdgeRecord[edgeCount];
        using (BinaryReader s = Section(SectionId.EdgeTable))
        {
            for (int edgeId = 0; edgeId < edgeCount; edgeId++)
            {
                edges[edgeId] = new EdgeRecord(
                    s.ReadUInt16(),
                    s.ReadUInt16(),
                    s.ReadByte(),
                    s.ReadByte(),
                    s.ReadUInt32(),
                    s.ReadByte(),
                    s.ReadUInt16(),
                    s.ReadUInt32(),
                    s.ReadUInt16());
            }
        }

        (int[] Offsets, int[] Values) ReadCsr(BinaryReader s, int rowCount)
        {
            int[] offsets = new int[rowCount + 1];
            for (int i = 0; i <= rowCount; i++)
            {
                offsets[i] = (int)s.ReadUInt32();
            }

            int[] values = new int[offsets[rowCount]];
            for (int i = 0; i < values.Length; i++)
            {
                values[i] = (int)s.ReadUInt32();
            }

            return (offsets, values);
        }

        int[] fwdOff;
        int[] fwdVal;
        using (BinaryReader s = Section(SectionId.ForwardAdjacency))
        {
            (fwdOff, fwdVal) = ReadCsr(s, nodeCount);
        }

        int[] revOff;
        int[] revVal;
        using (BinaryReader s = Section(SectionId.ReverseAdjacency))
        {
            (revOff, revVal) = ReadCsr(s, nodeCount);
        }

        int[] questNodeIds = new int[questCount];
        int[][] prereqIds = new int[questCount][];
        ItemReq[][] requiredItems = new ItemReq[questCount][];
        var steps = new List<StepEntry>();
        int[] stepOff = new int[questCount];
        int[][] giverIds = new int[questCount][];
        int[][] completerIds = new int[questCount][];
        int[][] chainsToIds = new int[questCount][];
        byte[] questFlags = new byte[questCount];
        using (BinaryReader s = Section(SectionId.QuestSpecs))
        {
            for (int qi = 0; qi < questCount; qi++)
            {
                questNodeIds[qi] = s.ReadUInt16();
            }

            for (int qi = 0; qi < questCount; qi++)
            {
                prereqIds[qi] = ReadIntArrayU16(s, s.ReadByte());
                requiredItems[qi] = ReadItemReqs(s, s.ReadByte());

                int stepCount = s.ReadByte();
                stepOff[qi] = steps.Count;
                for (int index = 0; index < stepCount; index++)
                {
                    steps.Add(new StepEntry(s.ReadByte(), s.ReadUInt16(), s.ReadByte()));
                }

                giverIds[qi] = ReadIntArrayU16(s, s.ReadByte());
                completerIds[qi] = ReadIntArrayU16(s, s.ReadByte());
                chainsToIds[qi] = ReadIntArrayU16(s, s.ReadByte());
                questFlags[qi] = s.ReadByte();
            }
        }

        int[] itemNodeIds = new int[itemCount];
        SourceSiteEntry[][] itemSources = new SourceSiteEntry[itemCount][];
        using (BinaryReader s = Section(SectionId.ItemSourceIndex))
        {
            for (int ii = 0; ii < itemCount; ii++)
            {
                itemNodeIds[ii] = s.ReadUInt16();
            }

            for (int ii = 0; ii < itemCount; ii++)
            {
                _ = s.ReadUInt16(); // item index, redundant but preserved in format
                int sourceCount = s.ReadUInt16();
                var sources = new SourceSiteEntry[sourceCount];
                for (int index = 0; index < sourceCount; index++)
                {
                    int sourceId = s.ReadUInt16();
                    byte sourceType = s.ReadByte();
                    byte edgeType = s.ReadByte();
                    int directItemId = s.ReadUInt16();
                    uint sceneOffset = s.ReadUInt32();
                    int posCount = s.ReadByte();
                    var positions = new SpawnPositionEntry[posCount];
                    for (int pos = 0; pos < posCount; pos++)
                    {
                        positions[pos] = new SpawnPositionEntry(
                            s.ReadUInt16(),
                            s.ReadSingle(),
                            s.ReadSingle(),
                            s.ReadSingle());
                    }
                    sources[index] = new SourceSiteEntry(
                        sourceId,
                        sourceType,
                        edgeType,
                        directItemId,
                        sceneOffset == 0 ? null : ReadString(sceneOffset),
                        positions);
                }
                itemSources[ii] = sources;
            }
        }

        var unlocks = new Dictionary<int, UnlockPredicateEntry>();
        using (BinaryReader s = Section(SectionId.UnlockPredicates))
        {
            int predicateCount = s.ReadUInt16();
            for (int i = 0; i < predicateCount; i++)
            {
                int targetId = s.ReadUInt16();
                int conditionCount = s.ReadByte();
                var conditions = new UnlockConditionEntry[conditionCount];
                for (int conditionIndex = 0; conditionIndex < conditionCount; conditionIndex++)
                {
                    conditions[conditionIndex] = new UnlockConditionEntry(s.ReadUInt16(), s.ReadByte(), s.ReadByte());
                }
                unlocks[targetId] = new UnlockPredicateEntry(conditions, s.ReadByte(), s.ReadByte());
            }
        }

        int[] topoOrder = new int[questCount];
        using (BinaryReader s = Section(SectionId.TopologicalOrder))
        {
            for (int qi = 0; qi < questCount; qi++)
            {
                topoOrder[qi] = s.ReadUInt16();
            }
        }

        int[] i2qOff;
        int[] i2qVal;
        int[] q2qOff;
        int[] q2qVal;
        using (BinaryReader s = Section(SectionId.ReverseDeps))
        {
            (i2qOff, i2qVal) = ReadCsr(s, itemCount);
            (q2qOff, q2qVal) = ReadCsr(s, questCount);
        }

        int[] zoneNodeIds;
        int[] zoneAdjOff;
        int[] zoneAdjVal;
        using (BinaryReader s = Section(SectionId.ZoneConnectivity))
        {
            int zoneCount = s.ReadUInt16();
            zoneNodeIds = new int[zoneCount];
            for (int zi = 0; zi < zoneCount; zi++)
            {
                zoneNodeIds[zi] = s.ReadUInt16();
            }
            (zoneAdjOff, zoneAdjVal) = ReadCsr(s, zoneCount);
        }

        QuestGiverEntry[] giverBlueprints;
        using (BinaryReader s = Section(SectionId.QuestGiverBlueprints))
        {
            int count = s.ReadUInt16();
            giverBlueprints = new QuestGiverEntry[count];
            for (int i = 0; i < count; i++)
            {
                int questId = s.ReadUInt16();
                int characterId = s.ReadUInt16();
                int positionId = s.ReadUInt16();
                byte interactionType = s.ReadByte();
                string? keyword = ReadNullableString(ReadString, s.ReadUInt32());
                string[] requiredQuestDbNames = ReadStringArray(s, ReadString);
                giverBlueprints[i] = new QuestGiverEntry(
                    questId,
                    characterId,
                    positionId,
                    interactionType,
                    keyword,
                    requiredQuestDbNames);
            }
        }

        QuestCompletion[] completionBlueprints;
        using (BinaryReader s = Section(SectionId.QuestCompletionBlueprints))
        {
            int count = s.ReadUInt16();
            completionBlueprints = new QuestCompletion[count];
            for (int i = 0; i < count; i++)
            {
                completionBlueprints[i] = new QuestCompletion(
                    s.ReadUInt16(),
                    s.ReadUInt16(),
                    s.ReadUInt16(),
                    s.ReadByte(),
                    ReadNullableString(ReadString, s.ReadUInt32()));
            }
        }

        bool[] infeasible = new bool[nodeCount];
        using (BinaryReader s = Section(SectionId.Feasibility))
        {
            byte[] bits = s.ReadBytes((int)s.BaseStream.Length);
            for (int nodeId = 0; nodeId < nodeCount; nodeId++)
            {
                int byteIndex = nodeId / 8;
                int bitIndex = nodeId % 8;
                if (byteIndex < bits.Length)
                {
                    infeasible[nodeId] = (bits[byteIndex] & (1 << bitIndex)) != 0;
                }
            }
        }

        logInfo?.Invoke($"Loaded compiled guide: {nodeCount} nodes, {edgeCount} edges, {questCount} quests, {itemCount} items");

        return new CompiledGuide(
            stringTable,
            nodes,
            keyToId,
            edges,
            fwdOff,
            fwdVal,
            revOff,
            revVal,
            questNodeIds,
            prereqIds,
            requiredItems,
            steps.ToArray(),
            stepOff,
            giverIds,
            completerIds,
            chainsToIds,
            questFlags,
            itemNodeIds,
            itemSources,
            unlocks,
            topoOrder,
            i2qOff,
            i2qVal,
            q2qOff,
            q2qVal,
            zoneNodeIds,
            zoneAdjOff,
            zoneAdjVal,
            giverBlueprints,
            completionBlueprints,
            infeasible);
    }

    private static byte[] ReadSectionBytes(byte[] allBytes, (int Offset, int Size) section)
    {
        byte[] bytes = new byte[section.Size];
        Array.Copy(allBytes, section.Offset, bytes, 0, section.Size);
        return bytes;
    }

    private static int[] ReadIntArrayU16(BinaryReader reader, int count)
    {
        var values = new int[count];
        for (int i = 0; i < count; i++)
        {
            values[i] = reader.ReadUInt16();
        }
        return values;
    }

    private static ItemReq[] ReadItemReqs(BinaryReader reader, int count)
    {
        var values = new ItemReq[count];
        for (int i = 0; i < count; i++)
        {
            values[i] = new ItemReq(reader.ReadUInt16(), reader.ReadUInt16(), reader.ReadByte());
        }
        return values;
    }

    private static string[] ReadStringArray(BinaryReader reader, Func<uint, string> readString)
    {
        int count = reader.ReadByte();
        var values = new string[count];
        for (int i = 0; i < count; i++)
        {
            values[i] = readString(reader.ReadUInt32());
        }
        return values;
    }

    private static string? ReadNullableString(Func<uint, string> readString, uint offset)
    {
        return offset == 0 ? null : readString(offset);
    }
}
