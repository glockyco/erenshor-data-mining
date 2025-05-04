using System.Text;

public class WikiFancyArmor
{
    public string Image { get; set; } = "[[File:{{PAGENAME}}.png|80px]]";
    public string Name { get; set; } = "{{PAGENAME}}";
    public string Slot { get; set; } // Charm, Head, Neck, Ring, Hand, Chest, Arm, Bracer, Leg, Waist, Foot, Back
    public bool Relic { get; set; }

    public int Str { get; set; }
    public int End { get; set; }
    public int Dex { get; set; }
    public int Agi { get; set; }
    public int Int { get; set; }
    public int Wis { get; set; }
    public int Cha { get; set; }
    public int Res { get; set; }
    
    public int Health { get; set; }
    public int Mana { get; set; }
    public int Armor { get; set; }

    public int Magic { get; set; }
    public int Poison { get; set; }
    public int Elemental { get; set; }
    public int Void { get; set; }

    public string Description { get; set; }

    public bool Arcanist { get; set; }
    public bool Duelist { get; set; }
    public bool Druid { get; set; }
    public bool Paladin { get; set; }

    public string ProcName { get; set; }
    public string ProcDesc { get; set; }
    public float? ProcChance { get; set; }
    public string ProcStyle { get; set; } // Bash, Attack, Cast, Kick, Worn

    public int Tier { get; set; } // 0, 1, 2
    
    public override string ToString()
    {
        var sb = new StringBuilder();
        sb.AppendLine("{{Fancy-weapon");

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
