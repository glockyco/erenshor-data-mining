using System.Runtime.Serialization;
using Newtonsoft.Json;
using Newtonsoft.Json.Converters;

namespace AdventureGuide.Graph;

[JsonConverter(typeof(StringEnumConverter))]
public enum NodeType
{
    [EnumMember(Value = "quest")]
    Quest,

    [EnumMember(Value = "item")]
    Item,

    [EnumMember(Value = "character")]
    Character,

    [EnumMember(Value = "zone")]
    Zone,

    [EnumMember(Value = "zone_line")]
    ZoneLine,

    [EnumMember(Value = "spawn_point")]
    SpawnPoint,

    [EnumMember(Value = "mining_node")]
    MiningNode,

    [EnumMember(Value = "water")]
    Water,

    [EnumMember(Value = "forge")]
    Forge,

    [EnumMember(Value = "item_bag")]
    ItemBag,

    [EnumMember(Value = "recipe")]
    Recipe,

    [EnumMember(Value = "door")]
    Door,

    [EnumMember(Value = "faction")]
    Faction,

    [EnumMember(Value = "spell")]
    Spell,

    [EnumMember(Value = "skill")]
    Skill,

    [EnumMember(Value = "teleport")]
    Teleport,

    [EnumMember(Value = "world_object")]
    WorldObject,

    [EnumMember(Value = "achievement_trigger")]
    AchievementTrigger,

    [EnumMember(Value = "secret_passage")]
    SecretPassage,

    [EnumMember(Value = "wishing_well")]
    WishingWell,

    [EnumMember(Value = "treasure_location")]
    TreasureLocation,

    [EnumMember(Value = "book")]
    Book,

    [EnumMember(Value = "class_")]
    Class,

    [EnumMember(Value = "stance")]
    Stance,

    [EnumMember(Value = "ascension")]
    Ascension,
}
