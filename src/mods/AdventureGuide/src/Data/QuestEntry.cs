using Newtonsoft.Json;

namespace AdventureGuide.Data;

public sealed class QuestEntry
{
    [JsonProperty("db_name")] public string DBName { get; set; } = "";
    [JsonProperty("stable_key")] public string StableKey { get; set; } = "";
    [JsonProperty("display_name")] public string DisplayName { get; set; } = "";
    [JsonProperty("description")] public string? Description { get; set; }
    [JsonProperty("quest_type")] public string? QuestType { get; set; }
    [JsonProperty("zone_context")] public string? ZoneContext { get; set; }
    [JsonProperty("difficulty")] public string? Difficulty { get; set; }
    [JsonProperty("estimated_time")] public string? EstimatedTime { get; set; }
    [JsonProperty("tags")] public List<string>? Tags { get; set; }
    [JsonProperty("acquisition")] public List<AcquisitionSource>? Acquisition { get; set; }
    [JsonProperty("prerequisites")] public List<string>? Prerequisites { get; set; }
    [JsonProperty("steps")] public List<QuestStep>? Steps { get; set; }
    [JsonProperty("required_items")] public List<RequiredItemInfo>? RequiredItems { get; set; }
    [JsonProperty("completion")] public List<CompletionSource>? Completion { get; set; }
    [JsonProperty("rewards")] public RewardInfo? Rewards { get; set; }
    [JsonProperty("chain")] public List<ChainLink>? Chain { get; set; }
    [JsonProperty("flags")] public QuestFlags? Flags { get; set; }
    [JsonProperty("level_estimate")] public LevelEstimate? LevelEstimate { get; set; }
}

public sealed class QuestStep
{
    [JsonProperty("order")] public int Order { get; set; }
    [JsonProperty("action")] public string Action { get; set; } = "";
    [JsonProperty("description")] public string Description { get; set; } = "";
    [JsonProperty("target_name")] public string? TargetName { get; set; }
    [JsonProperty("target_type")] public string? TargetType { get; set; }
    [JsonProperty("quantity")] public int? Quantity { get; set; }
    [JsonProperty("zone_name")] public string? ZoneName { get; set; }
    [JsonProperty("keyword")] public string? Keyword { get; set; }
    [JsonProperty("tips")] public List<string>? Tips { get; set; }
    [JsonProperty("level_estimate")] public LevelEstimate? LevelEstimate { get; set; }
}

public sealed class AcquisitionSource
{
    [JsonProperty("method")] public string Method { get; set; } = "";
    [JsonProperty("source_name")] public string? SourceName { get; set; }
    [JsonProperty("source_type")] public string? SourceType { get; set; }
    [JsonProperty("zone_name")] public string? ZoneName { get; set; }
    [JsonProperty("note")] public string? Note { get; set; }
}

public sealed class CompletionSource
{
    [JsonProperty("method")] public string Method { get; set; } = "";
    [JsonProperty("source_name")] public string? SourceName { get; set; }
    [JsonProperty("source_type")] public string? SourceType { get; set; }
    [JsonProperty("zone_name")] public string? ZoneName { get; set; }
    [JsonProperty("keyword")] public string? Keyword { get; set; }
    [JsonProperty("note")] public string? Note { get; set; }
}

public sealed class RequiredItemInfo
{
    [JsonProperty("item_name")] public string ItemName { get; set; } = "";
    [JsonProperty("item_stable_key")] public string ItemStableKey { get; set; } = "";
    [JsonProperty("quantity")] public int Quantity { get; set; } = 1;
    [JsonProperty("drop_sources")] public List<DropSource>? DropSources { get; set; }
    [JsonProperty("vendor_sources")] public List<VendorSource>? VendorSources { get; set; }
    [JsonProperty("fishing_sources")] public List<FishingSource>? FishingSources { get; set; }
    [JsonProperty("mining_sources")] public List<MiningSource>? MiningSources { get; set; }
    [JsonProperty("bag_sources")] public List<BagSource>? BagSources { get; set; }
    [JsonProperty("crafting_sources")] public List<CraftingSource>? CraftingSources { get; set; }
    [JsonProperty("quest_reward_sources")] public List<QuestRewardSource>? QuestRewardSources { get; set; }
}

public sealed class DropSource
{
    [JsonProperty("character_name")] public string CharacterName { get; set; } = "";
    [JsonProperty("zone_name")] public string? ZoneName { get; set; }
}

public sealed class VendorSource
{
    [JsonProperty("character_name")] public string CharacterName { get; set; } = "";
    [JsonProperty("zone_name")] public string? ZoneName { get; set; }

}

public sealed class FishingSource
{
    [JsonProperty("water_stable_key")] public string WaterStableKey { get; set; } = "";
    [JsonProperty("zone_name")] public string? ZoneName { get; set; }
    [JsonProperty("drop_chance")] public float? DropChance { get; set; }
}

public sealed class MiningSource
{
    [JsonProperty("node_stable_key")] public string NodeStableKey { get; set; } = "";
    [JsonProperty("zone_name")] public string? ZoneName { get; set; }
    [JsonProperty("drop_chance")] public float? DropChance { get; set; }
}

public sealed class BagSource
{
    [JsonProperty("zone_name")] public string? ZoneName { get; set; }
    [JsonProperty("x")] public float? X { get; set; }
    [JsonProperty("y")] public float? Y { get; set; }
    [JsonProperty("z")] public float? Z { get; set; }
    [JsonProperty("respawns")] public bool Respawns { get; set; }
}

public sealed class CraftingSource
{
    [JsonProperty("recipe_item_name")] public string RecipeItemName { get; set; } = "";
    [JsonProperty("recipe_item_stable_key")] public string RecipeItemStableKey { get; set; } = "";
}

public sealed class QuestRewardSource
{
    [JsonProperty("quest_name")] public string QuestName { get; set; } = "";
    [JsonProperty("quest_stable_key")] public string QuestStableKey { get; set; } = "";
}

public sealed class LevelEstimate
{
    [JsonProperty("recommended")] public int? Recommended { get; set; }
    [JsonProperty("factors")] public List<LevelFactor>? Factors { get; set; }
}

public sealed class LevelFactor
{
    [JsonProperty("source")] public string Source { get; set; } = "";
    [JsonProperty("name")] public string? Name { get; set; }
    [JsonProperty("level")] public int Level { get; set; }
}

public sealed class RewardInfo
{
    [JsonProperty("xp")] public int XP { get; set; }
    [JsonProperty("gold")] public int Gold { get; set; }
    [JsonProperty("item_name")] public string? ItemName { get; set; }
    [JsonProperty("next_quest_name")] public string? NextQuestName { get; set; }
    [JsonProperty("next_quest_stable_key")] public string? NextQuestStableKey { get; set; }
    [JsonProperty("also_completes")] public List<string>? AlsoCompletes { get; set; }
    [JsonProperty("achievements")] public List<string>? Achievements { get; set; }
    [JsonProperty("faction_effects")] public List<FactionEffect>? FactionEffects { get; set; }
}

public sealed class FactionEffect
{
    [JsonProperty("faction_name")] public string FactionName { get; set; } = "";
    [JsonProperty("amount")] public int Amount { get; set; }
}

public sealed class ChainLink
{
    [JsonProperty("quest_name")] public string QuestName { get; set; } = "";
    [JsonProperty("quest_stable_key")] public string QuestStableKey { get; set; } = "";
    [JsonProperty("relationship")] public string Relationship { get; set; } = "";
}

public sealed class QuestFlags
{
    [JsonProperty("repeatable")] public bool Repeatable { get; set; }
    [JsonProperty("disabled")] public bool Disabled { get; set; }
    [JsonProperty("disabled_text")] public string? DisabledText { get; set; }
    [JsonProperty("kill_turn_in_holder")] public bool KillTurnInHolder { get; set; }
    [JsonProperty("destroy_turn_in_holder")] public bool DestroyTurnInHolder { get; set; }
    [JsonProperty("once_per_spawn_instance")] public bool OncePerSpawnInstance { get; set; }
}