using System.Text;
using AdventureGuide.CompiledGuide;
using CompiledGuideModel = AdventureGuide.CompiledGuide.CompiledGuide;

namespace AdventureGuide.Tests.Helpers;

/// <summary>
/// Minimal fluent builder for CompiledGuide tests.
///
/// This bypasses binary serialization so runtime tests can exercise the new
/// guide model directly. It intentionally starts small and can be expanded as
/// later phases need richer fixtures.
/// </summary>
public sealed class CompiledGuideBuilder
{
    private sealed record QuestDef(
        string Key,
        string? DbName,
        string[] Prereqs,
        bool Implicit,
        string[] Givers,
        string[] Completers,
        string[] ChainsTo,
        (string ItemKey, int Quantity)[] RequiredItems);

    private sealed record ItemDef(string Key);
    private sealed record CharacterDef(string Key, string? Scene, float X, float Y, float Z);

    private sealed record ItemSourceDef(string ItemKey, string SourceKey);
    private sealed record UnlockDef(string TargetKey, string SourceKey, byte Group, byte CheckType);

    private readonly List<QuestDef> _quests = new();
    private readonly List<ItemDef> _items = new();
    private readonly List<CharacterDef> _characters = new();

    private readonly List<ItemSourceDef> _itemSources = new();
    private readonly List<UnlockDef> _unlockDefs = new();

    public CompiledGuideBuilder AddQuest(
        string key,
        string? dbName = null,
        string[]? prereqs = null,
        bool implicit_ = false,
        string[]? givers = null,
        string[]? completers = null,
        string[]? chainsTo = null,
        (string ItemKey, int Quantity)[]? requiredItems = null)
    {
        _quests.Add(new QuestDef(
            key,
            dbName,
            prereqs ?? Array.Empty<string>(),
            implicit_,
            givers ?? Array.Empty<string>(),
            completers ?? Array.Empty<string>(),
            chainsTo ?? Array.Empty<string>(),
            requiredItems ?? Array.Empty<(string, int)>()));
        return this;
    }

    public CompiledGuideBuilder AddItem(string key)
    {
        _items.Add(new ItemDef(key));
        return this;
    }

    public CompiledGuideBuilder AddCharacter(
        string key,
        string? scene = null,
        float x = float.NaN,
        float y = float.NaN,
        float z = float.NaN)
    {
        _characters.Add(new CharacterDef(key, scene, x, y, z));
        return this;
    }

    public CompiledGuideBuilder AddItemSource(string itemKey, string sourceKey)
    {
        _itemSources.Add(new ItemSourceDef(itemKey, sourceKey));
        return this;
    }

    public CompiledGuideBuilder AddUnlockPredicate(
        string targetKey,
        string sourceKey,
        byte group = 0,
        byte checkType = 0)
    {
        _unlockDefs.Add(new UnlockDef(targetKey, sourceKey, group, checkType));
        return this;
    }

    public CompiledGuideModel Build()
    {
        var allKeys = new SortedSet<string>(StringComparer.Ordinal);
        foreach (QuestDef quest in _quests)
        {
            allKeys.Add(quest.Key);
            foreach (string prereq in quest.Prereqs) allKeys.Add(prereq);
            foreach (string giver in quest.Givers) allKeys.Add(giver);
            foreach (string completer in quest.Completers) allKeys.Add(completer);
            foreach (string chained in quest.ChainsTo) allKeys.Add(chained);
            foreach ((string itemKey, _) in quest.RequiredItems) allKeys.Add(itemKey);
        }
        foreach (ItemDef item in _items) allKeys.Add(item.Key);
        foreach (CharacterDef character in _characters) allKeys.Add(character.Key);
        foreach (ItemSourceDef source in _itemSources)
        {
            allKeys.Add(source.ItemKey);
            allKeys.Add(source.SourceKey);
        }
        foreach (UnlockDef unlock in _unlockDefs)
        {
            allKeys.Add(unlock.TargetKey);
            allKeys.Add(unlock.SourceKey);
        }

        var keyToId = new Dictionary<string, int>(StringComparer.Ordinal);
        int nodeId = 0;
        foreach (string key in allKeys)
        {
            keyToId[key] = nodeId++;
        }

        var strings = new List<byte> { 0 };
        var offsets = new Dictionary<string, uint>(StringComparer.Ordinal) { [string.Empty] = 0 };

        uint Intern(string? value)
        {
            if (string.IsNullOrEmpty(value)) return 0;
            if (offsets.TryGetValue(value, out uint existing)) return existing;
            uint offset = (uint)strings.Count;
            offsets[value] = offset;
            strings.AddRange(Encoding.UTF8.GetBytes(value));
            strings.Add(0);
            return offset;
        }

        var questByKey = _quests.ToDictionary(q => q.Key, StringComparer.Ordinal);
        var itemKeys = _items.Select(i => i.Key).OrderBy(k => k, StringComparer.Ordinal).ToArray();
        var questKeys = _quests.Select(q => q.Key).OrderBy(k => k, StringComparer.Ordinal).ToArray();
        var charByKey = _characters.ToDictionary(c => c.Key, StringComparer.Ordinal);

        NodeRecord BuildNode(string key)
        {
            if (questByKey.TryGetValue(key, out QuestDef? quest))
            {
                ushort flags = quest.Implicit ? (ushort)NodeFlags.Implicit : (ushort)0;
                return new NodeRecord(Intern(key), 0, Intern(key), 0, float.NaN, float.NaN, float.NaN, flags, 0, 0, Intern(quest.DbName));
            }

            if (itemKeys.Contains(key, StringComparer.Ordinal))
            {
                return new NodeRecord(Intern(key), 1, Intern(key), 0, float.NaN, float.NaN, float.NaN, 0, 0, 0, 0);
            }

            if (charByKey.TryGetValue(key, out CharacterDef? character))
            {
                return new NodeRecord(Intern(key), 2, Intern(key), Intern(character.Scene), character.X, character.Y, character.Z, 0, 0, 0, 0);
            }

            return new NodeRecord(Intern(key), 255, Intern(key), 0, float.NaN, float.NaN, float.NaN, 0, 0, 0, 0);
        }

        var nodes = new NodeRecord[keyToId.Count];
        foreach ((string key, int id) in keyToId)
        {
            nodes[id] = BuildNode(key);
        }

        int[] questNodeIds = questKeys.Select(key => keyToId[key]).ToArray();
        int[] itemNodeIds = itemKeys.Select(key => keyToId[key]).ToArray();
        var questIndexByNodeId = questNodeIds.Select((id, index) => (id, index)).ToDictionary(p => p.id, p => p.index);

        var prereqs = new int[questNodeIds.Length][];
        var requiredItems = new ItemReq[questNodeIds.Length][];
        var giverIds = new int[questNodeIds.Length][];
        var completerIds = new int[questNodeIds.Length][];
        var chainsToIds = new int[questNodeIds.Length][];
        var questFlags = new byte[questNodeIds.Length];
        var stepOff = new int[questNodeIds.Length];

        for (int questIndex = 0; questIndex < questKeys.Length; questIndex++)
        {
            QuestDef quest = questByKey[questKeys[questIndex]];
            prereqs[questIndex] = quest.Prereqs.Select(prereq => keyToId[prereq]).ToArray();
            requiredItems[questIndex] = quest.RequiredItems
                .Select(item => new ItemReq(keyToId[item.ItemKey], item.Quantity, 0))
                .ToArray();
            giverIds[questIndex] = quest.Givers.Select(giver => keyToId[giver]).ToArray();
            completerIds[questIndex] = quest.Completers.Select(completer => keyToId[completer]).ToArray();
            chainsToIds[questIndex] = quest.ChainsTo.Select(chained => keyToId[chained]).ToArray();
            questFlags[questIndex] = quest.Implicit ? (byte)1 : (byte)0;
            stepOff[questIndex] = 0;
        }

        var q2qRows = new List<List<int>>();
        for (int i = 0; i < questNodeIds.Length; i++) q2qRows.Add(new List<int>());
        for (int questIndex = 0; questIndex < questNodeIds.Length; questIndex++)
        {
            foreach (int prereqNodeId in prereqs[questIndex])
            {
                if (questIndexByNodeId.TryGetValue(prereqNodeId, out int prereqIndex))
                {
                    q2qRows[prereqIndex].Add(questIndex);
                }
            }
        }

        var i2qRows = new List<List<int>>();
        for (int i = 0; i < itemNodeIds.Length; i++) i2qRows.Add(new List<int>());
        var itemIndexByNodeId = itemNodeIds.Select((id, index) => (id, index)).ToDictionary(p => p.id, p => p.index);
        for (int questIndex = 0; questIndex < questNodeIds.Length; questIndex++)
        {
            foreach (ItemReq item in requiredItems[questIndex])
            {
                if (itemIndexByNodeId.TryGetValue(item.ItemId, out int itemIndex))
                {
                    i2qRows[itemIndex].Add(questIndex);
                }
            }
        }

        (int[] Offsets, int[] Values) EncodeRows(IReadOnlyList<List<int>> rows)
        {
            var offsets = new int[rows.Count + 1];
            int count = 0;
            for (int i = 0; i < rows.Count; i++)
            {
                offsets[i] = count;
                count += rows[i].Count;
            }
            offsets[rows.Count] = count;
            var values = new int[count];
            int cursor = 0;
            foreach (List<int> row in rows)
            {
                foreach (int value in row)
                {
                    values[cursor++] = value;
                }
            }
            return (offsets, values);
        }

        var (i2qOff, i2qVal) = EncodeRows(i2qRows);
        var (q2qOff, q2qVal) = EncodeRows(q2qRows);

        var giverBlueprints = new List<QuestGiverEntry>();
        var completionBlueprints = new List<QuestCompletion>();
        for (int questIndex = 0; questIndex < questKeys.Length; questIndex++)
        {
            QuestDef quest = questByKey[questKeys[questIndex]];
            int questNodeId = questNodeIds[questIndex];
            string[] requiredQuestDbNames = quest.Prereqs
                .Select(prereq => questByKey.GetValueOrDefault(prereq)?.DbName)
                .Where(dbName => !string.IsNullOrEmpty(dbName))
                .Cast<string>()
                .ToArray();

            foreach (string giver in quest.Givers)
            {
                int giverId = keyToId[giver];
                giverBlueprints.Add(new QuestGiverEntry(
                    questNodeId,
                    giverId,
                    giverId,
                    interactionType: 0,
                    keyword: null,
                    requiredQuestDbNames));
            }

            foreach (string completer in quest.Completers)
            {
                int completerId = keyToId[completer];
                completionBlueprints.Add(new QuestCompletion(
                    questNodeId,
                    completerId,
                    completerId,
                    interactionType: 0,
                    keyword: null));
            }
        }

        return new CompiledGuideModel(
            strings.ToArray(),
            nodes,
            keyToId,
            Array.Empty<EdgeRecord>(),
            new int[keyToId.Count + 1],
            Array.Empty<int>(),
            new int[keyToId.Count + 1],
            Array.Empty<int>(),
            questNodeIds,
            prereqs,
            requiredItems,
            Array.Empty<StepEntry>(),
            stepOff,
            giverIds,
            completerIds,
            chainsToIds,
            questFlags,
            itemNodeIds,
            BuildItemSources(itemNodeIds, keyToId, charByKey),
            BuildUnlocks(keyToId),
            Enumerable.Range(0, questNodeIds.Length).ToArray(),
            i2qOff,
            i2qVal,
            q2qOff,
            q2qVal,
            Array.Empty<int>(),
            new[] { 0 },
            Array.Empty<int>(),
            giverBlueprints.ToArray(),
            completionBlueprints.ToArray(),
            new bool[keyToId.Count]);
    }

    private SourceSiteEntry[][] BuildItemSources(
        int[] itemNodeIds,
        Dictionary<string, int> keyToId,
        Dictionary<string, CharacterDef> charByKey)
    {
        var rows = itemNodeIds.Select(_ => Array.Empty<SourceSiteEntry>()).ToArray();
        var itemIndexByNodeId = itemNodeIds.Select((id, index) => (id, index)).ToDictionary(x => x.id, x => x.index);
        foreach (var group in _itemSources.GroupBy(def => def.ItemKey, StringComparer.Ordinal))
        {
            if (!keyToId.TryGetValue(group.Key, out int itemNodeId) || !itemIndexByNodeId.TryGetValue(itemNodeId, out int itemIndex))
            {
                continue;
            }

            var entries = new List<SourceSiteEntry>();
            foreach (ItemSourceDef def in group)
            {
                int sourceId = keyToId[def.SourceKey];
                CharacterDef? character = charByKey.GetValueOrDefault(def.SourceKey);
                SpawnPositionEntry[] positions = character is null
                    ? Array.Empty<SpawnPositionEntry>()
                    : new[] { new SpawnPositionEntry(sourceId, character.X, character.Y, character.Z) };
                entries.Add(new SourceSiteEntry(
                    sourceId,
                    sourceType: 2,
                    edgeType: 16,
                    directItemId: 0,
                    scene: character?.Scene,
                    positions: positions));
            }

            rows[itemIndex] = entries.ToArray();
        }

        return rows;
    }

    private Dictionary<int, UnlockPredicateEntry> BuildUnlocks(Dictionary<string, int> keyToId)
    {
        return _unlockDefs
            .GroupBy(def => def.TargetKey, StringComparer.Ordinal)
            .ToDictionary(
                group => keyToId[group.Key],
                group => new UnlockPredicateEntry(
                    group.Select(def => new UnlockConditionEntry(
                        keyToId[def.SourceKey],
                        def.CheckType,
                        def.Group)).ToArray(),
                    group.Max(def => (int)def.Group),
                    group.Any(def => def.Group != 0) ? (byte)1 : (byte)0));
    }
}
