#nullable enable

using SQLite;

/// <summary>
/// A character that a furnishing of the Reliquary's <c>PlanningTable</c> places. Building a
/// room or statue slot turns on the slot's child whose name is the <c>EquipmentToActivate</c>
/// of the furniture item that the player puts into the slot, and turns off the others.
/// </summary>
[Table("PlanningTableCharacters")]
public class PlanningTableCharacterRecord
{
    public const string TableName = "PlanningTableCharacters";

    [PrimaryKey]
    [ForeignKey(typeof(CharacterRecord), "StableKey")]
    public string CharacterStableKey { get; set; } = string.Empty;

    public string Scene { get; set; } = string.Empty;

    /// <summary>The <c>PlanningTable</c> field of the slot: <c>L1</c> to <c>R4</c>, or a statue.</summary>
    public string Slot { get; set; } = string.Empty;

    /// <summary>The name of the slot's child that holds the character.</summary>
    public string Furnishing { get; set; } = string.Empty;
}
