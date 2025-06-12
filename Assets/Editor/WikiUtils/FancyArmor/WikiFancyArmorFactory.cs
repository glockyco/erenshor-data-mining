using System;
using System.Linq;
using System.Text.RegularExpressions;
using SQLite;

public class WikiFancyArmorFactory
{
    private readonly SQLiteConnection _db;

    public WikiFancyArmorFactory(SQLiteConnection db)
    {
        _db = db;
    }

    public WikiFancyArmor Create(string wikiString)
    {
        if (wikiString is null || !wikiString.Contains("Fancy-armor"))
        {
            return null;
        }
        
        var armor = new WikiFancyArmor();
        var parameters = WikiTemplateParser.ParseParameters(wikiString, "Fancy-armor");

        armor.Image = WikiTemplateParser.GetString(parameters, "image", "[[File:{{PAGENAME}}.png|80px]]");
        armor.Name = WikiTemplateParser.GetString(parameters, "name", "{{PAGENAME}}");
        armor.Slot = WikiTemplateParser.GetString(parameters, "slot");
        armor.Relic = WikiTemplateParser.GetBool(parameters, "relic");

        armor.Str = WikiTemplateParser.GetInt(parameters, "str");
        armor.End = WikiTemplateParser.GetInt(parameters, "end");
        armor.Dex = WikiTemplateParser.GetInt(parameters, "dex");
        armor.Agi = WikiTemplateParser.GetInt(parameters, "agi");
        armor.Int = WikiTemplateParser.GetInt(parameters, "int");
        armor.Wis = WikiTemplateParser.GetInt(parameters, "wis");
        armor.Cha = WikiTemplateParser.GetInt(parameters, "cha");
        armor.Res = WikiTemplateParser.GetInt(parameters, "res");

        armor.Health = WikiTemplateParser.GetInt(parameters, "health");
        armor.Mana = WikiTemplateParser.GetInt(parameters, "mana");
        armor.Armor = WikiTemplateParser.GetInt(parameters, "armor");

        armor.Magic = WikiTemplateParser.GetInt(parameters, "magic");
        armor.Poison = WikiTemplateParser.GetInt(parameters, "poison");
        armor.Elemental = WikiTemplateParser.GetInt(parameters, "elemental");
        armor.Void = WikiTemplateParser.GetInt(parameters, "void");

        armor.Description = WikiTemplateParser.GetString(parameters, "description");

        armor.Arcanist = WikiTemplateParser.GetBool(parameters, "arcanist");
        armor.Duelist = WikiTemplateParser.GetBool(parameters, "duelist");
        armor.Druid = WikiTemplateParser.GetBool(parameters, "druid");
        armor.Paladin = WikiTemplateParser.GetBool(parameters, "paladin");

        armor.ProcName = WikiTemplateParser.GetString(parameters, "proc_name");
        armor.ProcDesc = WikiTemplateParser.GetString(parameters, "proc_desc");
        armor.ProcChance = WikiTemplateParser.GetFloat(parameters, "proc_chance");
        armor.ProcStyle = WikiTemplateParser.GetString(parameters, "proc_style");

        armor.Tier = WikiTemplateParser.GetInt(parameters, "tier");

        armor.OriginalWikiString = wikiString;

        return armor;
    }

    public WikiFancyArmor Create(ItemDBRecord item)
    {
        if (item is null)
        {
            return null;
        }
        
        // --- proc ---
        string spellString = "";
        string procStyle = "";
        if (!string.IsNullOrEmpty(item.ItemEffectOnClick))
        {
            spellString = item.ItemEffectOnClick;
            procStyle = "Activatable";
        }
        else if (!string.IsNullOrEmpty(item.WornEffect))
        {
            spellString = item.WornEffect;
            procStyle = "Worn";
        }
        else if (!string.IsNullOrEmpty(item.WeaponProcOnHit))
        {
            spellString = item.WeaponProcOnHit;
            procStyle = "Cast";
        }
        
        string spellId = null;
        var match = Regex.Match(spellString, @"\(([^)]+)\)");
        if (match.Success)
        {
            spellId = match.Groups[1].Value;
        }

        SpellDBRecord spell = null;
        if (!string.IsNullOrEmpty(spellId))
        {
            spell = _db.Table<SpellDBRecord>().FirstOrDefault(s => s.Id == spellId);
        }

        // --- tier ---
        int tier = item.Quality switch
        {
            "Normal" => 0,
            "Blessed" => 1,
            "Godly" => 2,
            _ => throw new ArgumentException(),
        };

        return new WikiFancyArmor
        {
            Slot = item.RequiredSlot,
            Relic = item.Relic,
            Str = item.Str,
            End = item.End,
            Dex = item.Dex,
            Agi = item.Agi,
            Int = item.Int,
            Wis = item.Wis,
            Cha = item.Cha,
            Res = item.Res,
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
            ProcDesc = spell == null ? "" : spell.SpellDesc.Trim(),
            ProcChance = item.WeaponProcChance,
            ProcStyle = procStyle,
            Tier = tier,
        };
    }
}