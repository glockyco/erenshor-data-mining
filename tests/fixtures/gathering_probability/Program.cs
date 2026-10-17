using System.Collections;
using System.Reflection;
using System.Text.Json;

// Data-only host for the production listeners and records. No Unity or game runs.
namespace SQLite
{
    public class TableAttribute(string name) : Attribute { }

    public class PrimaryKeyAttribute : Attribute { }

    public class IndexedAttribute : Attribute
    {
        public string Name { get; set; }
        public int Order { get; set; }
        public bool Unique { get; set; }
    }

    public class SQLiteConnection
    {
        private readonly Dictionary<Type, IList> tables = new();
        public int Mutations { get; private set; }
        public int Transactions { get; private set; }

        public List<T> Rows<T>()
        {
            if (!tables.TryGetValue(typeof(T), out var rows))
                tables[typeof(T)] = rows = new List<T>();
            return (List<T>)rows;
        }

        public void CreateTable<T>()
        {
            Mutations++;
            Rows<T>();
        }

        public void DeleteAll<T>()
        {
            Mutations++;
            Rows<T>().Clear();
        }

        public void InsertAll<T>(IEnumerable<T> rows)
        {
            Mutations++;
            Rows<T>().AddRange(rows);
        }

        public void Insert<T>(T row)
        {
            Mutations++;
            Rows<T>().Add(row);
        }

        public void RunInTransaction(Action action)
        {
            Transactions++;
            action();
        }
    }
}

namespace UnityEngine
{
    public static class Debug
    {
        public static void Log(string message) { }

        public static void LogWarning(string message) { }
    }
}

public interface IAssetScanListener<T>
{
    void OnScanStarted();
    void OnAssetFound(T asset);
    void OnScanFinished();
}

public class ForeignKeyAttribute(Type type, string field) : Attribute { }

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
    private static int nextInstanceId;
    private readonly int instanceId = ++nextInstanceId;

    public int GetInstanceID() => instanceId;

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

public class GameManager : Component
{
    public Item GuaranteeMine = new("item:global guarantee");
}

class NPC
{
    public string NPCName = "deposit";
}

static class StableKeyGenerator
{
    public static string ForItem(Item item) => item.name;

    public static string ForWater(string scene, float x, float y, float z) => "fixture";

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

class MiningCapture
{
    public List<MiningNodeRecord> nodes { get; init; }
    public List<MiningNodeItemRecord> rows { get; init; }
    public List<MiningNodePoolSlotRecord> slots { get; init; }
    public List<MiningFallbackItemRecord> fallback { get; init; }
    public int mutations { get; init; }
    public int transactions { get; init; }
    public int afterFirstFinish { get; init; }
}

class Program
{
    static List<Item> Pool(string[] keys) =>
        keys?.Select(key => key == null ? null : new Item(key)).ToList();

    static MiningCapture Capture(SQLite.SQLiteConnection db, int afterFirstFinish) =>
        new()
        {
            nodes = db.Rows<MiningNodeRecord>().ToList(),
            rows = db.Rows<MiningNodeItemRecord>().ToList(),
            slots = db.Rows<MiningNodePoolSlotRecord>().ToList(),
            fallback = db.Rows<MiningFallbackItemRecord>().ToList(),
            mutations = db.Mutations,
            transactions = db.Transactions,
            afterFirstFinish = afterFirstFinish,
        };

    static MiningCapture Export(
        MiningNode node,
        GameManager manager,
        bool managerFirst = false,
        bool unload = false
    )
    {
        var db = new SQLite.SQLiteConnection();
        var listener = new MiningNodeListener(db, new MiningNodeStableKeyResolver());
        IAssetScanListener<MiningNode> nodes = listener;
        IAssetScanListener<GameManager> managers = listener;
        nodes.OnScanStarted();
        managers.OnScanStarted();
        if (managerFirst)
            managers.OnAssetFound(manager);
        nodes.OnAssetFound(node);
        if (!managerFirst)
            managers.OnAssetFound(manager);
        if (unload)
        {
            foreach (var pool in new[] { node.Common, node.Rare, node.Legend })
            {
                if (pool == null)
                    continue;
                foreach (var item in pool.Where(item => item != null))
                    item.name = "item:mutated";
                pool.Clear();
            }
            if (node.guarantee != null)
                node.guarantee.name = "item:mutated guarantee";
            if (manager.GuaranteeMine != null)
                manager.GuaranteeMine.name = "item:mutated fallback";
            node.Common = node.Rare = node.Legend = null;
            node.guarantee = manager.GuaranteeMine = null;
            node.gameObject = manager.gameObject = null;
            node.transform = manager.transform = null;
            node.RespawnTime = -1;
        }
        if (managerFirst)
            managers.OnScanFinished();
        else
            nodes.OnScanFinished();
        var first = db.Mutations;
        if (managerFirst)
            nodes.OnScanFinished();
        else
            managers.OnScanFinished();
        return Capture(db, first);
    }

    static object Failure(MiningNode node, params GameManager[] managers)
    {
        var db = new SQLite.SQLiteConnection();
        var listener = new MiningNodeListener(db, new MiningNodeStableKeyResolver());
        listener.OnScanStarted();
        foreach (var manager in managers)
            listener.OnAssetFound(manager);
        listener.OnAssetFound(node);
        // Failed derivation never inserts rows. Observe the real captured record to
        // distinguish original null lists from empty lists before finalization.
        var snapshots = (IEnumerable)
            typeof(MiningNodeListener)
                .GetField("_snapshots", BindingFlags.NonPublic | BindingFlags.Instance)
                .GetValue(listener);
        var captured = snapshots
            .Cast<object>()
            .Select(snapshot =>
                (MiningNodeRecord)snapshot.GetType().GetField("Node").GetValue(snapshot)
            )
            .ToList();
        try
        {
            listener.OnScanFinished();
            throw new Exception("Expected invalid native mining input to fail");
        }
        catch (InvalidOperationException error)
        {
            // The shared listener marks finalization attempted before validating.
            listener.OnScanFinished();
            return new
            {
                error = error.Message,
                captured,
                output = Capture(db, db.Mutations),
            };
        }
    }

    static object SharedIdentity()
    {
        var db = new SQLite.SQLiteConnection();
        var resolver = new MiningNodeStableKeyResolver();
        var listener = new MiningNodeListener(db, resolver);
        IAssetScanListener<MiningNode> nodes = listener;
        IAssetScanListener<GameManager> managers = listener;
        var first = new MiningNode();
        var second = new MiningNode();
        var third = new MiningNode();
        var control = new MiningNodeStableKeyResolver();
        var expected = new[] { first, second, third }.Select(control.GetStableKey).ToArray();
        var rounds = new List<object>();
        foreach (
            var order in new[] { new[] { first, second, third }, new[] { third, second, first } }
        )
        {
            // Both scan starts precede discovery, as in the production scanner.
            nodes.OnScanStarted();
            managers.OnScanStarted();
            managers.OnAssetFound(new GameManager());
            var before = new List<string>();
            var repeated = new List<string>();
            var afterCapture = new List<string>();
            foreach (var node in order)
            {
                // A dependent consumer can discover the host before its own listener.
                before.Add(resolver.GetStableKey(node));
                repeated.Add(resolver.GetStableKey(node));
                repeated.Add(resolver.GetStableKey(node));
                nodes.OnAssetFound(node);
                afterCapture.Add(resolver.GetStableKey(node));
            }
            nodes.OnScanFinished();
            var firstFinish = db.Mutations;
            managers.OnScanFinished();
            var afterFinish = order.Select(resolver.GetStableKey).ToArray();
            rounds.Add(
                new
                {
                    before,
                    repeated,
                    afterCapture,
                    afterFinish,
                    output = Capture(db, firstFinish),
                }
            );
        }
        // Reset also clears the instance cache, not only the duplicate counter.
        resolver.Reset();
        var afterReset = new[] { first, second, third }.Select(resolver.GetStableKey).ToArray();
        return new
        {
            expected,
            rounds,
            afterReset,
        };
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
            var output = Export(node, new GameManager(), mining.Count % 2 == 0);
            mining.Add(
                new
                {
                    guarantee = globalGuarantee ? "item:global guarantee" : "item:guarantee",
                    nativeGuarantee = globalGuarantee ? null : "item:guarantee",
                    common,
                    rare,
                    legend,
                    output.rows,
                    output.nodes,
                    output.slots,
                    output.fallback,
                    output.mutations,
                    output.transactions,
                    output.afterFirstFinish,
                }
            );
        }
        MiningNode NativeNode() =>
            new()
            {
                guarantee = new("item:native guarantee"),
                RespawnTime = 73.5f,
                Common = Pool(["item:a", null, "item:a", "item:b", "item:c", "item:d", "item:e"]),
                Rare = Pool(["item:rare", null, "item:rare"]),
                Legend = Pool(["item:legend", "item:a", null]),
            };
        var failures = new Dictionary<string, object>
        {
            ["missing_manager"] = Failure(
                new MiningNode { guarantee = new("item:serialized guarantee") }
            ),
            ["multiple_managers"] = Failure(
                new MiningNode { guarantee = new("item:serialized guarantee") },
                new GameManager(),
                new GameManager()
            ),
            ["null_fallback_required"] = Failure(
                new MiningNode(),
                new GameManager { GuaranteeMine = null }
            ),
            ["null_common"] = Failure(
                new MiningNode { Common = null, guarantee = new("item:guarantee") },
                new GameManager()
            ),
            ["null_rare"] = Failure(
                new MiningNode { Rare = null, guarantee = new("item:guarantee") },
                new GameManager()
            ),
            ["null_legend"] = Failure(
                new MiningNode { Legend = null, guarantee = new("item:guarantee") },
                new GameManager()
            ),
            ["all_null_lists"] = Failure(
                new MiningNode
                {
                    Common = null,
                    Rare = null,
                    Legend = null,
                    guarantee = new("item:guarantee"),
                },
                new GameManager()
            ),
        };
        var waterDb = new SQLite.SQLiteConnection();
        var waterListener = new WaterListener(waterDb);
        waterListener.OnScanStarted();
        waterListener.OnAssetFound(
            new Water
            {
                DayFishables = Pool([
                    "item:fish",
                    "item:fish",
                    null,
                    "item:gen - torn map top right",
                ]),
                NightFishables = Pool([null, "item:night fish", "item:gen - torn map top right"]),
            }
        );
        waterListener.OnScanFinished();
        var resetDb = new SQLite.SQLiteConnection();
        var resetListener = new MiningNodeListener(resetDb, new MiningNodeStableKeyResolver());
        resetListener.OnScanStarted();
        resetListener.OnAssetFound(new GameManager());
        resetListener.OnAssetFound(NativeNode());
        resetListener.OnScanFinished();
        resetListener.OnScanStarted();
        resetListener.OnAssetFound(new MiningNode());
        resetListener.OnAssetFound(new GameManager { GuaranteeMine = new("item:reset fallback") });
        resetListener.OnScanFinished();
        var resetFirst = resetDb.Mutations;
        resetListener.OnScanFinished();
        Console.WriteLine(
            JsonSerializer.Serialize(
                new
                {
                    mining,
                    failures,
                    sharedIdentity = SharedIdentity(),
                    native = Export(NativeNode(), new GameManager(), unload: true),
                    nativeManagerFirst = Export(
                        NativeNode(),
                        new GameManager(),
                        managerFirst: true,
                        unload: true
                    ),
                    serializedWithNullFallback = Export(
                        new MiningNode { guarantee = new("item:serialized guarantee") },
                        new GameManager { GuaranteeMine = null }
                    ),
                    fallbackSnapshot = Export(new MiningNode(), new GameManager(), unload: true),
                    reset = Capture(resetDb, resetFirst),
                    water = waterDb.Rows<WaterFishableRecord>(),
                }
            )
        );
    }
}
