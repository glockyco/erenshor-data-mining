using System.ComponentModel;
using Newtonsoft.Json;
using Newtonsoft.Json.Converters;

namespace AdventureGuide.Graph;

public sealed class Node
{
    [JsonProperty("key")] public string Key { get; set; } = "";
    [JsonProperty("type"), JsonConverter(typeof(StringEnumConverter))] public NodeType Type { get; set; }
    [JsonProperty("display_name")] public string DisplayName { get; set; } = "";

    [JsonProperty("x")] public float? X { get; set; }
    [JsonProperty("y")] public float? Y { get; set; }
    [JsonProperty("z")] public float? Z { get; set; }
    [JsonProperty("scene")] public string? Scene { get; set; }
    [JsonProperty("db_name")] public string? DbName { get; set; }
    [JsonProperty("description")] public string? Description { get; set; }
    [JsonProperty("level")] public int? Level { get; set; }
    [JsonProperty("zone")] public string? Zone { get; set; }
    [JsonProperty("zone_key")] public string? ZoneKey { get; set; }
    [JsonProperty("keyword")] public string? Keyword { get; set; }

    [JsonProperty("night_spawn"), DefaultValue(false)] public bool NightSpawn { get; set; }
    [JsonProperty("is_enabled"), DefaultValue(true)] public bool IsEnabled { get; set; } = true;

    [JsonProperty("xp_reward")] public int? XpReward { get; set; }
    [JsonProperty("gold_reward")] public int? GoldReward { get; set; }
    [JsonProperty("reward_item_key")] public string? RewardItemKey { get; set; }

    [JsonProperty("repeatable"), DefaultValue(false)] public bool Repeatable { get; set; }
    [JsonProperty("disabled"), DefaultValue(false)] public bool Disabled { get; set; }
    [JsonProperty("disabled_text")] public string? DisabledText { get; set; }
    [JsonProperty("implicit"), DefaultValue(false)] public bool Implicit { get; set; }
    [JsonProperty("kill_turn_in_holder"), DefaultValue(false)] public bool KillTurnInHolder { get; set; }
    [JsonProperty("destroy_turn_in_holder"), DefaultValue(false)] public bool DestroyTurnInHolder { get; set; }
    [JsonProperty("drop_invuln_on_holder"), DefaultValue(false)] public bool DropInvulnOnHolder { get; set; }
    [JsonProperty("once_per_spawn_instance"), DefaultValue(false)] public bool OncePerSpawnInstance { get; set; }

    [JsonProperty("item_level")] public int? ItemLevel { get; set; }
    [JsonProperty("stackable"), DefaultValue(false)] public bool Stackable { get; set; }
    [JsonProperty("is_unique"), DefaultValue(false)] public bool IsUnique { get; set; }
    [JsonProperty("template"), DefaultValue(false)] public bool Template { get; set; }

    [JsonProperty("is_vendor"), DefaultValue(false)] public bool IsVendor { get; set; }
    [JsonProperty("is_friendly"), DefaultValue(false)] public bool IsFriendly { get; set; }
    [JsonProperty("invulnerable"), DefaultValue(false)] public bool Invulnerable { get; set; }
    [JsonProperty("faction_key")] public string? FactionKey { get; set; }

    [JsonProperty("spawn_chance")] public float? SpawnChance { get; set; }
    [JsonProperty("is_rare"), DefaultValue(false)] public bool IsRare { get; set; }
    [JsonProperty("respawn_delay")] public float? RespawnDelay { get; set; }
    [JsonProperty("respawn_time")] public float? RespawnTime { get; set; }
    [JsonProperty("respawns"), DefaultValue(true)] public bool Respawns { get; set; } = true;
    [JsonProperty("is_directly_placed"), DefaultValue(false)] public bool IsDirectlyPlaced { get; set; }
    [JsonProperty("is_trigger_spawn"), DefaultValue(false)] public bool IsTriggerSpawn { get; set; }

    [JsonProperty("key_item_key")] public string? KeyItemKey { get; set; }
    [JsonProperty("teleport_item_key")] public string? TeleportItemKey { get; set; }
    [JsonProperty("is_dungeon"), DefaultValue(false)] public bool IsDungeon { get; set; }

    [JsonProperty("level_min")] public int? LevelMin { get; set; }
    [JsonProperty("level_max")] public int? LevelMax { get; set; }

    [JsonProperty("book_title")] public string? BookTitle { get; set; }
    [JsonProperty("achievement_name")] public string? AchievementName { get; set; }
    [JsonProperty("default_value")] public float? DefaultValue { get; set; }

    [JsonProperty("destination_zone_key")] public string? DestinationZoneKey { get; set; }
    [JsonProperty("destination_display")] public string? DestinationDisplay { get; set; }
    [JsonProperty("landing_x")] public float? LandingX { get; set; }
    [JsonProperty("landing_y")] public float? LandingY { get; set; }
    [JsonProperty("landing_z")] public float? LandingZ { get; set; }

    public override string ToString() => Key;
}
