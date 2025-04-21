using System.IO;
using SQLite;
using UnityEditor;
using UnityEngine;

public class ItemDatabaseExporter
{
    [MenuItem("Tools/Export Items to SQLite DB")]
    public static void ExportItemsToDB()
    {
        // Load all Item assets from Resources/items
        Item[] items = Resources.LoadAll<Item>("items");
        if (items == null || items.Length == 0)
        {
            Debug.LogWarning("No items found in Resources/items!");
            return;
        }

        // Set up SQLite DB path
        string dbPath = Path.Combine(Application.dataPath, "../ItemDatabase.sqlite");
        var db = new SQLiteConnection(dbPath);
        db.CreateTable<ItemDBRecord>();

        // Clear existing records
        db.DeleteAll<ItemDBRecord>();

        foreach (var item in items)
        {
            var record = new ItemDBRecord
            {
                Id = item.Id,
                ItemName = item.ItemName,
                ItemLevel = item.ItemLevel,
                HP = item.HP,
                AC = item.AC,
                Mana = item.Mana,
                WeaponDmg = item.WeaponDmg,
                WeaponDly = item.WeaponDly,
                Str = item.Str,
                End = item.End,
                Dex = item.Dex,
                Agi = item.Agi,
                Int = item.Int,
                Wis = item.Wis,
                Cha = item.Cha,
                Res = item.Res,
                MR = item.MR,
                ER = item.ER,
                PR = item.PR,
                VR = item.VR,
                RequiredSlot = (int)item.RequiredSlot,
                ThisWeaponType = (int)item.ThisWeaponType,
                ItemValue = item.ItemValue,
                Lore = item.Lore,
                Shield = item.Shield,
                WeaponProcChance = item.WeaponProcChance,
                SpellCastTime = item.SpellCastTime,
                HideHairWhenEquipped = item.HideHairWhenEquipped,
                HideHeadWhenEquipped = item.HideHeadWhenEquipped,
                Stackable = item.Stackable,
                Disposable = item.Disposable,
                Unique = item.Unique,
                Mining = item.Mining,
                FuelSource = item.FuelSource,
                Template = item.Template,
                SimPlayersCantGet = item.SimPlayersCantGet,
                FuelLevel = (int)item.FuelLevel,
                Relic = item.Relic,
                BookTitle = item.BookTitle
                // Add more fields as needed
            };

            db.Insert(record);
        }

        Debug.Log($"Exported {items.Length} items to SQLite database at {dbPath}");
    }
}
