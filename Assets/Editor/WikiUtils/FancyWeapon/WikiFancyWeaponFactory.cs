using System;
using System.Linq;
using SQLite;

public class WikiFancyWeaponFactory
{
    private readonly SQLiteConnection _db;

    public WikiFancyWeaponFactory(SQLiteConnection db)
    {
        _db = db;
    }

    public WikiFancyWeapon Create(string wikiString)
    {
        var weapon = new WikiFancyWeapon();
        var parameters = WikiTemplateParser.ParseParameters(wikiString, "Fancy-weapon");

        weapon.Image = WikiTemplateParser.GetString(parameters, "image", "[[File:{{PAGENAME}}.png|80px]]");
        weapon.Name = WikiTemplateParser.GetString(parameters, "name", "{{PAGENAME}}");
        weapon.Type = WikiTemplateParser.GetString(parameters, "type");
        weapon.Relic = WikiTemplateParser.GetBool(parameters, "relic");

        weapon.Str = WikiTemplateParser.GetInt(parameters, "str");
        weapon.End = WikiTemplateParser.GetInt(parameters, "end");
        weapon.Dex = WikiTemplateParser.GetInt(parameters, "dex");
        weapon.Agi = WikiTemplateParser.GetInt(parameters, "agi");
        weapon.Int = WikiTemplateParser.GetInt(parameters, "int");
        weapon.Wis = WikiTemplateParser.GetInt(parameters, "wis");
        weapon.Cha = WikiTemplateParser.GetInt(parameters, "cha");
        weapon.Res = WikiTemplateParser.GetInt(parameters, "res");

        weapon.Damage = WikiTemplateParser.GetInt(parameters, "damage");
        weapon.Delay = WikiTemplateParser.GetFloat(parameters, "delay");

        weapon.Health = WikiTemplateParser.GetInt(parameters, "health");
        weapon.Mana = WikiTemplateParser.GetInt(parameters, "mana");
        weapon.Armor = WikiTemplateParser.GetInt(parameters, "armor");

        weapon.Magic = WikiTemplateParser.GetInt(parameters, "magic");
        weapon.Poison = WikiTemplateParser.GetInt(parameters, "poison");
        weapon.Elemental = WikiTemplateParser.GetInt(parameters, "elemental");
        weapon.Void = WikiTemplateParser.GetInt(parameters, "void");

        weapon.Description = WikiTemplateParser.GetString(parameters, "description");

        weapon.Arcanist = WikiTemplateParser.GetBool(parameters, "arcanist");
        weapon.Duelist = WikiTemplateParser.GetBool(parameters, "duelist");
        weapon.Druid = WikiTemplateParser.GetBool(parameters, "druid");
        weapon.Paladin = WikiTemplateParser.GetBool(parameters, "paladin");

        weapon.ProcName = WikiTemplateParser.GetString(parameters, "proc_name");
        weapon.ProcDesc = WikiTemplateParser.GetString(parameters, "proc_desc");
        weapon.ProcChance = WikiTemplateParser.GetFloat(parameters, "proc_chance");
        weapon.ProcStyle = WikiTemplateParser.GetString(parameters, "proc_style");

        weapon.Tier = WikiTemplateParser.GetInt(parameters, "tier");

        return weapon;
    }

    public WikiFancyWeapon Create(ItemDBRecord item)
    {
        // --- proc ---
        string spellId = null;
        string procStyle = "";
        if (!string.IsNullOrEmpty(item.WeaponProcOnHitId))
        {
            spellId = item.WeaponProcOnHitId;
            procStyle = item.Shield ? "Bash" : "Attack";
        }
        else if (!string.IsNullOrEmpty(item.WornEffectId))
        {
            spellId = item.WornEffectId;
            procStyle = "Worn";
        }

        SpellDBRecord spell = null;
        if (!string.IsNullOrEmpty(spellId))
        {
            spell = _db.Table<SpellDBRecord>().FirstOrDefault(s => s.Id == spellId);
        }

        // --- type ---
        string type;
        if (item.ThisWeaponType is "TwoHandMelee" or "TwoHandStaff")
        {
            if (item.RequiredSlot == "Primary")
            {
                type = "Primary - 2-Handed";
            }
            else
            {
                throw new ArgumentException();
            }
        }
        else
        {
            type = item.RequiredSlot switch
            {
                "PrimaryOrSecondary" => "Primary or Secondary",
                "Primary" => "Primary",
                "Secondary" => "Secondary",
                _ => throw new ArgumentException(),
            };
        }

        // --- tier ---
        int tier = item.Quality switch
        {
            "Normal" => 0,
            "Blessed" => 1,
            "Godly" => 2,
            _ => throw new ArgumentException(),
        };

        return new WikiFancyWeapon
        {
            Type = type,
            Relic = item.Relic,
            Str = item.Str,
            End = item.End,
            Dex = item.Dex,
            Agi = item.Agi,
            Int = item.Int,
            Wis = item.Wis,
            Cha = item.Cha,
            Res = item.Res,
            Damage = item.WeaponDmg,
            Delay = item.WeaponDly,
            Health = item.HP,
            Mana = item.Mana,
            Armor = item.AC,
            Magic = item.MR,
            Poison = item.PR,
            Elemental = item.ER,
            Void = item.VR,
            Description = item.Lore.Trim().Replace("|", "&#124;").Replace("=", "&#61;").Replace("\n", "<br>"),
            Arcanist = item.Classes.Split(", ").Contains("Arcanist"),
            Duelist = item.Classes.Split(", ").Contains("Duelist"),
            Druid = item.Classes.Split(", ").Contains("Druid"),
            Paladin = item.Classes.Split(", ").Contains("Paladin"),
            ProcName = spell == null ? "" : $"{{{{AbilityLink|{spell.SpellName}}}}}",
            ProcDesc = spell == null ? "" : spell.SpellDesc,
            ProcChance = item.WeaponProcChance,
            ProcStyle = procStyle,
            Tier = tier,
        };
    }
}
