using System.Text;

public class WikiFancyArmor
{
    [UseForComparison]
    public string Image { get; set; } = "[[File:{{PAGENAME}}.png|80px]]";
    [UseForComparison]
    public string Name { get; set; } = "{{PAGENAME}}";
    [UseForComparison]
    public string Slot { get; set; } // Charm, Head, Neck, Ring, Hand, Chest, Arm, Bracer, Leg, Waist, Foot, Back
    [UseForComparison]
    public bool Relic { get; set; }

    [UseForComparison]
    public int Str { get; set; }
    [UseForComparison]
    public int End { get; set; }
    [UseForComparison]
    public int Dex { get; set; }
    [UseForComparison]
    public int Agi { get; set; }
    [UseForComparison]
    public int Int { get; set; }
    [UseForComparison]
    public int Wis { get; set; }
    [UseForComparison]
    public int Cha { get; set; }
    [UseForComparison]
    public int Res { get; set; }
    
    [UseForComparison]
    public int Health { get; set; }
    [UseForComparison]
    public int Mana { get; set; }
    [UseForComparison]
    public int Armor { get; set; }

    [UseForComparison]
    public int Magic { get; set; }
    [UseForComparison]
    public int Poison { get; set; }
    [UseForComparison]
    public int Elemental { get; set; }
    [UseForComparison]
    public int Void { get; set; }

    [UseForComparison]
    public string Description { get; set; }

    [UseForComparison]
    public bool Arcanist { get; set; }
    [UseForComparison]
    public bool Duelist { get; set; }
    [UseForComparison]
    public bool Druid { get; set; }
    [UseForComparison]
    public bool Paladin { get; set; }

    [UseForComparison]
    public string ProcName { get; set; }
    [UseForComparison]
    public string ProcDesc { get; set; }
    [UseForComparison]
    public float? ProcChance { get; set; }
    [UseForComparison]
    public string ProcStyle { get; set; } // Bash, Attack, Cast, Kick, Worn

    [UseForComparison]
    public int Tier { get; set; } // 0, 1, 2
    
    public string OriginalWikiString { get; set; }
    
    public override string ToString()
    {
        var sb = new StringBuilder();
        sb.AppendLine("{{Fancy-armor");

        sb.AppendLine($"| image = {Image}");
        sb.AppendLine($"| name = {Name}");
        sb.AppendLine($"| slot = {Slot}");
        sb.AppendLine($"| relic = {(Relic ? "True" : "")}");

        sb.AppendLine($"| str = {Str}");
        sb.AppendLine($"| end = {End}");
        sb.AppendLine($"| dex = {Dex}");
        sb.AppendLine($"| agi = {Agi}");
        sb.AppendLine($"| int = {Int}");
        sb.AppendLine($"| wis = {Wis}");
        sb.AppendLine($"| cha = {Cha}");
        sb.AppendLine($"| res = {Res}");
        
        sb.AppendLine($"| health = {Health}");
        sb.AppendLine($"| mana = {Mana}");
        sb.AppendLine($"| armor = {Armor}");

        sb.AppendLine($"| magic = {Magic}");
        sb.AppendLine($"| poison = {Poison}");
        sb.AppendLine($"| elemental = {Elemental}");
        sb.AppendLine($"| void = {Void}");

        sb.AppendLine($"| description = {Description}");

        sb.AppendLine($"| arcanist = {(Arcanist ? "True" : "")}");
        sb.AppendLine($"| duelist = {(Duelist ? "True" : "")}");
        sb.AppendLine($"| druid = {(Druid ? "True" : "")}");
        sb.AppendLine($"| paladin = {(Paladin ? "True" : "")}");

        sb.AppendLine($"| proc_name = {ProcName ?? ""}");
        sb.AppendLine($"| proc_desc = {ProcDesc ?? ""}");
        sb.AppendLine($"| proc_chance = {(ProcChance is null or 0 ? "" : ProcChance)}");
        sb.AppendLine($"| proc_style = {ProcStyle ?? ""}");

        sb.AppendLine($"| tier = {Tier}");

        sb.Append("}}");
        return sb.ToString();
    }
}
