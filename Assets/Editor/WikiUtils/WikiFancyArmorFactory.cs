using System;
using System.IO;
using System.Linq;
using SQLite;
using UnityEngine;

public class WikiFancyArmorFactory
{
    private static readonly string DBPath = Path.GetFullPath(Path.Combine(Application.dataPath, "Erenshor.sqlite"));

    public WikiFancyArmor Create(string wikiString)
    {
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
        armor.ProcChance = WikiTemplateParser.GetNullableFloat(parameters, "proc_chance");
        armor.ProcStyle = WikiTemplateParser.GetString(parameters, "proc_style");

        armor.Tier = WikiTemplateParser.GetInt(parameters, "tier");

        return armor;
    }

    public WikiFancyArmor Create(ItemDBRecord item)
    {
        using var db = new SQLiteConnection(DBPath, SQLiteOpenFlags.ReadOnly);

        // --- proc ---
        string spellId = null;
        string procStyle = "";
        if (!string.IsNullOrEmpty(item.ItemEffectOnClickId))
        {
            spellId = item.ItemEffectOnClickId;
            procStyle = "Activatable";
        }
        else if (!string.IsNullOrEmpty(item.WornEffectId))
        {
            spellId = item.WornEffectId;
            procStyle = "Worn";
        }
        else if (!string.IsNullOrEmpty(item.WeaponProcOnHitId))
        {
            spellId = item.WeaponProcOnHitId;
            procStyle = "Cast";
        }

        SpellDBRecord spell = null;
        if (!string.IsNullOrEmpty(spellId))
        {
            spell = db.Table<SpellDBRecord>().FirstOrDefault(s => s.Id == spellId);
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
            ProcDesc = spell?.SpellDesc,
            ProcChance = item.WeaponProcChance,
            ProcStyle = procStyle,
            Tier = tier,
        };
    }
}
