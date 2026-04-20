using Newtonsoft.Json;

namespace AdventureGuide.CompiledGuide;

/// <summary>
/// Top-level JSON DTO mirroring the Python CompiledData structure.
/// Deserialized from guide.json via Newtonsoft.Json.
/// </summary>
public sealed class CompiledGuideData
{
    [JsonProperty("nodes")]
    public CompiledNodeData[] Nodes { get; set; } = Array.Empty<CompiledNodeData>();

    [JsonProperty("edges")]
    public CompiledEdgeData[] Edges { get; set; } = Array.Empty<CompiledEdgeData>();

    [JsonProperty("forward_adjacency")]
    public int[][] ForwardAdjacency { get; set; } = Array.Empty<int[]>();

    [JsonProperty("reverse_adjacency")]
    public int[][] ReverseAdjacency { get; set; } = Array.Empty<int[]>();

    [JsonProperty("quest_node_ids")]
    public int[] QuestNodeIds { get; set; } = Array.Empty<int>();

    [JsonProperty("item_node_ids")]
    public int[] ItemNodeIds { get; set; } = Array.Empty<int>();

    [JsonProperty("quest_specs")]
    public CompiledQuestSpecData[] QuestSpecs { get; set; } = Array.Empty<CompiledQuestSpecData>();

    [JsonProperty("item_sources")]
    public CompiledSourceSiteData[][] ItemSources { get; set; } =
        Array.Empty<CompiledSourceSiteData[]>();

    [JsonProperty("unlock_predicates")]
    public CompiledUnlockPredicateData[] UnlockPredicates { get; set; } =
        Array.Empty<CompiledUnlockPredicateData>();

    [JsonProperty("topo_order")]
    public int[] TopoOrder { get; set; } = Array.Empty<int>();

    [JsonProperty("item_to_quest_indices")]
    public int[][] ItemToQuestIndices { get; set; } = Array.Empty<int[]>();

    [JsonProperty("quest_to_dependent_quest_indices")]
    public int[][] QuestToDependentQuestIndices { get; set; } = Array.Empty<int[]>();

    [JsonProperty("zone_node_ids")]
    public int[] ZoneNodeIds { get; set; } = Array.Empty<int>();

    [JsonProperty("zone_adjacency")]
    public int[][] ZoneAdjacency { get; set; } = Array.Empty<int[]>();

    [JsonProperty("giver_blueprints")]
    public CompiledGiverBlueprintData[] GiverBlueprints { get; set; } =
        Array.Empty<CompiledGiverBlueprintData>();

    [JsonProperty("completion_blueprints")]
    public CompiledCompletionBlueprintData[] CompletionBlueprints { get; set; } =
        Array.Empty<CompiledCompletionBlueprintData>();

    [JsonProperty("infeasible_node_ids")]
    public int[] InfeasibleNodeIds { get; set; } = Array.Empty<int>();
}

public sealed class CompiledNodeData
{
    [JsonProperty("node_id")]
    public int NodeId { get; set; }

    [JsonProperty("key")]
    public string Key { get; set; } = string.Empty;

    [JsonProperty("node_type")]
    public int NodeType { get; set; }

    [JsonProperty("display_name")]
    public string DisplayName { get; set; } = string.Empty;

    [JsonProperty("scene")]
    public string? Scene { get; set; }

    [JsonProperty("x")]
    public float? X { get; set; }

    [JsonProperty("y")]
    public float? Y { get; set; }

    [JsonProperty("z")]
    public float? Z { get; set; }

    [JsonProperty("flags")]
    public int Flags { get; set; }

    [JsonProperty("level")]
    public int Level { get; set; }

    [JsonProperty("zone_key")]
    public string? ZoneKey { get; set; }

    [JsonProperty("db_name")]
    public string? DbName { get; set; }

    [JsonProperty("description")]
    public string? Description { get; set; }

    [JsonProperty("keyword")]
    public string? Keyword { get; set; }

    [JsonProperty("zone_display")]
    public string? ZoneDisplay { get; set; }

    [JsonProperty("xp_reward")]
    public int XpReward { get; set; }

    [JsonProperty("gold_reward")]
    public int GoldReward { get; set; }

    [JsonProperty("reward_item_key")]
    public string? RewardItemKey { get; set; }

    [JsonProperty("disabled_text")]
    public string? DisabledText { get; set; }

    [JsonProperty("key_item_key")]
    public string? KeyItemKey { get; set; }

    [JsonProperty("destination_zone_key")]
    public string? DestinationZoneKey { get; set; }

    [JsonProperty("destination_display")]
    public string? DestinationDisplay { get; set; }
}

public sealed class CompiledEdgeData
{
    [JsonProperty("source_id")]
    public int SourceId { get; set; }

    [JsonProperty("target_id")]
    public int TargetId { get; set; }

    [JsonProperty("edge_type")]
    public int EdgeType { get; set; }

    [JsonProperty("flags")]
    public int Flags { get; set; }

    [JsonProperty("group")]
    public string? Group { get; set; }

    [JsonProperty("ordinal")]
    public int Ordinal { get; set; }

    [JsonProperty("quantity")]
    public int Quantity { get; set; }

    [JsonProperty("keyword")]
    public string? Keyword { get; set; }

    [JsonProperty("chance")]
    public int Chance { get; set; }

    [JsonProperty("note")]
    public string? Note { get; set; }

    [JsonProperty("amount")]
    public int Amount { get; set; }
}

public sealed class CompiledQuestSpecData
{
    [JsonProperty("quest_id")]
    public int QuestId { get; set; }

    [JsonProperty("quest_index")]
    public int QuestIndex { get; set; }

    [JsonProperty("prereq_quest_ids")]
    public int[] PrereqQuestIds { get; set; } = Array.Empty<int>();

    [JsonProperty("prereq_quest_indices")]
    public int[] PrereqQuestIndices { get; set; } = Array.Empty<int>();

    [JsonProperty("required_items")]
    public CompiledItemRequirementData[] RequiredItems { get; set; } =
        Array.Empty<CompiledItemRequirementData>();

    [JsonProperty("steps")]
    public CompiledStepData[] Steps { get; set; } = Array.Empty<CompiledStepData>();

    [JsonProperty("giver_node_ids")]
    public int[] GiverNodeIds { get; set; } = Array.Empty<int>();

    [JsonProperty("completer_node_ids")]
    public int[] CompleterNodeIds { get; set; } = Array.Empty<int>();

    [JsonProperty("chains_to_ids")]
    public int[] ChainsToIds { get; set; } = Array.Empty<int>();

    [JsonProperty("is_implicit")]
    public bool IsImplicit { get; set; }

    [JsonProperty("is_infeasible")]
    public bool IsInfeasible { get; set; }

    [JsonProperty("display_name")]
    public string? DisplayName { get; set; }
}

public sealed class CompiledItemRequirementData
{
    [JsonProperty("item_id")]
    public int ItemId { get; set; }

    [JsonProperty("qty")]
    public int Qty { get; set; }

    [JsonProperty("group")]
    public int Group { get; set; }
}

public sealed class CompiledStepData
{
    [JsonProperty("step_type")]
    public int StepType { get; set; }

    [JsonProperty("target_id")]
    public int TargetId { get; set; }

    [JsonProperty("ordinal")]
    public int Ordinal { get; set; }
}

public sealed class CompiledSourceSiteData
{
    [JsonProperty("source_id")]
    public int SourceId { get; set; }

    [JsonProperty("source_type")]
    public int SourceType { get; set; }

    [JsonProperty("edge_type")]
    public int EdgeType { get; set; }

    [JsonProperty("direct_item_id")]
    public int DirectItemId { get; set; }

    [JsonProperty("scene")]
    public string? Scene { get; set; }

    [JsonProperty("positions")]
    public CompiledSpawnPositionData[] Positions { get; set; } =
        Array.Empty<CompiledSpawnPositionData>();

    [JsonProperty("keyword")]
    public string? Keyword { get; set; }
}

public sealed class CompiledSpawnPositionData
{
    [JsonProperty("spawn_id")]
    public int SpawnId { get; set; }

    [JsonProperty("x")]
    public float X { get; set; }

    [JsonProperty("y")]
    public float Y { get; set; }

    [JsonProperty("z")]
    public float Z { get; set; }
}

public sealed class CompiledUnlockPredicateData
{
    [JsonProperty("target_id")]
    public int TargetId { get; set; }

    [JsonProperty("conditions")]
    public CompiledUnlockConditionData[] Conditions { get; set; } =
        Array.Empty<CompiledUnlockConditionData>();

    [JsonProperty("group_count")]
    public int GroupCount { get; set; }

    [JsonProperty("semantics")]
    public int Semantics { get; set; }
}

public sealed class CompiledUnlockConditionData
{
    [JsonProperty("source_id")]
    public int SourceId { get; set; }

    [JsonProperty("check_type")]
    public int CheckType { get; set; }

    [JsonProperty("group")]
    public int Group { get; set; }
}

public sealed class CompiledGiverBlueprintData
{
    [JsonProperty("quest_id")]
    public int QuestId { get; set; }

    [JsonProperty("character_id")]
    public int CharacterId { get; set; }

    [JsonProperty("position_id")]
    public int PositionId { get; set; }

    [JsonProperty("interaction_type")]
    public int InteractionType { get; set; }

    [JsonProperty("keyword")]
    public string? Keyword { get; set; }

    [JsonProperty("required_quest_db_names")]
    public string[] RequiredQuestDbNames { get; set; } = Array.Empty<string>();
}

public sealed class CompiledCompletionBlueprintData
{
    [JsonProperty("quest_id")]
    public int QuestId { get; set; }

    [JsonProperty("character_id")]
    public int CharacterId { get; set; }

    [JsonProperty("position_id")]
    public int PositionId { get; set; }

    [JsonProperty("interaction_type")]
    public int InteractionType { get; set; }

    [JsonProperty("keyword")]
    public string? Keyword { get; set; }
}

/// <summary>
/// Domain flags for compiled nodes. Bit positions must match the Python
/// compiler's NodeFlags enum exactly.
/// </summary>
[Flags]
internal enum NodeFlags : ushort
{
    IsFriendly = 1 << 0,
    IsVendor = 1 << 1,
    NightSpawn = 1 << 2,
    Implicit = 1 << 3,
    Repeatable = 1 << 4,
    Disabled = 1 << 5,
    IsDirectlyPlaced = 1 << 6,
    IsEnabled = 1 << 7,
    Invulnerable = 1 << 8,
    IsRare = 1 << 9,
    IsTriggerSpawn = 1 << 10,
}
