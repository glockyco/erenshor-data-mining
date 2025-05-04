using System;
using System.IO;
using System.Linq;
using SQLite;
using UnityEngine;

public class WikiFancyWeaponFactory
{
    private static readonly string DBPath =
        Path.GetFullPath(Path.Combine(Application.dataPath, "..", "Erenshor.sqlite"));

    public WikiFancyWeapon Create(ItemDBRecord item)
    {
        using var db = new SQLiteConnection(DBPath, SQLiteOpenFlags.ReadOnly);

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
            spell = db.Table<SpellDBRecord>().FirstOrDefault(s => s.Id == spellId);
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
            ProcName = spell == null ? "" : $"[[{spell.SpellName}]]",
            ProcDesc = spell?.SpellDesc,
            ProcChance = item.WeaponProcChance,
            ProcStyle = procStyle,
            Tier = tier,
        };
    }
}