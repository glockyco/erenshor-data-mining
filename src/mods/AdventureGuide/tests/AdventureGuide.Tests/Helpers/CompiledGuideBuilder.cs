using AdventureGuide.CompiledGuide;
using CompiledGuideModel = AdventureGuide.CompiledGuide.CompiledGuide;

namespace AdventureGuide.Tests.Helpers;

/// <summary>
/// Minimal fluent builder for CompiledGuide tests.
///
/// Builds a CompiledGuideData DTO and passes it to the CompiledGuide
/// constructor. No binary serialization, no string interning, no CSR encoding.
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
    private sealed record CharacterDef(string Key, string? Scene, float X, float Y, float Z, bool IsFriendly);
    private sealed record StepDef(string QuestKey, byte StepType, string TargetKey);
    private sealed record ItemSourceDef(string ItemKey, string SourceKey, byte EdgeType, byte SourceType);
    private sealed record UnlockDef(string TargetKey, string SourceKey, byte Group, byte CheckType);

    private readonly List<QuestDef> _quests = new();
    private readonly List<ItemDef> _items = new();
    private readonly List<CharacterDef> _characters = new();
    private readonly List<StepDef> _steps = new();
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
        float z = float.NaN,
        bool isFriendly = false)
    {
        _characters.Add(new CharacterDef(key, scene, x, y, z, isFriendly));
        return this;
    }

    public CompiledGuideBuilder AddStep(string questKey, byte stepType, string targetKey)
    {
        _steps.Add(new StepDef(questKey, stepType, targetKey));
        return this;
    }

    public CompiledGuideBuilder AddItemSource(
        string itemKey,
        string sourceKey,
        byte edgeType = 16,
        byte sourceType = 2)
    {
        _itemSources.Add(new ItemSourceDef(itemKey, sourceKey, edgeType, sourceType));
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
        // Collect all keys and assign stable node IDs
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
        foreach (StepDef step in _steps)
        {
            allKeys.Add(step.QuestKey);
            allKeys.Add(step.TargetKey);
        }
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

        var questByKey = _quests.ToDictionary(q => q.Key, StringComparer.Ordinal);
        var itemKeys = _items.Select(i => i.Key).OrderBy(k => k, StringComparer.Ordinal).ToArray();
        var questKeys = _quests.Select(q => q.Key).OrderBy(k => k, StringComparer.Ordinal).ToArray();
        var charByKey = _characters.ToDictionary(c => c.Key, StringComparer.Ordinal);

        // Build node DTOs
        var nodes = new CompiledNodeData[keyToId.Count];
        foreach ((string key, int id) in keyToId)
        {
            nodes[id] = BuildNodeData(key, id, questByKey, itemKeys, charByKey);
        }

        // Build quest specs
        int[] questNodeIds = questKeys.Select(key => keyToId[key]).ToArray();
        int[] itemNodeIds = itemKeys.Select(key => keyToId[key]).ToArray();
        var questIndexByNodeId = questNodeIds.Select((id, index) => (id, index)).ToDictionary(p => p.id, p => p.index);

        var questSpecs = new CompiledQuestSpecData[questKeys.Length];
        for (int questIndex = 0; questIndex < questKeys.Length; questIndex++)
        {
            QuestDef quest = questByKey[questKeys[questIndex]];
            int[] prereqNodeIds = quest.Prereqs.Select(p => keyToId[p]).ToArray();
            int[] prereqIndices = prereqNodeIds
                .Where(id => questIndexByNodeId.ContainsKey(id))
                .Select(id => questIndexByNodeId[id])
                .ToArray();

            var steps = _steps
                .Where(s => string.Equals(s.QuestKey, quest.Key, StringComparison.Ordinal))
                .Select((s, ordinal) => new CompiledStepData
                {
                    StepType = s.StepType,
                    TargetId = keyToId[s.TargetKey],
                    Ordinal = ordinal,
                })
                .ToArray();

            questSpecs[questIndex] = new CompiledQuestSpecData
            {
                QuestId = questNodeIds[questIndex],
                QuestIndex = questIndex,
                PrereqQuestIds = prereqNodeIds,
                PrereqQuestIndices = prereqIndices,
                RequiredItems = quest.RequiredItems
                    .Select(r => new CompiledItemRequirementData { ItemId = keyToId[r.ItemKey], Qty = r.Quantity, Group = 0 })
                    .ToArray(),
                Steps = steps,
                GiverNodeIds = quest.Givers.Select(g => keyToId[g]).ToArray(),
                CompleterNodeIds = quest.Completers.Select(c => keyToId[c]).ToArray(),
                ChainsToIds = quest.ChainsTo.Select(c => keyToId[c]).ToArray(),
                IsImplicit = quest.Implicit,
                IsInfeasible = false,
                DisplayName = quest.Key,
            };
        }

        // Build reverse dependency indices
        var q2qRows = Enumerable.Range(0, questNodeIds.Length).Select(_ => new List<int>()).ToArray();
        for (int qi = 0; qi < questNodeIds.Length; qi++)
        {
            foreach (int prereqNodeId in questSpecs[qi].PrereqQuestIds)
            {
                if (questIndexByNodeId.TryGetValue(prereqNodeId, out int prereqIndex))
                {
                    q2qRows[prereqIndex].Add(qi);
                }
            }
        }

        var itemIndexByNodeId = itemNodeIds.Select((id, index) => (id, index)).ToDictionary(p => p.id, p => p.index);
        var i2qRows = Enumerable.Range(0, itemNodeIds.Length).Select(_ => new List<int>()).ToArray();
        for (int qi = 0; qi < questNodeIds.Length; qi++)
        {
            foreach (CompiledItemRequirementData item in questSpecs[qi].RequiredItems)
            {
                if (itemIndexByNodeId.TryGetValue(item.ItemId, out int itemIndex))
                {
                    i2qRows[itemIndex].Add(qi);
                }
            }
        }

        // Build giver/completion blueprints
        var giverBlueprints = new List<CompiledGiverBlueprintData>();
        var completionBlueprints = new List<CompiledCompletionBlueprintData>();
        for (int questIndex = 0; questIndex < questKeys.Length; questIndex++)
        {
            QuestDef quest = questByKey[questKeys[questIndex]];
            int questNid = questNodeIds[questIndex];
            string[] requiredQuestDbNames = quest.Prereqs
                .Select(prereq => questByKey.GetValueOrDefault(prereq)?.DbName)
                .Where(dbName => !string.IsNullOrEmpty(dbName))
                .Cast<string>()
                .ToArray();

            foreach (string giver in quest.Givers)
            {
                int giverId = keyToId[giver];
                giverBlueprints.Add(new CompiledGiverBlueprintData
                {
                    QuestId = questNid,
                    CharacterId = giverId,
                    PositionId = giverId,
                    InteractionType = 0,
                    Keyword = null,
                    RequiredQuestDbNames = requiredQuestDbNames,
                });
            }

            foreach (string completer in quest.Completers)
            {
                int completerId = keyToId[completer];
                completionBlueprints.Add(new CompiledCompletionBlueprintData
                {
                    QuestId = questNid,
                    CharacterId = completerId,
                    PositionId = completerId,
                    InteractionType = 0,
                    Keyword = null,
                });
            }
        }

        // Build item sources
        CompiledSourceSiteData[][] itemSourcesDto = BuildItemSourcesDto(itemNodeIds, keyToId, charByKey);

        // Build unlock predicates
        CompiledUnlockPredicateData[] unlockPredicates = BuildUnlockPredicatesDto(keyToId);

        int nodeCount = keyToId.Count;
        var data = new CompiledGuideData
        {
            Nodes = nodes,
            Edges = Array.Empty<CompiledEdgeData>(),
            ForwardAdjacency = Enumerable.Range(0, nodeCount).Select(_ => Array.Empty<int>()).ToArray(),
            ReverseAdjacency = Enumerable.Range(0, nodeCount).Select(_ => Array.Empty<int>()).ToArray(),
            QuestNodeIds = questNodeIds,
            ItemNodeIds = itemNodeIds,
            QuestSpecs = questSpecs,
            ItemSources = itemSourcesDto,
            UnlockPredicates = unlockPredicates,
            TopoOrder = Enumerable.Range(0, questNodeIds.Length).ToArray(),
            ItemToQuestIndices = i2qRows.Select(r => r.ToArray()).ToArray(),
            QuestToDependentQuestIndices = q2qRows.Select(r => r.ToArray()).ToArray(),
            ZoneNodeIds = Array.Empty<int>(),
            ZoneAdjacency = Array.Empty<int[]>(),
            ZoneLineIds = Array.Empty<int[]>(),
            GiverBlueprints = giverBlueprints.ToArray(),
            CompletionBlueprints = completionBlueprints.ToArray(),
            InfeasibleNodeIds = Array.Empty<int>(),
        };

        return new CompiledGuideModel(data);
    }

    private static CompiledNodeData BuildNodeData(
        string key,
        int id,
        Dictionary<string, QuestDef> questByKey,
        string[] itemKeys,
        Dictionary<string, CharacterDef> charByKey)
    {
        if (questByKey.TryGetValue(key, out QuestDef? quest))
        {
            int flags = quest.Implicit ? (int)NodeFlags.Implicit : 0;
            return new CompiledNodeData
            {
                NodeId = id,
                Key = key,
                NodeType = 0,
                DisplayName = key,
                Flags = flags,
                DbName = quest.DbName,
            };
        }

        if (itemKeys.Contains(key, StringComparer.Ordinal))
        {
            return new CompiledNodeData
            {
                NodeId = id,
                Key = key,
                NodeType = 1,
                DisplayName = key,
            };
        }

        if (charByKey.TryGetValue(key, out CharacterDef? character))
        {
            int flags = character.IsFriendly ? (int)NodeFlags.IsFriendly : 0;
            return new CompiledNodeData
            {
                NodeId = id,
                Key = key,
                NodeType = 2,
                DisplayName = key,
                Scene = character.Scene,
                X = float.IsNaN(character.X) ? null : character.X,
                Y = float.IsNaN(character.Y) ? null : character.Y,
                Z = float.IsNaN(character.Z) ? null : character.Z,
                Flags = flags,
            };
        }

        return new CompiledNodeData
        {
            NodeId = id,
            Key = key,
            NodeType = 255,
            DisplayName = key,
        };
    }

    private CompiledSourceSiteData[][] BuildItemSourcesDto(
        int[] itemNodeIds,
        Dictionary<string, int> keyToId,
        Dictionary<string, CharacterDef> charByKey)
    {
        var rows = itemNodeIds.Select(_ => Array.Empty<CompiledSourceSiteData>()).ToArray();
        var itemIndexByNodeId = itemNodeIds.Select((id, index) => (id, index)).ToDictionary(x => x.id, x => x.index);
        foreach (var group in _itemSources.GroupBy(def => def.ItemKey, StringComparer.Ordinal))
        {
            if (!keyToId.TryGetValue(group.Key, out int itemNodeId) || !itemIndexByNodeId.TryGetValue(itemNodeId, out int itemIndex))
            {
                continue;
            }

            var entries = new List<CompiledSourceSiteData>();
            foreach (ItemSourceDef def in group)
            {
                int sourceId = keyToId[def.SourceKey];
                CharacterDef? character = charByKey.GetValueOrDefault(def.SourceKey);
                CompiledSpawnPositionData[] positions = character is null
                    ? Array.Empty<CompiledSpawnPositionData>()
                    : new[] { new CompiledSpawnPositionData { SpawnId = sourceId, X = character.X, Y = character.Y, Z = character.Z } };
                entries.Add(new CompiledSourceSiteData
                {
                    SourceId = sourceId,
                    SourceType = def.SourceType,
                    EdgeType = def.EdgeType,
                    DirectItemId = 0,
                    Scene = character?.Scene,
                    Positions = positions,
                });
            }
            rows[itemIndex] = entries.ToArray();
        }
        return rows;
    }

    private CompiledUnlockPredicateData[] BuildUnlockPredicatesDto(Dictionary<string, int> keyToId)
    {
        return _unlockDefs
            .GroupBy(def => def.TargetKey, StringComparer.Ordinal)
            .Select(group => new CompiledUnlockPredicateData
            {
                TargetId = keyToId[group.Key],
                Conditions = group.Select(def => new CompiledUnlockConditionData
                {
                    SourceId = keyToId[def.SourceKey],
                    CheckType = def.CheckType,
                    Group = def.Group,
                }).ToArray(),
                GroupCount = group.Max(def => (int)def.Group),
                Semantics = group.Any(def => def.Group != 0) ? 1 : 0,
            })
            .ToArray();
    }
}
