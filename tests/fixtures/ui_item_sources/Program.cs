using System.Collections;
using System.Text.Json;
using UnityEngine;

// Execute the production listener and key generator without loading Unity or the game.
namespace SQLite
{
    public class TableAttribute(string name) : Attribute { }

    public class PrimaryKeyAttribute : Attribute { }

    public class SQLiteConnection
    {
        private readonly Dictionary<Type, IList> _rows = new();

        public void CreateTable<T>() => _rows.TryAdd(typeof(T), new List<T>());

        public void DeleteAll<T>() => _rows[typeof(T)].Clear();

        public void InsertAll<T>(IEnumerable<T> rows)
        {
            foreach (var row in rows)
                _rows[typeof(T)].Add(row);
        }

        public T[] Rows<T>() => _rows[typeof(T)].Cast<T>().ToArray();

        public void RunInTransaction(Action action) => action();
    }
}

namespace UnityEngine
{
    public class Object
    {
        public string name;
    }

    public class Component : Object
    {
        public GameObject gameObject;
        public Transform transform => gameObject.transform;
    }

    public class Transform : Component
    {
        public Transform parent;
        public List<Transform> children = new();
        public Vector3 position = new();
        public int RootIndex;

        public int GetSiblingIndex() => parent == null ? RootIndex : parent.children.IndexOf(this);

        public bool CompareTag(string tag) => gameObject.CompareTag(tag);
    }

    public class Vector3
    {
        public float x,
            y,
            z;
    }

    public class Scene
    {
        public string name;
    }

    public class GameObject : Object
    {
        public Scene scene = new();
        public Transform transform;
        public string tag = "Untagged";
        public bool activeSelf = true;
        public bool activeInHierarchy =>
            activeSelf && (transform.parent?.gameObject.activeInHierarchy ?? true);
        private readonly List<Component> _components = new();

        public GameObject(string name, string scene = "LoadScene", GameObject parent = null)
        {
            this.name = name;
            this.scene.name = scene;
            transform = Add(new Transform { name = name });
            if (parent != null)
            {
                transform.parent = parent.transform;
                parent.transform.children.Add(transform);
            }
        }

        public T Add<T>(T component)
            where T : Component
        {
            component.gameObject = this;
            component.name = name;
            _components.Add(component);
            return component;
        }

        public bool CompareTag(string value) => tag == value;

        public T[] GetComponents<T>() => _components.OfType<T>().ToArray();

        public Component[] GetComponents(Type type) =>
            _components.Where(type.IsInstanceOfType).ToArray();

        public T[] GetComponentsInChildren<T>(bool includeInactive)
        {
            var result = new List<T>();
            if (includeInactive || activeSelf)
            {
                result.AddRange(GetComponents<T>());
                foreach (var child in transform.children)
                    result.AddRange(child.gameObject.GetComponentsInChildren<T>(includeInactive));
            }
            return result.ToArray();
        }
    }
}

public interface IAssetScanListener<T> { }

public class ForeignKeyAttribute(Type type, string field) : Attribute { }

public class ItemRecord { }

public class QuestRecord { }

public class Item(string resourceName) : UnityEngine.Object
{
    public new string name = resourceName;

    public enum SlotType
    {
        General,
        Primary,
    }
}

public class Spell : UnityEngine.Object { }

public class Skill : UnityEngine.Object { }

public class Stance : UnityEngine.Object { }

public class GuildTopic : UnityEngine.Object { }

public class Ascension : UnityEngine.Object { }

public class Quest(string dbName)
{
    public string DBName = dbName;
}

public class WorldFaction
{
    public string REFNAME;
}

public class Character : Component { }

public class Misc : Component
{
    public Item TMOGHIDE;
}

public class ReplenishTMOGHide : Component
{
    public ItemIcon MyIcon;
}

public class PlanningTableUI : Component
{
    public ItemIcon Portal;
}

public class QuestSpawnListener : Component
{
    public Quest Quest,
        ActiveQuest;
    public Item item;
    public List<GameObject> EnableOnQuestComplete = new();
}

public class ItemIcon : Component
{
    public Item MyItem;
    public int Quantity = 1;
    public bool DisplayOnly,
        VendorSlot,
        LootSlot,
        BankSlot,
        MouseSlot,
        PlayerOwned,
        NotInInventory;
    public Item.SlotType ThisSlotType;
}

class Program
{
    static object Sources(bool reverse, bool nullPortal)
    {
        var db = new SQLite.SQLiteConnection();
        var listener = new UiItemSourceListener(db);
        var root = new GameObject("UI");
        var hide = new GameObject("Hide", parent: root);
        var hideIcon = hide.Add(
            new ItemIcon { MyItem = new Item("native serialized seed"), Quantity = 7 }
        );
        hide.Add(new ReplenishTMOGHide { MyIcon = hideIcon });
        var planning = new GameObject("Planning", parent: root);
        var portal = new GameObject("Portal", parent: planning);
        var portalIcon = portal.Add(
            new ItemIcon
            {
                MyItem = nullPortal ? null : new Item("native portal gift"),
                Quantity = 3,
                NotInInventory = true,
                DisplayOnly = true,
                PlayerOwned = true,
            }
        );
        planning.Add(new PlanningTableUI { Portal = portalIcon });
        var misc = new GameObject("Manager");
        misc.Add(new Misc { TMOGHIDE = new Item("native replenishment gift") });
        var objects = new[] { misc, hide, planning };
        listener.OnScanStarted();
        foreach (var asset in reverse ? objects.Reverse() : objects)
            listener.OnAssetFound(asset);
        listener.OnScanFinished();
        return db.Rows<UiItemSourceRecord>();
    }

    static object Access()
    {
        var db = new SQLite.SQLiteConnection();
        var listener = new UiItemSourceListener(db);
        var enabled = new GameObject("Rooms", "Reliquary") { activeSelf = false };
        var desk = new GameObject("Desk", "Reliquary", enabled) { tag = "PlanningDesk" };
        desk.transform.position = new Vector3
        {
            x = 11,
            y = 12,
            z = 13,
        };
        var disabled = new GameObject("Disabled", "Reliquary", enabled) { activeSelf = false };
        var blocked = new GameObject("BlockedDesk", "Reliquary", disabled) { tag = "PlanningDesk" };
        var trigger = new GameObject("QuestTrigger", "Reliquary");
        trigger.Add(
            new QuestSpawnListener
            {
                Quest = new Quest("NATIVECLAIM"),
                ActiveQuest = new Quest("NATIVEALTERNATIVE"),
                item = new Item("native possession key"),
                EnableOnQuestComplete = new() { enabled, enabled },
            }
        );
        listener.OnScanStarted();
        foreach (var asset in new[] { desk, blocked, trigger })
            listener.OnAssetFound(asset);
        listener.OnScanFinished();
        return new
        {
            targets = db.Rows<UiItemAccessTargetRecord>(),
            activations = db.Rows<UiItemAccessActivationRecord>(),
        };
    }

    static object Unrelated()
    {
        var db = new SQLite.SQLiteConnection();
        var listener = new UiItemSourceListener(db);
        var gear = new GameObject("StoredGear");
        gear.Add(new ItemIcon { MyItem = new Item("arbitrary stored equipment") });
        var misc = new GameObject("UnrelatedManager", "OtherScene");
        misc.Add(new Misc());
        listener.OnScanStarted();
        listener.OnAssetFound(gear);
        listener.OnAssetFound(misc);
        listener.OnScanFinished();
        return db.Rows<UiItemSourceRecord>();
    }

    static string Failure(string scenario)
    {
        var db = new SQLite.SQLiteConnection();
        var listener = new UiItemSourceListener(db);
        var hide = new GameObject("Hide");
        var icon = hide.Add(new ItemIcon());
        hide.Add(new ReplenishTMOGHide { MyIcon = scenario == "missing_icon" ? null : icon });
        listener.OnScanStarted();
        try
        {
            listener.OnAssetFound(hide);
            if (scenario == "ambiguous_misc")
            {
                foreach (var name in new[] { "First", "Second" })
                {
                    var misc = new GameObject(name);
                    misc.Add(new Misc { TMOGHIDE = new Item("native gift") });
                    listener.OnAssetFound(misc);
                }
            }
            listener.OnScanFinished();
        }
        catch (InvalidOperationException error)
        {
            return error.Message;
        }
        throw new Exception($"Expected producer rejection for {scenario}");
    }

    static void Main() =>
        Console.WriteLine(
            JsonSerializer.Serialize(
                new
                {
                    forward = Sources(false, false),
                    reverse = Sources(true, false),
                    empty = Sources(false, true),
                    access = Access(),
                    unrelated = Unrelated(),
                    failures = new[]
                    {
                        "missing_icon",
                        "missing_misc",
                        "ambiguous_misc",
                    }.ToDictionary(scenario => scenario, Failure),
                }
            )
        );
}
