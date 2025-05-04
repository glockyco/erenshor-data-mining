using System;
using System.IO;
using System.Linq;
using SQLite;
using UnityEngine;

public class WikiFancyArmorFactory
{
    private static readonly string DBPath =
        Path.GetFullPath(Path.Combine(Application.dataPath, "..", "Erenshor.sqlite"));

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
            ProcName = spell == null ? "" : $"[[{spell.SpellName}]]",
            ProcDesc = spell?.SpellDesc,
            ProcChance = item.WeaponProcChance,
            ProcStyle = procStyle,
            Tier = tier,
        };
    }
}