using SQLite;

public class CharacterDBRecord
{
    [PrimaryKey]
    public string PrefabGuid { get; set; }
    public string PrefabName { get; set; }
    public int MyFaction { get; set; }
    public int BaseFaction { get; set; }
    public int TempFaction { get; set; }
    public float AggroRange { get; set; }
    public bool Alive { get; set; }
    public bool isNPC { get; set; }
    public bool isVendor { get; set; }
    public float AttackRange { get; set; }
    public bool Invulnerable { get; set; }
    // Add more fields as needed, skipping UnityEngine.Object references
}