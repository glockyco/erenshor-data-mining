using System.Text.Json;

static object Export(List<Item?> pool, bool mutateAfterCapture = false)
{
    var db = new SQLite.SQLiteConnection();
    var listener = new MiscListener(db);
    listener.OnAssetFound(new Misc { FossilGame = pool });
    if (mutateAfterCapture)
    {
        foreach (var item in pool.Where(item => item != null))
            item!.name = "changed after capture";
        pool.Clear();
    }
    listener.OnScanFinished();
    return new
    {
        pools = db.Rows<ItemDropPoolRecord>(),
        slots = db.Rows<ItemDropPoolSlotRecord>(),
        outcomes = db.Rows<ItemDropRecord>(),
        db.QueryText,
        db.QueryArguments,
        db.CheckedItems,
    };
}

static object Failure(Action<MiscListener, SQLite.SQLiteConnection> scan)
{
    var db = new SQLite.SQLiteConnection();
    var listener = new MiscListener(db);
    try
    {
        scan(listener, db);
        listener.OnScanFinished();
        throw new Exception("Expected invalid producer input to fail");
    }
    catch (Exception error) when (error is InvalidOperationException or KeyNotFoundException)
    {
        return new { error = error.Message, mutations = db.Mutations };
    }
}

static object BindingSnapshot(SQLite.SQLiteConnection db) =>
    new
    {
        bindings = db.Rows<NativeItemBindingRecord>().ToArray(),
        db.CheckedItems,
        db.QueryText,
        db.Tables,
        db.Mutations,
    };

static object ExportBinding(Item? item, bool mutateAfterCapture = false)
{
    var db = new SQLite.SQLiteConnection();
    if (item != null)
        db.ExistingItems.Add(item.name);
    var listener = new GameManagerItemBindingListener(db);
    var host = new UnityEngine.GameObject
    {
        Key = "object:fixture:calibration hall[2]/native host[1]",
    };
    var manager = new GameManager { gameObject = host, PlanarShard = item };
    listener.OnScanStarted();
    listener.OnAssetFound(manager);
    if (mutateAfterCapture)
    {
        item!.name = "mutated item";
        manager.PlanarShard = null;
        manager.gameObject = new UnityEngine.GameObject { Placed = false };
        host.Key = "mutated host";
        host.Placed = false;
    }
    listener.OnScanFinished();
    var writes = db.Mutations;
    listener.OnScanFinished();
    return new { snapshot = BindingSnapshot(db), writesBeforeSecondFinish = writes };
}

static object BindingFailure(Action<GameManagerItemBindingListener, SQLite.SQLiteConnection> scan)
{
    var db = new SQLite.SQLiteConnection();
    var listener = new GameManagerItemBindingListener(db);
    listener.OnScanStarted();
    string? callbackError = null;
    try
    {
        scan(listener, db);
    }
    catch (Exception error) when (error is InvalidOperationException or KeyNotFoundException)
    {
        callbackError = error.Message;
    }
    var finishErrors = new List<string>();
    for (var attempt = 0; attempt < 2; attempt++)
    {
        try
        {
            listener.OnScanFinished();
            throw new Exception("Expected invalid native binding input to fail");
        }
        catch (Exception error) when (error is InvalidOperationException or KeyNotFoundException)
        {
            finishErrors.Add(error.Message);
        }
    }
    var mutationsBeforeReset = db.Mutations;
    var tablesBeforeReset = db.Tables;
    var checkedBeforeReset = db.CheckedItems.ToArray();
    listener.OnScanStarted();
    listener.OnAssetFound(new GameManager { PlanarShard = new Item("item:a") });
    listener.OnScanFinished();
    return new
    {
        callbackError,
        finishErrors,
        mutationsBeforeReset,
        tablesBeforeReset,
        checkedBeforeReset,
        recovered = BindingSnapshot(db),
    };
}

static object ResetBindings()
{
    var db = new SQLite.SQLiteConnection();
    var listener = new GameManagerItemBindingListener(db);
    listener.OnScanStarted();
    // Starting a new scan must discard a captured but unwritten source.
    listener.OnAssetFound(new GameManager { PlanarShard = new Item("item:b") });
    listener.OnScanStarted();
    listener.OnAssetFound(new GameManager { PlanarShard = new Item("item:a") });
    listener.OnScanFinished();
    var first = db.Rows<NativeItemBindingRecord>().ToArray();
    listener.OnScanStarted();
    listener.OnAssetFound(
        new GameManager
        {
            gameObject = new UnityEngine.GameObject { Key = "object:fixture:replacement[3]" },
            PlanarShard = null,
        }
    );
    listener.OnScanFinished();
    var second = db.Rows<NativeItemBindingRecord>().ToArray();
    var writes = db.Mutations;
    listener.OnScanFinished();
    var writesAfterSecondFinish = db.Mutations;
    listener.OnScanStarted();
    string? missingSourceError = null;
    try
    {
        listener.OnScanFinished();
        throw new Exception("Expected a fresh scan without a source to fail");
    }
    catch (InvalidOperationException error)
    {
        missingSourceError = error.Message;
    }
    return new
    {
        first,
        second,
        writesBeforeSecondFinish = writes,
        writesAfterSecondFinish,
        missingSourceError,
        final = BindingSnapshot(db),
    };
}

var bindingFailures = new Dictionary<string, object>
{
    ["missing_source"] = BindingFailure((_, _) => { }),
    ["multiple_sources"] = BindingFailure(
        (listener, _) =>
        {
            listener.OnAssetFound(new GameManager { PlanarShard = new Item("item:a") });
            listener.OnAssetFound(new GameManager { PlanarShard = new Item("item:b") });
        }
    ),
    ["non_scene_source"] = BindingFailure(
        (listener, _) =>
            listener.OnAssetFound(
                new GameManager
                {
                    gameObject = new UnityEngine.GameObject { Placed = false },
                    PlanarShard = new Item("item:a"),
                }
            )
    ),
    ["missing_item"] = BindingFailure(
        (listener, db) =>
        {
            db.ExistingItems.Remove("item:b");
            listener.OnAssetFound(new GameManager { PlanarShard = new Item("item:b") });
        }
    ),
    ["invalid_item_reference"] = BindingFailure(
        (listener, _) =>
            listener.OnAssetFound(
                new GameManager { PlanarShard = new Item("item:a") { FailStableKey = true } }
            )
    ),
};

var resetDb = new SQLite.SQLiteConnection();
var resetListener = new MiscListener(resetDb);
resetListener.OnAssetFound(new Misc { FossilGame = [new("item:a")] });
resetListener.OnScanFinished();
resetListener.OnAssetFound(new Misc { FossilGame = [new("item:b"), null] });
resetListener.OnScanFinished();
var failures = new Dictionary<string, object>
{
    ["missing_source"] = Failure((_, _) => { }),
    ["multiple_sources"] = Failure(
        (listener, _) =>
        {
            listener.OnAssetFound(new Misc { FossilGame = [new("item:a")] });
            listener.OnAssetFound(new Misc { FossilGame = [new("item:b")] });
        }
    ),
    ["null_pool"] = Failure((listener, _) => listener.OnAssetFound(new Misc { FossilGame = null })),
    ["empty_pool"] = Failure((listener, _) => listener.OnAssetFound(new Misc())),
    ["no_click_source"] = Failure(
        (listener, db) =>
        {
            db.Sources.Clear();
            listener.OnAssetFound(new Misc { FossilGame = [new("item:a")] });
        }
    ),
    ["query_failure"] = Failure(
        (listener, db) =>
        {
            db.QueryFailure = true;
            listener.OnAssetFound(new Misc { FossilGame = [new("item:a")] });
        }
    ),
    ["missing_outcome"] = Failure(
        (listener, db) =>
        {
            db.ExistingItems.Remove("item:b");
            listener.OnAssetFound(new Misc { FossilGame = [new("item:a"), new("item:b")] });
        }
    ),
    ["non_scene_source"] = Failure(
        (listener, _) =>
            listener.OnAssetFound(
                new Misc
                {
                    gameObject = new UnityEngine.GameObject { Placed = false },
                    FossilGame = [new("item:a")],
                }
            )
    ),
};
Console.WriteLine(
    JsonSerializer.Serialize(
        new
        {
            weighted = Export([new("item:a"), null, new("item:a"), new("item:b")], true),
            precision = Export([new("item:a"), new("item:b"), new("item:b")]),
            allNull = Export([null, null]),
            reset = new
            {
                pools = resetDb.Rows<ItemDropPoolRecord>(),
                slots = resetDb.Rows<ItemDropPoolSlotRecord>(),
                outcomes = resetDb.Rows<ItemDropRecord>(),
            },
            failures,
            nativeItemBindings = new
            {
                nonNull = ExportBinding(new Item("item:serialized-native-binding")),
                serializedNull = ExportBinding(null),
                capturedSnapshot = ExportBinding(new Item("item:captured-native-binding"), true),
                reset = ResetBindings(),
                failures = bindingFailures,
            },
        }
    )
);

public interface IAssetScanListener<T> { }

public sealed class Item(string key)
{
    public string name = key;
    public bool FailStableKey;
}

public sealed class ItemRecord { }

public sealed class Misc
{
    public UnityEngine.GameObject gameObject = new();
    public List<Item?>? FossilGame = new();
}

public sealed class GameManager
{
    public UnityEngine.GameObject gameObject = new();
    public Item? PlanarShard;
}

public static class StableKeyGenerator
{
    public static string ForItem(Item item) =>
        item.FailStableKey
            ? throw new InvalidOperationException("Fixture item has no stable identity")
            : item.name;
}

public static class ActivationTargetResolver
{
    public static string ObjectKey(UnityEngine.GameObject value) =>
        value.Placed
            ? value.Key
            : throw new InvalidOperationException("Fixture source is not a placed scene object");
}

public sealed class ForeignKeyAttribute(Type type, string column) : Attribute { }

namespace UnityEngine
{
    public sealed class GameObject
    {
        public bool Placed = true;
        public string Key = "object:fixture:misc[0]";
    }

    public static class Debug
    {
        public static void Log(string message) { }
    }
}

namespace SQLite
{
    public sealed class TableAttribute(string name) : Attribute { }

    public sealed class PrimaryKeyAttribute : Attribute { }

    public sealed class IndexedAttribute : Attribute
    {
        public string Name { get; set; } = "";
        public int Order { get; set; }
        public bool Unique { get; set; }
    }

    public sealed class SQLiteConnection
    {
        private readonly Dictionary<Type, object> _rows = new();
        public List<string> Sources = ["item:source-a", "item:source-b"];
        public HashSet<string> ExistingItems = ["item:a", "item:b"];
        public List<string> CheckedItems = new();
        public string QueryText = "";
        public object[] QueryArguments = [];
        public bool QueryFailure;
        public int Mutations;
        public string[] Tables => _rows.Keys.Select(type => type.Name).Order().ToArray();

        public List<T> Query<T>(string sql, params object[] arguments)
        {
            QueryText = sql;
            QueryArguments = arguments;
            if (QueryFailure)
                throw new InvalidOperationException("Fixture query failure");
            return Sources
                .Select(key =>
                {
                    var row = (T)Activator.CreateInstance(typeof(T), nonPublic: true)!;
                    typeof(T).GetProperty("StableKey")!.SetValue(row, key);
                    return row;
                })
                .ToList();
        }

        public T Get<T>(string key)
            where T : new()
        {
            CheckedItems.Add(key);
            if (!ExistingItems.Contains(key))
                throw new KeyNotFoundException("Missing referenced item " + key);
            return new T();
        }

        public void CreateTable<T>()
        {
            _rows.TryAdd(typeof(T), new List<T>());
            Mutations++;
        }

        public void DeleteAll<T>()
        {
            _rows[typeof(T)] = new List<T>();
            Mutations++;
        }

        public void Insert<T>(T row)
        {
            Rows<T>().Add(row);
            Mutations++;
        }

        public void InsertAll<T>(IEnumerable<T> rows)
        {
            Rows<T>().AddRange(rows);
            Mutations++;
        }

        public void RunInTransaction(Action action) => action();

        public List<T> Rows<T>() => (List<T>)_rows[typeof(T)];
    }
}
