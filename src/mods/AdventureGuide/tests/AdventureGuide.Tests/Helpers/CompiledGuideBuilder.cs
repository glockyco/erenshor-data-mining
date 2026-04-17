using AdventureGuide.CompiledGuide;
using AdventureGuide.Graph;
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
        (string ItemKey, int Quantity)[] RequiredItems
    );

    private sealed record ItemDef(string Key);

    private sealed record CharacterDef(
        string Key,
        string? Scene,
        float X,
        float Y,
        float Z,
        bool IsFriendly
    );

    private sealed record StepDef(string QuestKey, byte StepType, string TargetKey);

    private sealed record ItemSourceDef(
        string ItemKey,
        string SourceKey,
        byte EdgeType,
        byte SourceType,
        string[] PositionKeys
    );

    private sealed record UnlockDef(string TargetKey, string SourceKey, byte Group, byte CheckType);

    private sealed record ZoneLineDef(
        string Key,
        string? Scene,
        string? DestinationZoneKey,
        float X,
        float Y,
        float Z,
        bool IsEnabled
    );

    private sealed record ZoneDef(string Key, string? Scene);

    private sealed record SpawnPointDef(
        string Key,
        string? Scene,
        string? Zone,
        float X,
        float Y,
        float Z
    );

    private sealed record DoorDef(string Key, string? Scene, string? KeyItemKey);

    private sealed record MiningNodeDef(string Key, string? Scene, float X, float Y, float Z);

    private sealed record ItemBagDef(string Key, string? Scene);

    private sealed record WaterDef(string Key, string? Scene, float X, float Y, float Z);

    private sealed record RecipeDef(string Key);

    private sealed record EdgeDef(
        string Source,
        string Target,
        EdgeType Type,
        string? Group,
        int? Ordinal,
        int? Quantity,
        string? Keyword,
        string? Note,
        int? Amount
    );

    private readonly List<QuestDef> _quests = new();
    private readonly List<ItemDef> _items = new();
    private readonly List<CharacterDef> _characters = new();
    private readonly List<StepDef> _steps = new();
    private readonly List<ItemSourceDef> _itemSources = new();
    private readonly List<UnlockDef> _unlockDefs = new();
    private readonly List<ZoneLineDef> _zoneLines = new();
    private readonly List<ZoneDef> _zones = new();
    private readonly List<SpawnPointDef> _spawnPoints = new();
    private readonly List<DoorDef> _doors = new();
    private readonly List<MiningNodeDef> _miningNodes = new();
    private readonly List<ItemBagDef> _itemBags = new();
    private readonly List<WaterDef> _waters = new();
    private readonly List<RecipeDef> _recipes = new();
    private readonly List<EdgeDef> _edges = new();

    public CompiledGuideBuilder AddQuest(
        string key,
        string? dbName = null,
        string[]? prereqs = null,
        bool implicit_ = false,
        string[]? givers = null,
        string[]? completers = null,
        string[]? chainsTo = null,
        (string ItemKey, int Quantity)[]? requiredItems = null
    )
    {
        _quests.Add(
            new QuestDef(
                key,
                dbName,
                prereqs ?? Array.Empty<string>(),
                implicit_,
                givers ?? Array.Empty<string>(),
                completers ?? Array.Empty<string>(),
                chainsTo ?? Array.Empty<string>(),
                requiredItems ?? Array.Empty<(string, int)>()
            )
        );
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
        bool isFriendly = false
    )
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
        byte edgeType = (byte)EdgeType.DropsItem,
        byte sourceType = (byte)NodeType.Character,
        string[]? positionKeys = null
    )
    {
        _itemSources.Add(
            new ItemSourceDef(
                itemKey,
                sourceKey,
                edgeType,
                sourceType,
                positionKeys ?? Array.Empty<string>()
            )
        );
        return this;
    }

    public CompiledGuideBuilder AddUnlockPredicate(
        string targetKey,
        string sourceKey,
        byte group = 0,
        byte checkType = 0
    )
    {
        _unlockDefs.Add(new UnlockDef(targetKey, sourceKey, group, checkType));
        return this;
    }

    public CompiledGuideBuilder AddZoneLine(
        string key,
        string? scene = null,
        string? destinationZoneKey = null,
        float x = float.NaN,
        float y = float.NaN,
        float z = float.NaN,
        bool isEnabled = true
    )
    {
        _zoneLines.Add(new ZoneLineDef(key, scene, destinationZoneKey, x, y, z, isEnabled));
        return this;
    }

    public CompiledGuideBuilder AddZone(string key, string? scene = null)
    {
        _zones.Add(new ZoneDef(key, scene));
        return this;
    }

    public CompiledGuideBuilder AddSpawnPoint(
        string key,
        string? scene = null,
        string? zone = null,
        float x = float.NaN,
        float y = float.NaN,
        float z = float.NaN
    )
    {
        _spawnPoints.Add(new SpawnPointDef(key, scene, zone, x, y, z));
        return this;
    }

    public CompiledGuideBuilder AddDoor(string key, string? scene = null, string? keyItemKey = null)
    {
        _doors.Add(new DoorDef(key, scene, keyItemKey));
        return this;
    }

    public CompiledGuideBuilder AddMiningNode(
        string key,
        string? scene = null,
        float x = float.NaN,
        float y = float.NaN,
        float z = float.NaN
    )
    {
        _miningNodes.Add(new MiningNodeDef(key, scene, x, y, z));
        return this;
    }

    public CompiledGuideBuilder AddItemBag(string key, string? scene = null)
    {
        _itemBags.Add(new ItemBagDef(key, scene));
        return this;
    }

    public CompiledGuideBuilder AddWater(
        string key,
        string? scene = null,
        float x = float.NaN,
        float y = float.NaN,
        float z = float.NaN
    )
    {
        _waters.Add(new WaterDef(key, scene, x, y, z));
        return this;
    }

    public CompiledGuideBuilder AddRecipe(string key)
    {
        _recipes.Add(new RecipeDef(key));
        return this;
    }

    public CompiledGuideBuilder AddEdge(
        string source,
        string target,
        EdgeType type,
        string? group = null,
        int? ordinal = null,
        int? quantity = null,
        string? keyword = null,
        string? note = null,
        int? amount = null
    )
    {
        _edges.Add(
            new EdgeDef(source, target, type, group, ordinal, quantity, keyword, note, amount)
        );
        return this;
    }

    public CompiledGuideModel Build()
    {
        // Collect all keys and assign stable node IDs
        var allKeys = new SortedSet<string>(StringComparer.Ordinal);
        foreach (QuestDef quest in _quests)
        {
            allKeys.Add(quest.Key);
            foreach (string prereq in quest.Prereqs)
                allKeys.Add(prereq);
            foreach (string giver in quest.Givers)
                allKeys.Add(giver);
            foreach (string completer in quest.Completers)
                allKeys.Add(completer);
            foreach (string chained in quest.ChainsTo)
                allKeys.Add(chained);
            foreach ((string itemKey, _) in quest.RequiredItems)
                allKeys.Add(itemKey);
        }
        foreach (ItemDef item in _items)
            allKeys.Add(item.Key);
        foreach (CharacterDef character in _characters)
            allKeys.Add(character.Key);
        foreach (StepDef step in _steps)
        {
            allKeys.Add(step.QuestKey);
            allKeys.Add(step.TargetKey);
        }
        foreach (ItemSourceDef source in _itemSources)
        {
            allKeys.Add(source.ItemKey);
            allKeys.Add(source.SourceKey);
            foreach (string positionKey in source.PositionKeys)
                allKeys.Add(positionKey);
        }
        foreach (UnlockDef unlock in _unlockDefs)
        {
            allKeys.Add(unlock.TargetKey);
            allKeys.Add(unlock.SourceKey);
        }
        foreach (ZoneLineDef zl in _zoneLines)
            allKeys.Add(zl.Key);
        foreach (ZoneDef z in _zones)
            allKeys.Add(z.Key);
        foreach (SpawnPointDef sp in _spawnPoints)
            allKeys.Add(sp.Key);
        foreach (DoorDef d in _doors)
            allKeys.Add(d.Key);
        foreach (MiningNodeDef mn in _miningNodes)
            allKeys.Add(mn.Key);
        foreach (ItemBagDef ib in _itemBags)
            allKeys.Add(ib.Key);
        foreach (WaterDef w in _waters)
            allKeys.Add(w.Key);
        foreach (RecipeDef recipe in _recipes)
            allKeys.Add(recipe.Key);
        foreach (EdgeDef e in _edges)
        {
            allKeys.Add(e.Source);
            allKeys.Add(e.Target);
        }

        var keyToId = new Dictionary<string, int>(StringComparer.Ordinal);
        int nodeId = 0;
        foreach (string key in allKeys)
        {
            keyToId[key] = nodeId++;
        }

        var questByKey = _quests.ToDictionary(q => q.Key, StringComparer.Ordinal);
        var itemKeys = _items.Select(i => i.Key).OrderBy(k => k, StringComparer.Ordinal).ToArray();
        var questKeys = _quests
            .Select(q => q.Key)
            .OrderBy(k => k, StringComparer.Ordinal)
            .ToArray();
        var charByKey = _characters.ToDictionary(c => c.Key, StringComparer.Ordinal);
        var zoneLineByKey = _zoneLines.ToDictionary(zl => zl.Key, StringComparer.Ordinal);
        var zoneByKey = _zones.ToDictionary(z => z.Key, StringComparer.Ordinal);
        var spawnPointByKey = _spawnPoints.ToDictionary(sp => sp.Key, StringComparer.Ordinal);
        var doorByKey = _doors.ToDictionary(d => d.Key, StringComparer.Ordinal);
        var miningNodeByKey = _miningNodes.ToDictionary(mn => mn.Key, StringComparer.Ordinal);
        var itemBagByKey = _itemBags.ToDictionary(ib => ib.Key, StringComparer.Ordinal);
        var waterByKey = _waters.ToDictionary(w => w.Key, StringComparer.Ordinal);
        var recipeByKey = _recipes.ToDictionary(r => r.Key, StringComparer.Ordinal);

        // Build node DTOs
        var nodes = new CompiledNodeData[keyToId.Count];
        foreach ((string key, int id) in keyToId)
        {
            nodes[id] = BuildNodeData(
                key,
                id,
                questByKey,
                itemKeys,
                charByKey,
                zoneLineByKey,
                zoneByKey,
                spawnPointByKey,
                doorByKey,
                miningNodeByKey,
                itemBagByKey,
                waterByKey,
                recipeByKey
            );
        }

        // Build quest specs
        int[] questNodeIds = questKeys.Select(key => keyToId[key]).ToArray();
        int[] itemNodeIds = itemKeys.Select(key => keyToId[key]).ToArray();
        var questIndexByNodeId = questNodeIds
            .Select((id, index) => (id, index))
            .ToDictionary(p => p.id, p => p.index);

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
                .Select(
                    (s, ordinal) =>
                        new CompiledStepData
                        {
                            StepType = s.StepType,
                            TargetId = keyToId[s.TargetKey],
                            Ordinal = ordinal,
                        }
                )
                .ToArray();

            questSpecs[questIndex] = new CompiledQuestSpecData
            {
                QuestId = questNodeIds[questIndex],
                QuestIndex = questIndex,
                PrereqQuestIds = prereqNodeIds,
                PrereqQuestIndices = prereqIndices,
                RequiredItems = quest
                    .RequiredItems.Select(r => new CompiledItemRequirementData
                    {
                        ItemId = keyToId[r.ItemKey],
                        Qty = r.Quantity,
                        Group = 0,
                    })
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

        var q2qRows = Enumerable
            .Range(0, questNodeIds.Length)
            .Select(_ => new List<int>())
            .ToArray();
        for (int qi = 0; qi < questNodeIds.Length; qi++)
        {
            foreach (int prereqNodeId in questSpecs[qi].PrereqQuestIds)
            {
                if (questIndexByNodeId.TryGetValue(prereqNodeId, out int prereqIndex))
                    q2qRows[prereqIndex].Add(qi);
            }
        }

        var itemIndexByNodeId = itemNodeIds
            .Select((id, index) => (id, index))
            .ToDictionary(p => p.id, p => p.index);
        var i2qRows = Enumerable
            .Range(0, itemNodeIds.Length)
            .Select(_ => new List<int>())
            .ToArray();
        for (int qi = 0; qi < questNodeIds.Length; qi++)
        {
            foreach (CompiledItemRequirementData item in questSpecs[qi].RequiredItems)
            {
                if (itemIndexByNodeId.TryGetValue(item.ItemId, out int itemIndex))
                    i2qRows[itemIndex].Add(qi);
            }
        }

        var giverBlueprints = new List<CompiledGiverBlueprintData>();
        var completionBlueprints = new List<CompiledCompletionBlueprintData>();
        for (int questIndex = 0; questIndex < questKeys.Length; questIndex++)
        {
            QuestDef quest = questByKey[questKeys[questIndex]];
            int questNid = questNodeIds[questIndex];
            string[] requiredQuestDbNames = quest
                .Prereqs.Select(prereq => questByKey.GetValueOrDefault(prereq)?.DbName)
                .Where(dbName => !string.IsNullOrEmpty(dbName))
                .Cast<string>()
                .ToArray();
            foreach (string giver in quest.Givers)
            {
                int giverId = keyToId[giver];
                giverBlueprints.Add(
                    new CompiledGiverBlueprintData
                    {
                        QuestId = questNid,
                        CharacterId = giverId,
                        PositionId = giverId,
                        InteractionType = 0,
                        Keyword = null,
                        RequiredQuestDbNames = requiredQuestDbNames,
                    }
                );
            }

            foreach (string completer in quest.Completers)
            {
                int completerId = keyToId[completer];
                completionBlueprints.Add(
                    new CompiledCompletionBlueprintData
                    {
                        QuestId = questNid,
                        CharacterId = completerId,
                        PositionId = completerId,
                        InteractionType = 0,
                        Keyword = null,
                    }
                );
            }
        }

        CompiledSourceSiteData[][] itemSourcesDto = BuildItemSourcesDto(
            itemNodeIds,
            keyToId,
            nodes,
            spawnPointByKey
        );

        // Build unlock predicates
        CompiledUnlockPredicateData[] unlockPredicates = BuildUnlockPredicatesDto(keyToId);

        // Build edges and adjacency
        var edgeDataList = new List<CompiledEdgeData>();
        var forwardAdj = Enumerable.Range(0, keyToId.Count).Select(_ => new List<int>()).ToArray();
        var reverseAdj = Enumerable.Range(0, keyToId.Count).Select(_ => new List<int>()).ToArray();

        for (int i = 0; i < _edges.Count; i++)
        {
            EdgeDef e = _edges[i];
            int sourceId = keyToId[e.Source];
            int targetId = keyToId[e.Target];

            edgeDataList.Add(
                new CompiledEdgeData
                {
                    SourceId = sourceId,
                    TargetId = targetId,
                    EdgeType = (int)e.Type,
                    Group = e.Group,
                    Ordinal = e.Ordinal ?? 0,
                    Flags = 0,

                    Quantity = e.Quantity ?? 0,
                    Keyword = e.Keyword,
                    Note = e.Note,
                    Amount = e.Amount ?? 0,
                }
            );
            int edgeIndex = edgeDataList.Count - 1;
            forwardAdj[sourceId].Add(edgeIndex);
            reverseAdj[targetId].Add(edgeIndex);
        }

        int nodeCount = keyToId.Count;
        var data = new CompiledGuideData
        {
            Nodes = nodes,
            Edges = edgeDataList.ToArray(),
            ForwardAdjacency = forwardAdj.Select(l => l.ToArray()).ToArray(),
            ReverseAdjacency = reverseAdj.Select(l => l.ToArray()).ToArray(),
            QuestNodeIds = questNodeIds,
            ItemNodeIds = itemNodeIds,
            QuestSpecs = questSpecs,
            ItemSources = itemSourcesDto,
            UnlockPredicates = unlockPredicates,
            TopoOrder = Enumerable.Range(0, questNodeIds.Length).ToArray(),

            ItemToQuestIndices = i2qRows.Select(l => l.ToArray()).ToArray(),
            QuestToDependentQuestIndices = q2qRows.Select(l => l.ToArray()).ToArray(),
            ZoneNodeIds = _zones.Select(z => keyToId[z.Key]).ToArray(),
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
        Dictionary<string, CharacterDef> charByKey,
        Dictionary<string, ZoneLineDef> zoneLineByKey,
        Dictionary<string, ZoneDef> zoneByKey,
        Dictionary<string, SpawnPointDef> spawnPointByKey,
        Dictionary<string, DoorDef> doorByKey,
        Dictionary<string, MiningNodeDef> miningNodeByKey,
        Dictionary<string, ItemBagDef> itemBagByKey,
        Dictionary<string, WaterDef> waterByKey,
        Dictionary<string, RecipeDef> recipeByKey
    )
    {
        // NodeType ordinals match the C# enum: Quest=0, Item=1, Character=2,
        // Zone=3, ZoneLine=4, SpawnPoint=5, MiningNode=6, Water=7, Forge=8,
        // ItemBag=9, Recipe=10, Door=11

        if (questByKey.TryGetValue(key, out QuestDef? quest))
        {
            int flags = quest.Implicit ? (int)NodeFlags.Implicit : 0;
            return new CompiledNodeData
            {
                NodeId = id,
                Key = key,
                NodeType = (int)Graph.NodeType.Quest,
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
                NodeType = (int)Graph.NodeType.Item,
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
                NodeType = (int)Graph.NodeType.Character,
                DisplayName = key,
                Scene = character.Scene,
                X = float.IsNaN(character.X) ? null : character.X,
                Y = float.IsNaN(character.Y) ? null : character.Y,
                Z = float.IsNaN(character.Z) ? null : character.Z,
                Flags = flags,
            };
        }

        if (zoneLineByKey.TryGetValue(key, out ZoneLineDef? zoneLine))
        {
            int flags = zoneLine.IsEnabled ? (int)NodeFlags.IsEnabled : 0;
            return new CompiledNodeData
            {
                NodeId = id,
                Key = key,
                NodeType = (int)Graph.NodeType.ZoneLine,
                DisplayName = key,
                Scene = zoneLine.Scene,
                X = float.IsNaN(zoneLine.X) ? null : zoneLine.X,
                Y = float.IsNaN(zoneLine.Y) ? null : zoneLine.Y,
                Z = float.IsNaN(zoneLine.Z) ? null : zoneLine.Z,
                DestinationZoneKey = zoneLine.DestinationZoneKey,
                Flags = flags,
            };
        }

        if (zoneByKey.TryGetValue(key, out ZoneDef? zone))
        {
            return new CompiledNodeData
            {
                NodeId = id,
                Key = key,
                NodeType = (int)Graph.NodeType.Zone,
                DisplayName = key,
                Scene = zone.Scene,
            };
        }

        if (spawnPointByKey.TryGetValue(key, out SpawnPointDef? spawnPoint))
        {
            return new CompiledNodeData
            {
                NodeId = id,
                Key = key,
                NodeType = (int)Graph.NodeType.SpawnPoint,
                DisplayName = key,
                Scene = spawnPoint.Scene,
                ZoneKey = spawnPoint.Zone,
                X = float.IsNaN(spawnPoint.X) ? null : spawnPoint.X,
                Y = float.IsNaN(spawnPoint.Y) ? null : spawnPoint.Y,
                Z = float.IsNaN(spawnPoint.Z) ? null : spawnPoint.Z,
            };
        }

        if (doorByKey.TryGetValue(key, out DoorDef? door))
        {
            return new CompiledNodeData
            {
                NodeId = id,
                Key = key,
                NodeType = (int)Graph.NodeType.Door,
                DisplayName = key,
                Scene = door.Scene,
                KeyItemKey = door.KeyItemKey,
            };
        }

        if (miningNodeByKey.TryGetValue(key, out MiningNodeDef? miningNode))
        {
            return new CompiledNodeData
            {
                NodeId = id,
                Key = key,
                NodeType = (int)Graph.NodeType.MiningNode,
                DisplayName = key,
                Scene = miningNode.Scene,
                X = miningNode.X,
                Y = miningNode.Y,
                Z = miningNode.Z,
            };
        }

        if (itemBagByKey.TryGetValue(key, out ItemBagDef? itemBag))
        {
            return new CompiledNodeData
            {
                NodeId = id,
                Key = key,
                NodeType = (int)Graph.NodeType.ItemBag,
                DisplayName = key,
                Scene = itemBag.Scene,
            };
        }

        if (waterByKey.TryGetValue(key, out WaterDef? water))
        {
            return new CompiledNodeData
            {
                NodeId = id,
                Key = key,
                NodeType = (int)Graph.NodeType.Water,
                DisplayName = key,
                Scene = water.Scene,
                X = float.IsNaN(water.X) ? null : water.X,
                Y = float.IsNaN(water.Y) ? null : water.Y,
                Z = float.IsNaN(water.Z) ? null : water.Z,
            };
        }

        if (recipeByKey.ContainsKey(key))
        {
            return new CompiledNodeData
            {
                NodeId = id,
                Key = key,
                NodeType = (int)Graph.NodeType.Recipe,
                DisplayName = key,
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
        CompiledNodeData[] nodes,
        Dictionary<string, SpawnPointDef> spawnPointByKey
    )
    {
        var rows = itemNodeIds.Select(_ => Array.Empty<CompiledSourceSiteData>()).ToArray();
        var itemIndexByNodeId = itemNodeIds
            .Select((id, index) => (id, index))
            .ToDictionary(x => x.id, x => x.index);
        foreach (var group in _itemSources.GroupBy(def => def.ItemKey, StringComparer.Ordinal))
        {
            if (
                !keyToId.TryGetValue(group.Key, out int itemNodeId)
                || !itemIndexByNodeId.TryGetValue(itemNodeId, out int itemIndex)
            )
            {
                continue;
            }

            var entries = new List<CompiledSourceSiteData>();
            foreach (ItemSourceDef def in group)
            {
                int sourceId = keyToId[def.SourceKey];
                CompiledNodeData sourceNode = nodes[sourceId];
                string? scene = sourceNode.Scene;
                CompiledSpawnPositionData[] positions;
                if (def.PositionKeys.Length > 0)
                {
                    positions = def
                        .PositionKeys.Where(spawnPointByKey.ContainsKey)
                        .Select(positionKey =>
                        {
                            var spawnPoint = spawnPointByKey[positionKey];
                            return new CompiledSpawnPositionData
                            {
                                SpawnId = keyToId[positionKey],
                                X = spawnPoint.X,
                                Y = spawnPoint.Y,
                                Z = spawnPoint.Z,
                            };
                        })
                        .ToArray();
                    if (positions.Length > 0)
                        scene = spawnPointByKey[def.PositionKeys[0]].Scene;
                }
                else if (sourceNode.X.HasValue && sourceNode.Y.HasValue && sourceNode.Z.HasValue)
                {
                    positions = new[]
                    {
                        new CompiledSpawnPositionData
                        {
                            SpawnId = sourceId,
                            X = sourceNode.X.Value,
                            Y = sourceNode.Y.Value,
                            Z = sourceNode.Z.Value,
                        },
                    };
                }
                else
                {
                    positions = Array.Empty<CompiledSpawnPositionData>();
                }

                entries.Add(
                    new CompiledSourceSiteData
                    {
                        SourceId = sourceId,
                        SourceType = def.SourceType,
                        EdgeType = def.EdgeType,
                        DirectItemId = 0,
                        Scene = scene,
                        Positions = positions,
                    }
                );
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
                Conditions = group
                    .Select(def => new CompiledUnlockConditionData
                    {
                        SourceId = keyToId[def.SourceKey],
                        CheckType = def.CheckType,
                        Group = def.Group,
                    })
                    .ToArray(),
                GroupCount = group.Max(def => (int)def.Group),
                Semantics = group.Any(def => def.Group != 0) ? 1 : 0,
            })
            .ToArray();
    }
}
