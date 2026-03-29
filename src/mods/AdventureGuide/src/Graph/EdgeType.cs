using System.Runtime.Serialization;
using Newtonsoft.Json;
using Newtonsoft.Json.Converters;

namespace AdventureGuide.Graph;

[JsonConverter(typeof(StringEnumConverter))]
public enum EdgeType
{
    [EnumMember(Value = "requires_quest")]
    RequiresQuest,

    [EnumMember(Value = "requires_item")]
    RequiresItem,

    [EnumMember(Value = "step_talk")]
    StepTalk,

    [EnumMember(Value = "step_kill")]
    StepKill,

    [EnumMember(Value = "step_travel")]
    StepTravel,

    [EnumMember(Value = "step_shout")]
    StepShout,

    [EnumMember(Value = "step_read")]
    StepRead,

    [EnumMember(Value = "completed_by")]
    CompletedBy,

    [EnumMember(Value = "assigned_by")]
    AssignedBy,

    [EnumMember(Value = "rewards_item")]
    RewardsItem,

    [EnumMember(Value = "chains_to")]
    ChainsTo,

    [EnumMember(Value = "also_completes")]
    AlsoCompletes,

    [EnumMember(Value = "unlocks_zone_line")]
    UnlocksZoneLine,

    [EnumMember(Value = "unlocks_character")]
    UnlocksCharacter,

    [EnumMember(Value = "affects_faction")]
    AffectsFaction,

    [EnumMember(Value = "unlocks_vendor_item")]
    UnlocksVendorItem,

    [EnumMember(Value = "crafted_from")]
    CraftedFrom,

    [EnumMember(Value = "teaches_spell")]
    TeachesSpell,

    [EnumMember(Value = "assigns_quest")]
    AssignsQuest,

    [EnumMember(Value = "completes_quest")]
    CompletesQuest,

    [EnumMember(Value = "unlocks_door")]
    UnlocksDoor,

    [EnumMember(Value = "enables_interaction")]
    EnablesInteraction,

    [EnumMember(Value = "drops_item")]
    DropsItem,

    [EnumMember(Value = "sells_item")]
    SellsItem,

    [EnumMember(Value = "gives_item")]
    GivesItem,

    [EnumMember(Value = "spawns_in")]
    SpawnsIn,

    [EnumMember(Value = "has_spawn")]
    HasSpawn,

    [EnumMember(Value = "belongs_to_faction")]
    BelongsToFaction,

    [EnumMember(Value = "protects")]
    Protects,

    [EnumMember(Value = "requires_material")]
    RequiresMaterial,

    [EnumMember(Value = "produces")]
    Produces,

    [EnumMember(Value = "connects_to")]
    ConnectsTo,

    [EnumMember(Value = "contains")]
    Contains,

    [EnumMember(Value = "yields_item")]
    YieldsItem,

    [EnumMember(Value = "spawns_character")]
    SpawnsCharacter,

    [EnumMember(Value = "gated_by_quest")]
    GatedByQuest,

    [EnumMember(Value = "stops_after_quest")]
    StopsAfterQuest,

    [EnumMember(Value = "connects_zones")]
    ConnectsZones,

    [EnumMember(Value = "removes_invulnerability")]
    RemovesInvulnerability,
}
