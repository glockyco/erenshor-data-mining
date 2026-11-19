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

public class Spell : UnityEngine.Object { }

public class Skill : UnityEngine.Object { }

public class Stance : UnityEngine.Object { }

public class GuildTopic : UnityEngine.Object { }

public class Ascension : UnityEngine.Object { }

public class Quest
{
    public string DBName = "";
}

public class WorldFaction
{
    public string REFNAME = "";
}

public class Character : Component
{
    public Transform transform = new();
}

public class Transform
{
    public (float x, float y, float z) position;
}

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

class Program
{
    static GameObject Prefab(string path, string guid, bool gm, bool rival, long localId = 100) =>
        new GameObject
        {
            name = "SameObjectName",
            Guid = guid,
            Path = path,
            LocalId = localId,
        }
            .Add(new Character())
            .Add(new NPC { NPCName = "SameSaveName" })
            .Add(new Stats())
            .Add(new SimPlayer { IsGMCharacter = gm, Rival = rival })
            .Add(new Inventory { EquippedItems = [new("A"), null, new("A")] });

    static string Failure(params GameObject?[] prefabs)
    {
        var listener = new AuthoredSimListener(new SQLite.SQLiteConnection(), new());
        listener.OnScanStarted();
        try
        {
            listener.OnAssetFound(new SimPlayerMngr { ActualSims = [.. prefabs] });
            return "did not fail";
        }
        catch (InvalidOperationException error)
        {
            return error.Message;
        }
    }

    static void Main()
    {
        var first = Prefab("Assets/Resources/A/Seed.prefab", "guid-a", true, false);
        var second = Prefab("Assets/Resources/B/Seed.prefab", "guid-b", false, true);
        var manager = new SimPlayerMngr { name = "manager:1", ActualSims = [first, second, first] };
        var db = new SQLite.SQLiteConnection();
        var listener = new AuthoredSimListener(db, new());
        listener.OnScanStarted();
        listener.OnAssetFound(manager);
        var prefabManager = new SimPlayerMngr
        {
            ActualSims = [Prefab("Assets/Resources/unplaced.prefab", "unplaced", false, false)],
        };
        prefabManager.gameObject.scene.name = "";
        listener.OnAssetFound(prefabManager);
        listener.OnScanFinished();
        var sims = db.Rows<AuthoredSimRecord>();
        var references = db.Rows<AuthoredSimReferenceRecord>();
        var equipment = db.Rows<AuthoredSimEquipmentRecord>();
        // A new rip changes serialized file identities. Reordering changes reference indices.
        listener.OnScanStarted();
        var rerippedFirst = Prefab(first.Path, "rerip-a", true, false, 901);
        var rerippedSecond = Prefab(second.Path, "rerip-b", false, true, 902);
        manager.ActualSims = [rerippedSecond, rerippedFirst, rerippedFirst];
        listener.OnAssetFound(manager);
        listener.OnScanFinished();
        var missingIdentity = Prefab(first.Path, "", false, false);
        var wrongAsset = Prefab("Assets/Scenes/LoadScene.unity", "guid-scene", false, false);
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
                    reripped = db.Rows<AuthoredSimRecord>(),
                    rerippedReferences = db.Rows<AuthoredSimReferenceRecord>(),
                    failures = new[]
                    {
                        Failure((GameObject?)null),
                        Failure(missingIdentity),
                        Failure(wrongAsset),
                        Failure(missingComponent),
                        Failure(first, rerippedFirst),
                    },
                }
            )
        );
    }
}
