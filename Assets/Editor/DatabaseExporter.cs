using System.IO;
using SQLite;
using UnityEditor;
using UnityEngine;

public class DatabaseExporter
{
    private const string DB_PATH = "../Erenshor.sqlite";
    private const string ITEMS_PATH = "items";
    private const string CHARACTERS_PATH = "Assets/GameObject";

    [MenuItem("Tools/Export/All to SQLite DB")]
    public static void ExportAllToDB()
    {
        string dbPath = Path.Combine(Application.dataPath, DB_PATH);
        var db = new SQLiteConnection(dbPath);

        // Create tables for both types
        db.CreateTable<CharacterDBRecord>();
        db.CreateTable<ItemDBRecord>();

        // Clear existing records
        db.DeleteAll<CharacterDBRecord>();
        db.DeleteAll<ItemDBRecord>();

        // Export both types
        int characterCount = ExportCharacters(db);
        int itemCount = ExportItems(db);

        Debug.Log($"Exported {characterCount} characters and {itemCount} items to SQLite database at {dbPath}");
    }

    [MenuItem("Tools/Export/Characters to SQLite DB")]
    public static void ExportCharactersToDB()
    {
        string dbPath = Path.Combine(Application.dataPath, DB_PATH);
        var db = new SQLiteConnection(dbPath);

        // Create table for characters
        db.CreateTable<CharacterDBRecord>();

        // Clear existing character records
        db.DeleteAll<CharacterDBRecord>();

        // Export characters
        int characterCount = ExportCharacters(db);

        Debug.Log($"Exported {characterCount} characters to SQLite database at {dbPath}");
    }

    [MenuItem("Tools/Export/Items to SQLite DB")]
    public static void ExportItemsToDB()
    {
        string dbPath = Path.Combine(Application.dataPath, DB_PATH);
        var db = new SQLiteConnection(dbPath);

        // Create table for items
        db.CreateTable<ItemDBRecord>();

        // Clear existing item records
        db.DeleteAll<ItemDBRecord>();

        // Export items
        int itemCount = ExportItems(db);

        Debug.Log($"Exported {itemCount} items to SQLite database at {dbPath}");
    }

    private static int ExportCharacters(SQLiteConnection db)
    {
        string[] guids = AssetDatabase.FindAssets("t:Prefab", new[] { CHARACTERS_PATH });
        if (guids == null || guids.Length == 0)
        {
            Debug.LogWarning($"No prefabs found in {CHARACTERS_PATH}!");
            return 0;
        }

        int exportedCount = 0;

        foreach (string guid in guids)
        {
            string assetPath = AssetDatabase.GUIDToAssetPath(guid);
            GameObject prefab = AssetDatabase.LoadAssetAtPath<GameObject>(assetPath);
            if (prefab == null)
                continue;

            Character character = prefab.GetComponent<Character>();
            if (character == null)
                continue;

            var record = new CharacterDBRecord
            {
                PrefabGuid = guid,
                PrefabName = prefab.name,
                MyFaction = (int)character.MyFaction,
                BaseFaction = (int)character.BaseFaction,
                TempFaction = (int)character.TempFaction,
                AggroRange = character.AggroRange,
                Alive = character.Alive,
                isNPC = character.isNPC,
                isVendor = character.isVendor,
                AttackRange = character.AttackRange,
                Invulnerable = character.Invulnerable,
            };

            // Check if the prefab has a Stats component and include stats data if available
            Stats stats = prefab.GetComponent<Stats>();
            if (stats != null)
            {
                record.HasStats = true;
                record.CharacterName = stats.MyName;
                record.Level = stats.Level;
                record.BaseHP = stats.BaseHP;
                record.BaseAC = stats.BaseAC;
                record.BaseMana = stats.BaseMana;
                record.BaseStr = stats.BaseStr;
                record.BaseEnd = stats.BaseEnd;
                record.BaseDex = stats.BaseDex;
                record.BaseAgi = stats.BaseAgi;
                record.BaseInt = stats.BaseInt;
                record.BaseWis = stats.BaseWis;
                record.BaseCha = stats.BaseCha;
                record.BaseRes = stats.BaseRes;
                record.BaseMR = stats.BaseMR;
                record.BaseER = stats.BaseER;
                record.BasePR = stats.BasePR;
                record.BaseVR = stats.BaseVR;
            }

            db.InsertOrReplace(record);
            exportedCount++;
        }

        return exportedCount;
    }

    private static int ExportItems(SQLiteConnection db)
    {
        // Load all Item assets from Resources/items
        Item[] items = Resources.LoadAll<Item>(ITEMS_PATH);
        if (items == null || items.Length == 0)
        {
            Debug.LogWarning($"No items found in Resources/{ITEMS_PATH}!");
            return 0;
        }

        int exportedCount = 0;

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
            };

            db.Insert(record);
            exportedCount++;
        }

        return exportedCount;
    }
}
