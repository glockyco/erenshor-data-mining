#nullable enable

using System;
using System.Collections.Generic;
using System.Linq;
using SQLite;
using UnityEngine;

public class MiningNodeListener : IAssetScanListener<MiningNode>, IAssetScanListener<GameManager>
{
    private readonly SQLiteConnection _db;
    private readonly List<Snapshot> _snapshots = new();
    private readonly MiningNodeStableKeyResolver _miningNodeKeys;
    private string? _fallbackItemStableKey;
    private int _gameManagerCount;
    private bool _written;

    public MiningNodeListener(SQLiteConnection db, MiningNodeStableKeyResolver miningNodeKeys)
    {
        _db = db;
        _miningNodeKeys = miningNodeKeys;
    }

    public void OnScanStarted()
    {
        _snapshots.Clear();
        _miningNodeKeys.Reset();
        _fallbackItemStableKey = null;
        _gameManagerCount = 0;
        _written = false;
    }

    public void OnAssetFound(GameManager manager)
    {
        _gameManagerCount++;
        _fallbackItemStableKey = ItemKey(manager.GuaranteeMine);
    }

    public void OnScanFinished()
    {
        // The same listener is registered for both component types.
        if (_written)
            return;
        _written = true;
        if (_gameManagerCount != 1)
            throw new InvalidOperationException(
                $"Mining export requires exactly one native GameManager component, found {_gameManagerCount}"
            );

        var nodes = new List<MiningNodeRecord>();
        var items = new List<MiningNodeItemRecord>();
        var slots = new List<MiningNodePoolSlotRecord>();
        foreach (var snapshot in _snapshots)
        {
            nodes.Add(snapshot.Node);
            slots.Add(
                new MiningNodePoolSlotRecord
                {
                    MiningNodeStableKey = snapshot.Node.StableKey,
                    Pool = "guarantee",
                    Position = 0,
                    ItemStableKey = snapshot.GuaranteeItemStableKey,
                }
            );
            AddPoolSlots(snapshot.Node.StableKey, "Common", snapshot.Common, slots);
            AddPoolSlots(snapshot.Node.StableKey, "Rare", snapshot.Rare, slots);
            AddPoolSlots(snapshot.Node.StableKey, "Legend", snapshot.Legend, slots);
            items.AddRange(CreateMiningNodeItemRecords(snapshot, _fallbackItemStableKey));
        }

        _db.CreateTable<MiningNodeRecord>();
        _db.CreateTable<MiningNodeItemRecord>();
        _db.CreateTable<MiningNodePoolSlotRecord>();
        _db.CreateTable<MiningFallbackItemRecord>();
        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<MiningNodeItemRecord>();
            _db.DeleteAll<MiningNodePoolSlotRecord>();
            _db.DeleteAll<MiningNodeRecord>();
            _db.DeleteAll<MiningFallbackItemRecord>();
            _db.InsertAll(nodes);
            _db.Insert(
                new MiningFallbackItemRecord
                {
                    SourceKey = MiningFallbackItemRecord.GuaranteeSourceKey,
                    ItemStableKey = _fallbackItemStableKey,
                }
            );
            _db.InsertAll(slots);
            _db.InsertAll(items);
        });
        _snapshots.Clear();
    }

    public void OnAssetFound(MiningNode asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        var scene = asset.gameObject.scene.name;
        var x = asset.transform.position.x;
        var y = asset.transform.position.y;
        var z = asset.transform.position.z;

        var stableKey = _miningNodeKeys.GetStableKey(asset);
        var common = CapturePool(asset.Common);
        var rare = CapturePool(asset.Rare);
        var legend = CapturePool(asset.Legend);

        // Scenes close before OnScanFinished. Keep only serialized values and stable keys.
        _snapshots.Add(
            new Snapshot
            {
                Node = new MiningNodeRecord
                {
                    StableKey = stableKey,
                    Scene = scene,
                    X = x,
                    Y = y,
                    Z = z,
                    NPCName = asset.GetComponent<NPC>().NPCName,
                    RespawnTime = asset.RespawnTime,
                    CommonCount = common?.Length,
                    RareCount = rare?.Length,
                    LegendCount = legend?.Length,
                },
                GuaranteeItemStableKey = ItemKey(asset.guarantee),
                Common = common,
                Rare = rare,
                Legend = legend,
            }
        );
    }

    private static string? ItemKey(Item? item) =>
        item == null ? null : StableKeyGenerator.ForItem(item);

    private static string?[]? CapturePool(List<Item>? pool) => pool?.Select(ItemKey).ToArray();

    private static void AddPoolSlots(
        string nodeKey,
        string poolName,
        string?[]? pool,
        List<MiningNodePoolSlotRecord> slots
    )
    {
        if (pool == null)
            return;
        for (var position = 0; position < pool.Length; position++)
            slots.Add(
                new MiningNodePoolSlotRecord
                {
                    MiningNodeStableKey = nodeKey,
                    Pool = poolName,
                    Position = position,
                    ItemStableKey = pool[position],
                }
            );
    }

    private static List<MiningNodeItemRecord> CreateMiningNodeItemRecords(
        Snapshot snapshot,
        string? fallbackItemStableKey
    )
    {
        // code-fact: mining.outcome_roll
        // code-fact: mining.roll_range
        // Percent per mined node at the standard runtime rate.
        const double guaranteeChance = 20.0;
        const double commonChance = 55.0;
        const double rareChance = 21.0;
        const double legendChance = 4.0;

        var itemTotalDropChances = new Dictionary<string, double>();

        // code-fact: mining.guarantee_fallback
        var guaranteeItemKey = snapshot.GuaranteeItemStableKey ?? fallbackItemStableKey;
        if (guaranteeItemKey == null)
            throw new InvalidOperationException(
                $"Mining node {snapshot.Node.StableKey} requires GameManager.GuaranteeMine because its native guarantee is null, but the captured fallback is null"
            );

        void AddItem(string? itemKey, double chance)
        {
            if (itemKey == null)
                return;
            itemTotalDropChances.TryGetValue(itemKey, out var previousChance);
            itemTotalDropChances[itemKey] = previousChance + chance;
        }

        // code-fact: mining.empty_common_fallback
        // code-fact: mining.empty_rare_fallback
        // code-fact: mining.empty_legend_fallback
        void AddPool(string poolName, string?[]? pool, double chance)
        {
            if (pool == null)
                throw new InvalidOperationException(
                    $"Mining node {snapshot.Node.StableKey} requires a non-null native MiningNode.{poolName} list to derive Mine outcomes"
                );
            if (pool.Length == 0)
            {
                AddItem(guaranteeItemKey, chance);
                return;
            }
            // Null slots retain their share rather than increasing other items' chances.
            var perSlot = chance / pool.Length;
            foreach (var itemKey in pool)
                AddItem(itemKey, perSlot);
        }

        AddItem(guaranteeItemKey, guaranteeChance);
        AddPool("Common", snapshot.Common, commonChance);
        AddPool("Rare", snapshot.Rare, rareChance);
        AddPool("Legend", snapshot.Legend, legendChance);

        return itemTotalDropChances
            .Select(kvp => new MiningNodeItemRecord
            {
                MiningNodeStableKey = snapshot.Node.StableKey,
                ItemStableKey = kvp.Key,
                DropChance = kvp.Value,
            })
            .ToList();
    }

    private sealed class Snapshot
    {
        public MiningNodeRecord Node = null!;
        public string? GuaranteeItemStableKey;
        public string?[]? Common;
        public string?[]? Rare;
        public string?[]? Legend;
    }
}
