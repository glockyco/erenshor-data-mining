using System.Text.Json;
using UnityEngine;

namespace SQLite
{
    public class TableAttribute(string name) : Attribute { }

    public class PrimaryKeyAttribute : Attribute { }

    public class IndexedAttribute : Attribute
    {
        public string Name { get; set; } = "";
        public int Order { get; set; }
        public bool Unique { get; set; }
    }

    public class SQLiteConnection
    {
        private readonly Dictionary<Type, object> _rows = new();

        public void CreateTable<T>() { }

        public void DeleteAll<T>() => _rows[typeof(T)] = new List<T>();

        public void InsertAll<T>(IEnumerable<T> rows) => _rows[typeof(T)] = rows.ToList();

        public List<T> Rows<T>() => (List<T>)_rows[typeof(T)];
    }
}

namespace UnityEngine
{
    public class Object
    {
        public string name = "";
    }

    public class Scene
    {
        public string name = "LoadScene",
            path = "Assets/Scenes/LoadScene.unity";
    }

    public class Component : Object
    {
        public GameObject gameObject = new();
    }

    public class GameObject : Object
    {
        private readonly Dictionary<Type, Component> _components = new();
        public Scene scene = new();
        public string Guid = "",
            Path = "";
        public long LocalId = 100;

        public T? GetComponent<T>()
            where T : Component => _components.GetValueOrDefault(typeof(T)) as T;

        public GameObject Add<T>(T component)
            where T : Component
        {
            component.gameObject = this;
            _components[typeof(T)] = component;
            return this;
        }
    }
}

namespace UnityEditor
{
    public static class AssetDatabase
    {
        public static bool TryGetGUIDAndLocalFileIdentifier(
            GameObject asset,
            out string guid,
            out long localId
        )
        {
            guid = asset.Guid;
            localId = asset.LocalId;
            return guid.Length > 0;
        }

        public static string GetAssetPath(GameObject asset) => asset.Path;
    }

    public static class GlobalObjectId
    {
        public static string GetGlobalObjectIdSlow(SimPlayerMngr manager) => manager.name;
    }
}

public interface IAssetScanListener<T> { }

public class Item(string key)
{
    public string name = key;
}

public class Character : Component { }

public class NPC : Component
{
    public string NPCName = "";
}

public class Class
{
    public string ClassName = "Reaver";
}

public class Stats : Component
{
    public Class CharacterClass = new();
    public int Level = 7;
}

public class Inventory : Component
{
    public bool isMale;
    public List<Item?> EquippedItems = new();
}

public class SimPlayer : Component
{
    public float SkillLevel = 42.5f;
    public string HairName = "Hair_A";
    public int HairColor = 2,
        SkinColor = 3;
    public bool IsGMCharacter,
        Rival;
}

public class SimPlayerMngr : Component
{
    public List<GameObject?> ActualSims = new();
    public List<string> NameDatabaseMale = new() { "RandomPoolName" };
}

public class CharacterStableKeyResolver
{
    public string GetStableKey(Character character) => "character:" + character.gameObject.Guid;
}

public static class StableKeyGenerator
{
    public static string ForAuthoredSim(string guid, long id) => $"authored_sim:{guid}:{id}";

    public static string ForItem(Item item) => item.name;
}

class Program
{
    static GameObject Prefab(string guid, bool gm, bool rival) =>
        new GameObject
        {
            name = "SameObjectName",
            Guid = guid,
            Path = $"Assets/Resources/{guid}.prefab",
        }
            .Add(new Character())
            .Add(new NPC { NPCName = "SameSaveName" })
            .Add(new Stats())
            .Add(new SimPlayer { IsGMCharacter = gm, Rival = rival })
            .Add(new Inventory { EquippedItems = [new("item:a"), null, new("item:a")] });

    static string Failure(GameObject? prefab)
    {
        var listener = new AuthoredSimListener(new SQLite.SQLiteConnection(), new());
        listener.OnScanStarted();
        try
        {
            listener.OnAssetFound(new SimPlayerMngr { ActualSims = [prefab] });
            return "did not fail";
        }
        catch (InvalidOperationException error)
        {
            return error.Message;
        }
    }

    static void Main()
    {
        var first = Prefab("guid-a", true, false);
        var second = Prefab("guid-b", false, true);
        _ = Prefab("unused-numbered-template", false, false);
        var manager = new SimPlayerMngr { name = "manager:1", ActualSims = [first, second, first] };
        var db = new SQLite.SQLiteConnection();
        var listener = new AuthoredSimListener(db, new());
        listener.OnScanStarted();
        listener.OnAssetFound(manager);
        var prefabManager = new SimPlayerMngr
        {
            ActualSims = [Prefab("not-scene-authored", false, false)],
        };
        prefabManager.gameObject.scene.name = "";
        listener.OnAssetFound(prefabManager);
        listener.OnScanFinished();
        var sims = db.Rows<AuthoredSimRecord>();
        var references = db.Rows<AuthoredSimReferenceRecord>();
        var equipment = db.Rows<AuthoredSimEquipmentRecord>();
        // Reordering changes source indices, never identity.
        listener.OnScanStarted();
        manager.ActualSims = [second, first, first];
        listener.OnAssetFound(manager);
        listener.OnScanFinished();
        var missingIdentity = Prefab("", false, false);
        var wrongAsset = Prefab("guid-scene", false, false);
        wrongAsset.Path = "Assets/Scenes/LoadScene.unity";
        var missingComponent = new GameObject
        {
            Guid = "no-components",
            Path = "Assets/none.prefab",
        };
        Console.WriteLine(
            JsonSerializer.Serialize(
                new
                {
                    sims,
                    references,
                    equipment,
                    reordered = db.Rows<AuthoredSimRecord>(),
                    failures = new[]
                    {
                        Failure(null),
                        Failure(missingIdentity),
                        Failure(wrongAsset),
                        Failure(missingComponent),
                    },
                }
            )
        );
    }
}
