using System.IO;
using SQLite;
using UnityEditor;
using UnityEngine;

public class CharacterDatabaseExporter
{
    [MenuItem("Tools/Export Characters to SQLite DB")]
    public static void ExportCharactersToDB()
    {
        string[] guids = AssetDatabase.FindAssets("t:Prefab", new[] { "Assets/GameObject" });
        if (guids == null || guids.Length == 0)
        {
            Debug.LogWarning("No prefabs found in Assets/GameObject!");
            return;
        }

        string dbPath = Path.Combine(Application.dataPath, "../CharacterDatabase.sqlite");
        var db = new SQLiteConnection(dbPath);
        db.CreateTable<CharacterDBRecord>();
        db.DeleteAll<CharacterDBRecord>();

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
                Invulnerable = character.Invulnerable
            };

            db.InsertOrReplace(record);
            exportedCount++;
        }

        Debug.Log($"Exported {exportedCount} characters to SQLite database at {dbPath}");
    }
}