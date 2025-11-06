#nullable enable

using SQLite;

[Table("Factions")]
public class WorldFactionRecord
{
    public const string TableName = "Factions";

    [PrimaryKey]
    public string StableKey { get; set; } = string.Empty; // Stable identifier: "faction:refname"
    public int FactionDBIndex { get; set; } // Index from GlobalFactionManager.FactionDB array (internal Unity use only)
    public string FactionName { get; set; } = string.Empty; // From WorldFaction.FactionName (Display Name)
    public string FactionDesc { get; set; } = string.Empty; // From WorldFaction.FactionDesc
    public float DefaultValue { get; set; } // From WorldFaction.DEFAULTVAL

    // Internals / Metadata
    public string REFNAME { get; set; } = string.Empty; // From WorldFaction.REFNAME (Unique Identifier)
    public string ResourceName { get; set; } = string.Empty; // The filename of the ScriptableObject asset

    // Note: FactionValue (current runtime value) is generally not exported
    // as it's player-specific save data, not static game data.
}
