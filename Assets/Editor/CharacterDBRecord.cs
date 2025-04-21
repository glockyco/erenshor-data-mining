using SQLite;

[Table("Characters")]
public class CharacterDBRecord
{
    [PrimaryKey]
    public string PrefabGuid { get; set; }
    public string PrefabName { get; set; }
    public string NPCName { get; set; }
    public int MyFaction { get; set; }
    public int BaseFaction { get; set; }
    public int TempFaction { get; set; }
    public float AggroRange { get; set; }
    public bool Alive { get; set; }
    public bool isNPC { get; set; }
    public bool isVendor { get; set; }
    public float AttackRange { get; set; }
    public bool Invulnerable { get; set; }

    // Stats properties
    public bool HasStats { get; set; }
    public string CharacterName { get; set; }
    public int Level { get; set; }
    public int BaseHP { get; set; }
    public int BaseAC { get; set; }
    public int BaseMana { get; set; }
    public int BaseStr { get; set; }
    public int BaseEnd { get; set; }
    public int BaseDex { get; set; }
    public int BaseAgi { get; set; }
    public int BaseInt { get; set; }
    public int BaseWis { get; set; }
    public int BaseCha { get; set; }
    public int BaseRes { get; set; }
    public int BaseMR { get; set; }
    public int BaseER { get; set; }
    public int BasePR { get; set; }
    public int BaseVR { get; set; }
}
