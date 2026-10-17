using System.Text.Json;

// The production calculator is linked above; these are only the Unity asset surface it reads.
public class Item
{
    public string name;
    public bool Unique;
    public string EquipmentToActivate = "";

    public Item(string name) => this.name = name;
}

public static class StableKeyGenerator
{
    public static string ForItem(Item item) => item.name;

    // Supply coordinate identity only. Caching and duplicate suffixes use production code.
    public static string ForMiningNode(string scene, float x, float y, float z) =>
        FormattableString.Invariant($"mining:{scene}:{x}:{y}:{z}");
}

public class LootTable : UnityEngine.Component
{
    public string name = "fixture";
    public List<Item> UltraRareDrop = new();
    public List<Item> LegendaryDrop = new();
    public List<Item> RareDrop = new();
    public List<Item> UncommonDrop = new();
    public List<Item> CommonDrop = new();
    public List<Item> GuaranteeOneDrop = new();
    public List<Item> ActualDrops = new();
    public int MaxNumberDrops;
    public int MaxNonCommonDrops;
    public int NumberOfGuaranteedDrops;
    public List<UnityEngine.Transform> VisiblePieces = new();
    public string ZoneThisLootIsFrom = "";
}

namespace UnityEngine
{
    public static class Mathf
    {
        public static int Max(int a, int b) => Math.Max(a, b);
    }
}

public static class Program
{
    private static List<LootTableRecord> ExportListenerRecords(LootTable table)
    {
        var host = new UnityEngine.GameObject();
        host.Add(new Character());
        host.Add(table);
        var db = new SQLite.SQLiteConnection();
        var listener = new LootTableListener(
            db,
            new CharacterStableKeyResolver(),
            new MiningNodeStableKeyResolver()
        );
        listener.OnAssetFound(new GameManager { CommonWorldItems = [new Item("world")] });
        listener.OnAssetFound(table);
        listener.OnScanFinished();
        return db.Rows<LootTableRecord>();
    }

    private static object NativeCapture(bool enabled = false)
    {
        var db = new SQLite.SQLiteConnection();
        var listener = new LootTableListener(
            db,
            new CharacterStableKeyResolver(),
            new MiningNodeStableKeyResolver()
        );
        var worldItem = new Item("snapshot:world");
        var world = new List<Item> { worldItem, null, worldItem };
        listener.OnAssetFound(new GameManager { CommonWorldItems = world });
        var item = new Item("snapshot:item") { Unique = true, EquipmentToActivate = "helmet" };
        var characterHost = new UnityEngine.GameObject();
        characterHost.Add(new Character { StableKey = "character:snapshot" });
        var table = characterHost.Add(
            new LootTable
            {
                enabled = enabled,
                UltraRareDrop = [item, null, item],
                LegendaryDrop = [item, null, item],
                RareDrop = [item, null, item],
                UncommonDrop = [item, null, item],
                CommonDrop = [item, null, item],
                GuaranteeOneDrop = [item, null, item],
                ActualDrops = [item, null, item],
                MaxNumberDrops = 2,
                MaxNonCommonDrops = 1,
                NumberOfGuaranteedDrops = 2,
                VisiblePieces = [new UnityEngine.Transform { name = "helmet" }, null],
                ZoneThisLootIsFrom = "CapturedZone",
            }
        );
        listener.OnAssetFound(table);
        listener.OnAssetFound(table); // Identical scanner callbacks do not duplicate a source.

        // Multiple native tables without a Character remain independent configuration sources.
        var host = new UnityEngine.GameObject { ObjectKey = "object:fixture:unbound[4]" };
        var unbound0 = host.Add(
            new LootTable
            {
                UltraRareDrop = null,
                LegendaryDrop = [],
                RareDrop = null,
                UncommonDrop = [],
                CommonDrop = null,
                GuaranteeOneDrop = [],
                ActualDrops = null,
                MaxNumberDrops = -3,
                MaxNonCommonDrops = -2,
                NumberOfGuaranteedDrops = -1,
            }
        );
        var unbound1 = host.Add(
            new LootTable
            {
                UltraRareDrop = [],
                LegendaryDrop = null,
                RareDrop = [],
                UncommonDrop = null,
                CommonDrop = [],
                GuaranteeOneDrop = null,
                ActualDrops = [new Item("unbound:actual"), null, new Item("unbound:actual")],
                MaxNumberDrops = 7,
                MaxNonCommonDrops = 5,
                NumberOfGuaranteedDrops = 3,
            }
        );
        listener.OnAssetFound(unbound1); // Callback order does not determine component index.
        listener.OnAssetFound(unbound0);
        var prefabHost = new UnityEngine.GameObject
        {
            IsPrefabAsset = true,
            AssetGuid = "fixture-guid",
            LocalId = 42,
        };
        listener.OnAssetFound(
            prefabHost.Add(new LootTable { ActualDrops = [new Item("prefab:actual")] })
        );
        var otherHost = new UnityEngine.GameObject();
        otherHost.Add(new Character { StableKey = "character:other" });
        listener.OnAssetFound(
            otherHost.Add(
                new LootTable { UltraRareDrop = [new Item("other:zero")], MaxNumberDrops = -1 }
            )
        );

        // Mutate all retained Unity inputs and invalidate component lookup before completion.
        item.name = "mutated";
        item.Unique = false;
        item.EquipmentToActivate = "mutated";
        worldItem.name = "mutated world";
        world.Clear();
        table.UltraRareDrop.Clear();
        table.LegendaryDrop = null;
        table.RareDrop.Clear();
        table.UncommonDrop.Clear();
        table.CommonDrop.Clear();
        table.GuaranteeOneDrop.Clear();
        table.ActualDrops.Clear();
        table.VisiblePieces[0].name = "mutated";
        table.VisiblePieces.Clear();
        table.ZoneThisLootIsFrom = "mutated";
        table.MaxNumberDrops = 99;
        table.MaxNonCommonDrops = 99;
        table.NumberOfGuaranteedDrops = 99;
        table.enabled = true;
        characterHost.Unloaded = host.Unloaded = prefabHost.Unloaded = true;
        listener.OnScanFinished();
        listener.OnScanFinished();
        var foreignKey = (ForeignKeyAttribute)
            Attribute.GetCustomAttribute(
                typeof(LootTableRecord).GetProperty(nameof(LootTableRecord.LootTableStableKey)),
                typeof(ForeignKeyAttribute)
            );
        return new
        {
            sources = db.Rows<LootTableSourceRecord>(),
            slots = db.Rows<LootTablePoolSlotRecord>(),
            drops = db.Rows<LootTableRecord>(),
            world = db.Rows<CommonWorldItemRecord>(),
            transactions = db.Transactions,
            dropSourceForeignKey = new
            {
                record = foreignKey.RecordType.Name,
                field = foreignKey.Field,
            },
        };
    }

    private static object MiningCapture()
    {
        var db = new SQLite.SQLiteConnection();
        var keys = new MiningNodeStableKeyResolver();
        keys.Reset();
        var listener = new LootTableListener(db, new CharacterStableKeyResolver(), keys);
        listener.OnAssetFound(new GameManager { CommonWorldItems = [new Item("mining:world")] });
        var identities = new List<object>();
        var hosts = new List<UnityEngine.GameObject>();
        for (int index = 0; index < 2; index++)
        {
            var host = new UnityEngine.GameObject();
            hosts.Add(host);
            // These native Characters have no ordinary CharacterRecord export.
            host.Add(new Character { StableKey = $"native:mining:{index}" });
            var node = host.Add(new MiningNode());
            node.transform.position = new UnityEngine.Vector3(12, 34, 56);
            string key = keys.GetStableKey(node);
            var first = host.Add(
                new LootTable
                {
                    UltraRareDrop = [new Item("mining:random"), null],
                    CommonDrop = [new Item("mining:common")],
                    GuaranteeOneDrop = [new Item("mining:guaranteed")],
                    ActualDrops = [new Item("mining:actual"), null, new Item("mining:actual")],
                    NumberOfGuaranteedDrops = 3,
                    MaxNumberDrops = 4,
                    MaxNonCommonDrops = 2,
                }
            );
            var second = host.Add(
                new LootTable { enabled = false, CommonDrop = [new Item("mining:disabled")] }
            );
            listener.OnAssetFound(second);
            listener.OnAssetFound(first);
            listener.OnAssetFound(first);
            identities.Add(
                new
                {
                    key,
                    repeatedKey = keys.GetStableKey(node),
                    instanceId = node.GetInstanceID(),
                }
            );
        }
        foreach (var host in hosts)
            host.Unloaded = true;
        listener.OnScanFinished();
        var foreignKey = (ForeignKeyAttribute)
            Attribute.GetCustomAttribute(
                typeof(LootTableSourceRecord).GetProperty(
                    nameof(LootTableSourceRecord.MiningNodeStableKey)
                ),
                typeof(ForeignKeyAttribute)
            );
        var characterForeignKey = (ForeignKeyAttribute)
            Attribute.GetCustomAttribute(
                typeof(LootTableSourceRecord).GetProperty(
                    nameof(LootTableSourceRecord.CharacterStableKey)
                ),
                typeof(ForeignKeyAttribute)
            );
        return new
        {
            identities,
            sources = db.Rows<LootTableSourceRecord>(),
            slots = db.Rows<LootTablePoolSlotRecord>(),
            drops = db.Rows<LootTableRecord>(),
            characters = db.Rows<CharacterRecord>(),
            miningForeignKey = new
            {
                record = foreignKey.RecordType.Name,
                field = foreignKey.Field,
            },
            characterForeignKey = new
            {
                record = characterForeignKey.RecordType.Name,
                field = characterForeignKey.Field,
            },
        };
    }

    private static object DisabledCapture()
    {
        var db = new SQLite.SQLiteConnection();
        var listener = new LootTableListener(
            db,
            new CharacterStableKeyResolver(),
            new MiningNodeStableKeyResolver()
        );
        listener.OnAssetFound(new GameManager { CommonWorldItems = [new Item("disabled:global")] });
        var actual = new Item("disabled:actual") { Unique = true };
        foreach (bool preseeded in new[] { true, false })
        {
            var host = new UnityEngine.GameObject();
            host.Add(
                new Character { StableKey = preseeded ? "character:preseeded" : "character:empty" }
            );
            listener.OnAssetFound(
                host.Add(
                    new LootTable
                    {
                        enabled = false,
                        ActualDrops = preseeded
                            ? [actual, null, actual, new Item("disabled:second")]
                            : [],
                        UltraRareDrop = [new Item("disabled:ultra")],
                        LegendaryDrop = [new Item("disabled:legendary")],
                        RareDrop = [new Item("disabled:rare")],
                        UncommonDrop = [new Item("disabled:uncommon")],
                        CommonDrop = [new Item("disabled:common")],
                        GuaranteeOneDrop = [new Item("disabled:guaranteed")],
                        NumberOfGuaranteedDrops = 4,
                        MaxNumberDrops = 5,
                        MaxNonCommonDrops = 3,
                    }
                )
            );
        }
        listener.OnScanFinished();
        return new
        {
            sources = db.Rows<LootTableSourceRecord>(),
            slots = db.Rows<LootTablePoolSlotRecord>(),
            drops = db.Rows<LootTableRecord>(),
            world = db.Rows<CommonWorldItemRecord>(),
        };
    }

    private static object CallbackValidation()
    {
        object Capture(string name, Action<LootTableListener> callbacks)
        {
            var db = new SQLite.SQLiteConnection();
            var listener = new LootTableListener(
                db,
                new CharacterStableKeyResolver(),
                new MiningNodeStableKeyResolver()
            );
            string error = null;
            try
            {
                callbacks(listener);
            }
            catch (InvalidOperationException exception)
            {
                error = exception.Message;
            }
            return new
            {
                name,
                error,
                transactions = db.Transactions,
                sources = db.Rows<LootTableSourceRecord>(),
                drops = db.Rows<LootTableRecord>(),
            };
        }
        return new[]
        {
            Capture("missing_manager", listener => listener.OnScanFinished()),
            Capture(
                "two_managers",
                listener =>
                {
                    listener.OnAssetFound(
                        new GameManager { CommonWorldItems = [new Item("world")] }
                    );
                    listener.OnAssetFound(
                        new GameManager { CommonWorldItems = [new Item("world")] }
                    );
                    listener.OnScanFinished();
                }
            ),
            Capture(
                "null_world",
                listener => listener.OnAssetFound(new GameManager { CommonWorldItems = null })
            ),
            Capture(
                "empty_world",
                listener =>
                {
                    listener.OnAssetFound(new GameManager());
                    listener.OnScanFinished();
                }
            ),
            Capture(
                "ambiguous_character_components",
                listener =>
                {
                    var host = new UnityEngine.GameObject();
                    host.Add(new Character { StableKey = "character:ambiguous" });
                    var first = host.Add(new LootTable());
                    host.Add(new LootTable());
                    listener.OnAssetFound(first);
                }
            ),
            Capture(
                "null_slot_world_completes_once",
                listener =>
                {
                    listener.OnAssetFound(new GameManager { CommonWorldItems = [null] });
                    listener.OnScanFinished();
                    listener.OnScanFinished();
                }
            ),
            Capture(
                "missing_identity",
                listener =>
                {
                    var host = new UnityEngine.GameObject { scene = new UnityEngine.Scene(false) };
                    listener.OnAssetFound(host.Add(new LootTable()));
                }
            ),
            Capture(
                "missing_component_index",
                listener =>
                {
                    listener.OnAssetFound(
                        new LootTable { gameObject = new UnityEngine.GameObject() }
                    );
                }
            ),
            Capture(
                "conflicting_source",
                listener =>
                {
                    var host = new UnityEngine.GameObject();
                    var table = host.Add(new LootTable());
                    listener.OnAssetFound(table);
                    table.CommonDrop = null;
                    listener.OnAssetFound(table);
                }
            ),
        };
    }

    public static void Main()
    {
        var bread = new Item("Bread");
        var water = new Item("Water");
        var rare = new Item("Rare");
        var calculator = new LootTableProbabilityCalculator();
        var scenarios = new List<object>();
        void Add(string name, LootTable table, List<Item> world, bool mutate = false)
        {
            var items = new Dictionary<string, LootItemInputs>();
            var inputs = new LootTableInputs(table, items);
            var capturedWorld = LootTableInputs.CaptureItems(world, items);
            string[][] lists = new[]
            {
                inputs.UltraRareDrop,
                inputs.LegendaryDrop,
                inputs.RareDrop,
                inputs.UncommonDrop,
                inputs.CommonDrop,
            }
                .Select(list => list.Select(item => item?.Name).ToArray())
                .ToArray();
            if (mutate)
            {
                table.CommonDrop[0].name = "changed after snapshot";
                table.CommonDrop.Clear();
                table.MaxNumberDrops = 100;
                table.MaxNonCommonDrops = 100;
            }
            scenarios.Add(
                new
                {
                    name,
                    lists,
                    world = capturedWorld.Select(item => item?.Name).ToArray(),
                    rolls = Math.Max(0, inputs.MaxNumberDrops + 1),
                    cap = inputs.MaxNonCommonDrops,
                    distributions = calculator.CalculatePerItemDropCountDistributions(
                        inputs,
                        capturedWorld
                    ),
                }
            );
        }
        Add(
            "duplicates_nulls_and_combined_item",
            new LootTable
            {
                CommonDrop = new() { bread, bread, null, water },
                MaxNonCommonDrops = 0,
            },
            new() { bread, water, water, null }
        );
        Add(
            "cap_fallthrough",
            new LootTable
            {
                RareDrop = new() { rare },
                CommonDrop = new() { bread },
                MaxNumberDrops = 2,
                MaxNonCommonDrops = 1,
            },
            new() { water }
        );
        Add(
            "overlapping_tiers_do_not_consume_common_cap",
            new LootTable
            {
                UltraRareDrop = new() { bread },
                LegendaryDrop = new() { rare },
                RareDrop = new() { bread, null },
                UncommonDrop = new() { water },
                CommonDrop = new() { bread, rare },
                MaxNumberDrops = 2,
                MaxNonCommonDrops = 1,
            },
            new() { bread, water }
        );
        Add(
            "null_noncommon_consumes_cap",
            new LootTable
            {
                UncommonDrop = new() { null },
                CommonDrop = new() { bread },
                MaxNumberDrops = 1,
                MaxNonCommonDrops = 1,
            },
            new() { water, null }
        );
        Add(
            "no_common_no_world",
            new LootTable
            {
                RareDrop = new() { rare },
                MaxNumberDrops = 2,
                MaxNonCommonDrops = 1,
            },
            new() { water }
        );
        Add(
            "negative_roll_count",
            new LootTable
            {
                CommonDrop = new() { bread },
                MaxNumberDrops = -1,
            },
            new() { water }
        );
        Add(
            "snapshot_survives_source_changes",
            new LootTable
            {
                CommonDrop = new() { bread },
                MaxNumberDrops = 1,
            },
            new() { water },
            mutate: true
        );
        bread.name = "Bread";
        var fixedItems = new Dictionary<string, LootItemInputs>();
        var fixedAndGuaranteed = calculator.CalculatePerItemDropCountDistributions(
            new LootTableInputs(
                new LootTable
                {
                    CommonDrop = new() { bread },
                    ActualDrops = new() { bread },
                    GuaranteeOneDrop = new() { bread },
                    NumberOfGuaranteedDrops = 1,
                },
                fixedItems
            ),
            LootTableInputs.CaptureItems(new[] { bread }, fixedItems)
        );
        var listenerPrecision = ExportListenerRecords(
            new LootTable
            {
                UltraRareDrop = Enumerable
                    .Range(0, 7)
                    .Select(index => new Item($"ultra:{index}"))
                    .ToList(),
                MaxNonCommonDrops = 1,
                ActualDrops = [new Item("fixed")],
            }
        );
        var listenerUnknown = ExportListenerRecords(
            new LootTable
            {
                GuaranteeOneDrop = [new Item("unmodeled")],
                NumberOfGuaranteedDrops = 0,
            }
        );
        var listenerZero = ExportListenerRecords(
            new LootTable { UltraRareDrop = [new Item("known zero")], MaxNumberDrops = -1 }
        );
        Console.WriteLine(
            JsonSerializer.Serialize(
                new
                {
                    scenarios,
                    fixedAndGuaranteed,
                    listenerPrecision,
                    listenerUnknown,
                    listenerZero,
                    nativeCapture = NativeCapture(),
                    enabledNativeCapture = NativeCapture(enabled: true),
                    miningCapture = MiningCapture(),
                    disabledCapture = DisabledCapture(),
                    callbackValidation = CallbackValidation(),
                }
            )
        );
    }
}
