using System.Reflection;
using System.Text.Json;

// Data-only host for the actual export listeners. No Unity editor or game runs.
namespace SQLite
{
    public class TableAttribute(string name) : Attribute { }

    public class IndexedAttribute : Attribute
    {
        public string Name { get; set; }
        public int Order { get; set; }
        public bool Unique { get; set; }
    }

    public class SQLiteConnection
    {
        public void CreateTable<T>() { }

        public void DeleteAll<T>() { }

        public void InsertAll<T>(IEnumerable<T> rows) { }
    }
}

namespace UnityEngine
{
    public static class Debug
    {
        public static void Log(string message) { }
    }
}

public interface IAssetScanListener<T> { }

public class ForeignKeyAttribute(Type type, string field) : Attribute { }

class DuplicateKeyTracker(string owner)
{
    public string GetUniqueKey(string key, string name) => key;
}

public class Item(string key)
{
    public string name = key;
}

public class Vector
{
    public float x,
        y,
        z;
}

public class Transform
{
    public Vector position = new(),
        localScale = new();
}

public class Scene
{
    public string name = "fixture";
}

public class GameObject
{
    public Scene scene = new();
    public string name = "fixture";
}

public class Component
{
    public string name = "fixture";
    public GameObject gameObject = new();
    public Transform transform = new();

    public T GetComponent<T>()
        where T : new() => new();
}

public class Water : Component
{
    public List<Item> DayFishables = new(),
        NightFishables = new();
}

public class MiningNode : Component
{
    public Item guarantee;
    public List<Item> Common = new(),
        Rare = new(),
        Legend = new();
    public float RespawnTime;
}

class NPC
{
    public string NPCName = "deposit";
}

class Manager
{
    public Item GuaranteeMine = new("item:global guarantee");
}

static class GameData
{
    public static Manager GM = new();
}

static class StableKeyGenerator
{
    public static string ForItem(Item item) => item.name;

    public static string ForWater(string scene, float x, float y, float z) => "water:fixture";

    public static string ForMiningNode(string scene, float x, float y, float z) => "mining:fixture";
}

public class ItemRecord { }

public class WaterRecord
{
    public string StableKey,
        Scene;
    public float X,
        Y,
        Z,
        Width,
        Height,
        Depth;
}

class MiningNodeRecord
{
    public string StableKey,
        Scene,
        NPCName;
    public float X,
        Y,
        Z,
        RespawnTime;
}

class MiningNodeItemRecord
{
    public string MiningNodeStableKey { get; set; }
    public string ItemStableKey { get; set; }
    public float DropChance { get; set; }
}

class Program
{
    static object Invoke(Type listener, string method, object asset) =>
        listener
            .GetMethod(method, BindingFlags.NonPublic | BindingFlags.Static)
            .Invoke(null, new[] { asset, "fixture" });

    static List<Item> Pool(string[] keys) =>
        keys.Select(key => key == null ? null : new Item(key)).ToList();

    static string MissingGuaranteeFailure()
    {
        try
        {
            Invoke(typeof(MiningNodeListener), "CreateMiningNodeItemRecords", new MiningNode());
            throw new Exception("Unresolved guarantee did not fail export");
        }
        catch (TargetInvocationException exception)
            when (exception.InnerException is InvalidOperationException)
        {
            return exception.InnerException.Message;
        }
    }

    static void Main()
    {
        string[][] pools =
        [
            [],
            ["item:a"],
            ["item:guarantee"],
            ["item:a", "item:a", null],
            [null],
        ];
        var mining = new List<object>();
        foreach (bool globalGuarantee in new[] { false, true })
        foreach (var common in pools)
        foreach (var rare in pools)
        foreach (var legend in pools)
        {
            var node = new MiningNode
            {
                guarantee = globalGuarantee ? null : new Item("item:guarantee"),
                Common = Pool(common),
                Rare = Pool(rare),
                Legend = Pool(legend),
            };
            mining.Add(
                new
                {
                    guarantee = (node.guarantee ?? GameData.GM.GuaranteeMine).name,
                    common,
                    rare,
                    legend,
                    rows = Invoke(typeof(MiningNodeListener), "CreateMiningNodeItemRecords", node),
                }
            );
        }
        var water = new Water
        {
            DayFishables = Pool(["item:fish", "item:fish", null, "item:gen - torn map top right"]),
        };
        GameData.GM = null;
        var noManagerFailure = MissingGuaranteeFailure();
        var serializedWithoutManager = Invoke(
            typeof(MiningNodeListener),
            "CreateMiningNodeItemRecords",
            new MiningNode { guarantee = new Item("item:serialized guarantee") }
        );
        GameData.GM = new Manager { GuaranteeMine = null };
        var noManagerItemFailure = MissingGuaranteeFailure();
        Console.WriteLine(
            JsonSerializer.Serialize(
                new
                {
                    mining,
                    noManagerFailure,
                    noManagerItemFailure,
                    serializedWithoutManager,
                    water = Invoke(typeof(WaterListener), "CreateWaterFishableRecords", water),
                }
            )
        );
    }
}
