using SQLite;

[Table("Factions")]
public class FactionDBRecord
{
    public int FactionDBIndex { get; set; } // Index from GlobalFactionManager.FactionDB array
    public string FactionName { get; set; } // From WorldFaction.FactionName (Display Name)
    public string FactionDesc { get; set; } // From WorldFaction.FactionDesc
    public float DefaultValue { get; set; } // From WorldFaction.DEFAULTVAL

    [PrimaryKey] // Use REFNAME as the primary key for uniqueness
    public string REFNAME { get; set; } // From WorldFaction.REFNAME (Unique Identifier)

    // Note: FactionValue (current runtime value) is generally not exported
    // as it's player-specific save data, not static game data.
}
