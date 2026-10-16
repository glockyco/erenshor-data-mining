#nullable enable

using System;
using System.Collections.Generic;
using System.Linq;
using Newtonsoft.Json;
using SQLite;
using UnityEngine;

public class LootTableListener : IAssetScanListener<LootTable>, IAssetScanListener<GameManager>
{
    private readonly SQLiteConnection _db;
    private readonly CharacterStableKeyResolver _characterKeyResolver;
    private readonly List<Snapshot> _snapshots = new();
    private readonly LootTableProbabilityCalculator _probabilityCalculator = new();
    private readonly Dictionary<string, LootItemInputs> _items = new();
    private List<LootItemInputs> _commonWorldItems = new();
    private int _gameManagerCount;
    private bool _written;

    public LootTableListener(SQLiteConnection db, CharacterStableKeyResolver characterKeyResolver)
    {
        _db = db;
        _characterKeyResolver = characterKeyResolver;
    }

    public void OnAssetFound(GameManager manager)
    {
        _gameManagerCount++;
        if (manager.CommonWorldItems == null)
            throw new InvalidOperationException("GameManager.CommonWorldItems is null");
        _commonWorldItems = LootTableInputs.CaptureItems(manager.CommonWorldItems, _items);
    }

    public void OnAssetFound(LootTable asset)
    {
        var character = asset.GetComponent<Character>();
        if (character == null)
        {
            Debug.LogWarning(
                $"[{GetType().Name}] LootTable on {asset.gameObject.name} has no Character component - skipping"
            );
            return;
        }

        // The scanner closes scenes before OnScanFinished. Retain no scene components.
        _snapshots.Add(
            new Snapshot
            {
                CharacterStableKey = _characterKeyResolver.GetStableKey(character),
                Inputs = new LootTableInputs(asset, _items),
                VisiblePieces = new HashSet<string>(
                    (asset.VisiblePieces ?? new List<Transform>())
                        .Where(piece => piece != null)
                        .Select(piece => piece.name)
                ),
                Zone = asset.ZoneThisLootIsFrom ?? string.Empty,
            }
        );
    }

    public void OnScanFinished()
    {
        // The same listener is registered for two component types.
        if (_written)
            return;
        _written = true;
        if (_gameManagerCount != 1)
            throw new InvalidOperationException(
                $"Expected exactly one GameManager component, found {_gameManagerCount}"
            );
        if (_commonWorldItems.Count == 0)
            throw new InvalidOperationException("GameManager.CommonWorldItems is empty");

        var records = new List<LootTableRecord>();
        var tables = new Dictionary<string, CharacterLootTableRecord>();
        var seen = new HashSet<(string character, string item)>();
        foreach (var snapshot in _snapshots)
        {
            string characterKey = snapshot.CharacterStableKey;
            if (!tables.ContainsKey(characterKey))
                tables[characterKey] = new CharacterLootTableRecord
                {
                    CharacterStableKey = characterKey,
                    NumberOfGuaranteedDrops = snapshot.Inputs.NumberOfGuaranteedDrops,
                };
            else
                Debug.LogWarning(
                    $"[LootTableListener] Second LootTable for '{characterKey}' on {snapshot.Inputs.Name}: keeping the roll count of the first"
                );

            foreach (var record in CreateRecords(snapshot))
            {
                if (seen.Add((record.CharacterStableKey, record.ItemStableKey)))
                    records.Add(record);
                else
                    Debug.LogWarning(
                        $"[LootTableListener] Duplicate loot drop: Character '{characterKey}' dropping Item '{record.ItemStableKey}'. LootTable asset: '{snapshot.Inputs.Name}'. Skipping duplicate."
                    );
            }
        }

        var worldItems = _commonWorldItems
            .Select(
                (item, position) =>
                    new CommonWorldItemRecord
                    {
                        Position = position,
                        ItemStableKey = item?.StableKey,
                    }
            )
            .ToList();
        _db.CreateTable<CommonWorldItemRecord>();
        _db.CreateTable<LootTableRecord>();
        _db.CreateTable<CharacterLootTableRecord>();
        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<CommonWorldItemRecord>();
            _db.DeleteAll<LootTableRecord>();
            _db.DeleteAll<CharacterLootTableRecord>();
            _db.InsertAll(worldItems);
            _db.InsertAll(records);
            _db.InsertAll(tables.Values);
        });
        _snapshots.Clear();
        Debug.Log(
            $"[{GetType().Name}] Wrote {records.Count} loot drops and {worldItems.Count} common world entries"
        );
    }

    private List<LootTableRecord> CreateRecords(Snapshot snapshot)
    {
        var lootTable = snapshot.Inputs;
        var perItemDistributions = _probabilityCalculator.CalculatePerItemDropCountDistributions(
            lootTable,
            _commonWorldItems
        );
        var expectedDrops = _probabilityCalculator.ComputeExpectedDrops(perItemDistributions);
        var records = new List<LootTableRecord>();
        foreach (var item in EnumerateAllUniqueItems(lootTable))
        {
            perItemDistributions.TryGetValue(item.StableKey, out var dist);
            var dropProbability = dist is { Length: > 0 } ? 1.0 - dist[0] : 0.0;
            var dropCountList = new List<DropCountProbability>();
            if (dist != null)
            {
                for (var n = 0; n < dist.Length; ++n)
                {
                    var pct = Math.Round(dist[n] * 100.0, 2);
                    if (pct > 0)
                        dropCountList.Add(
                            new DropCountProbability { Count = n, Chance = $"{pct}%" }
                        );
                }
            }
            records.Add(
                new LootTableRecord
                {
                    CharacterStableKey = snapshot.CharacterStableKey,
                    ItemStableKey = item.StableKey,
                    DropProbability = Math.Round(dropProbability * 100.0, 2),
                    ExpectedPerKill = Math.Round(
                        expectedDrops.GetValueOrDefault(item.StableKey, 0.0),
                        4
                    ),
                    DropCountDistribution = JsonConvert.SerializeObject(dropCountList),
                    IsActual = lootTable.ActualDrops.Contains(item),
                    IsGuaranteed = lootTable.GuaranteeOneDrop.Contains(item),
                    IsCommon = lootTable.CommonDrop.Contains(item),
                    IsCommonWorldItem =
                        lootTable.CommonDrop.Count > 0 && _commonWorldItems.Contains(item),
                    IsUncommon = lootTable.UncommonDrop.Contains(item),
                    IsRare = lootTable.RareDrop.Contains(item),
                    IsLegendary = lootTable.LegendaryDrop.Contains(item),
                    IsUltraRare = lootTable.UltraRareDrop.Contains(item),
                    IsUnique = item.Unique,
                    IsVisible = snapshot.VisiblePieces.Contains(item.EquipmentToActivate),
                    Zone = snapshot.Zone,
                }
            );
        }
        return records;
    }

    private IEnumerable<LootItemInputs> EnumerateAllUniqueItems(LootTableInputs lootTable)
    {
        var seen = new HashSet<string>();
        foreach (
            var list in new[]
            {
                lootTable.UltraRareDrop,
                lootTable.LegendaryDrop,
                lootTable.RareDrop,
                lootTable.UncommonDrop,
                lootTable.CommonDrop,
                lootTable.GuaranteeOneDrop,
                lootTable.ActualDrops,
                lootTable.CommonDrop.Count > 0 ? _commonWorldItems : new List<LootItemInputs>(),
            }
        )
        {
            foreach (var item in list)
            {
                if (item != null && seen.Add(item.StableKey))
                    yield return item;
            }
        }
    }

    private sealed class Snapshot
    {
        public string CharacterStableKey = string.Empty;
        public LootTableInputs Inputs = null!;
        public HashSet<string> VisiblePieces = new();
        public string Zone = string.Empty;
    }

    private class DropCountProbability
    {
        public int Count { get; set; }
        public string Chance { get; set; } = string.Empty;
    }
}
