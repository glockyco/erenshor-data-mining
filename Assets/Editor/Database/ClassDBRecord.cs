using SQLite;

[Table("Classes")]
public class ClassDBRecord
{
    [PrimaryKey]
    public string ClassName { get; set; }

    public float MitigationBonus { get; set; }
    public int StrBenefit { get; set; }
    public int EndBenefit { get; set; }
    public int DexBenefit { get; set; }
    public int AgiBenefit { get; set; }
    public int IntBenefit { get; set; }
    public int WisBenefit { get; set; }
    public int ChaBenefit { get; set; }
    public float AggroMod { get; set; }
    
    public string ResourceName { get; set; } // The filename of the ScriptableObject asset
}
