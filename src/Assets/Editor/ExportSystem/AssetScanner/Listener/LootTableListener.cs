#nullable enable

using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using Newtonsoft.Json;
using SQLite;
using UnityEditor;
using UnityEngine;

public class LootTableListener : IAssetScanListener<LootTable>, IAssetScanListener<GameManager>
{
    private readonly SQLiteConnection _db;
    private readonly CharacterStableKeyResolver _characterKeyResolver;
    private readonly MiningNodeStableKeyResolver _miningNodeKeys;
    private readonly Dictionary<string, Snapshot> _snapshots = new();
    private readonly LootTableProbabilityCalculator _probabilityCalculator = new();
    private readonly Dictionary<string, LootItemInputs> _items = new();
    private List<LootItemInputs> _commonWorldItems = new();
    private int _gameManagerCount;
    private bool _written;

    public LootTableListener(
        SQLiteConnection db,
        CharacterStableKeyResolver characterKeyResolver,
        MiningNodeStableKeyResolver miningNodeKeys
    )
    {
        _db = db;
        _characterKeyResolver = characterKeyResolver;
        _miningNodeKeys = miningNodeKeys;
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
        var miningNode = asset.GetComponent<MiningNode>();
        var components = asset.GetComponents<LootTable>();
        int componentIndex = Array.IndexOf(components, asset);
        if (componentIndex < 0)
            throw new InvalidOperationException(
                $"LootTable '{asset.name}' has no native component index"
            );
        if (character != null && miningNode == null && components.Length != 1)
            throw new InvalidOperationException(
                $"Unsupported LootTable binding for '{_characterKeyResolver.GetStableKey(character)}': "
                    + $"{components.Length} native LootTable components. Runtime GetComponent<LootTable>() "
                    + "does not prove which table supplies this character's loot."
            );

        string? nativeCharacterKey =
            character != null ? _characterKeyResolver.GetStableKey(character) : null;
        string? characterKey = miningNode == null ? nativeCharacterKey : null;
        string sourceKey = SourceKey(asset, nativeCharacterKey, componentIndex);
        // The scanner closes scenes before OnScanFinished. Retain no scene components.
        var snapshot = new Snapshot
        {
            Source = new LootTableSourceRecord
            {
                StableKey = sourceKey,
                CharacterStableKey = characterKey,
                MiningNodeStableKey =
                    miningNode != null ? _miningNodeKeys.GetStableKey(miningNode) : null,
                ComponentIndex = componentIndex,
                ComponentIsEnabled = asset.enabled,
                MaxNumberDrops = asset.MaxNumberDrops,
                MaxNonCommonDrops = asset.MaxNonCommonDrops,
                NumberOfGuaranteedDrops = asset.NumberOfGuaranteedDrops,
                UltraRareDropCount = asset.UltraRareDrop?.Count,
                LegendaryDropCount = asset.LegendaryDrop?.Count,
                RareDropCount = asset.RareDrop?.Count,
                UncommonDropCount = asset.UncommonDrop?.Count,
                CommonDropCount = asset.CommonDrop?.Count,
                GuaranteeOneDropCount = asset.GuaranteeOneDrop?.Count,
                ActualDropsCount = asset.ActualDrops?.Count,
            },
            Inputs = new LootTableInputs(asset, _items),
            Zone = asset.ZoneThisLootIsFrom ?? string.Empty,
        };
        if (asset.VisiblePieces != null)
            foreach (var piece in asset.VisiblePieces)
                if (piece != null)
                    snapshot.VisiblePieces.Add(piece.name);

        if (_snapshots.TryGetValue(sourceKey, out var existing))
        {
            if (!SameSnapshot(existing, snapshot))
                throw new InvalidOperationException(
                    $"Conflicting LootTable definitions for '{sourceKey}'"
                );
            return;
        }
        _snapshots.Add(sourceKey, snapshot);
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
        var sources = new List<LootTableSourceRecord>(_snapshots.Count);
        var slots = new List<LootTablePoolSlotRecord>();
        var characterSources = new Dictionary<string, string>();
        foreach (var snapshot in _snapshots.Values)
        {
            var source = snapshot.Source;
            sources.Add(source);
            AddPoolSlots(
                slots,
                source.StableKey,
                nameof(LootTable.UltraRareDrop),
                snapshot.Inputs.UltraRareDrop
            );
            AddPoolSlots(
                slots,
                source.StableKey,
                nameof(LootTable.LegendaryDrop),
                snapshot.Inputs.LegendaryDrop
            );
            AddPoolSlots(
                slots,
                source.StableKey,
                nameof(LootTable.RareDrop),
                snapshot.Inputs.RareDrop
            );
            AddPoolSlots(
                slots,
                source.StableKey,
                nameof(LootTable.UncommonDrop),
                snapshot.Inputs.UncommonDrop
            );
            AddPoolSlots(
                slots,
                source.StableKey,
                nameof(LootTable.CommonDrop),
                snapshot.Inputs.CommonDrop
            );
            AddPoolSlots(
                slots,
                source.StableKey,
                nameof(LootTable.GuaranteeOneDrop),
                snapshot.Inputs.GuaranteeOneDrop
            );
            AddPoolSlots(
                slots,
                source.StableKey,
                nameof(LootTable.ActualDrops),
                snapshot.Inputs.ActualDrops
            );
            if (source.CharacterStableKey == null)
                continue;
            if (characterSources.TryGetValue(source.CharacterStableKey, out var previousSource))
                throw new InvalidOperationException(
                    $"Unsupported LootTable binding for '{source.CharacterStableKey}': "
                        + $"distinct sources '{previousSource}' and '{source.StableKey}'"
                );
            characterSources.Add(source.CharacterStableKey, source.StableKey);
            records.AddRange(CreateRecords(snapshot));
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
        _db.CreateTable<LootTableSourceRecord>();
        _db.CreateTable<LootTablePoolSlotRecord>();
        _db.CreateTable<LootTableRecord>();
        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<LootTableRecord>();
            _db.DeleteAll<LootTablePoolSlotRecord>();
            _db.DeleteAll<LootTableSourceRecord>();
            _db.DeleteAll<CommonWorldItemRecord>();
            _db.InsertAll(worldItems);
            _db.InsertAll(sources);
            _db.InsertAll(slots);
            _db.InsertAll(records);
        });
        _snapshots.Clear();
        Debug.Log(
            $"[{GetType().Name}] Wrote {sources.Count} loot sources, {slots.Count} pool slots, "
                + $"{records.Count} loot drops and {worldItems.Count} common world entries"
        );
    }

    private List<LootTableRecord> CreateRecords(Snapshot snapshot)
    {
        var lootTable = snapshot.Inputs;
        // code-fact: loot.start_initialization_sequence
        bool initializerRuns = snapshot.Source.ComponentIsEnabled;
        var perItemDistributions = initializerRuns
            ? _probabilityCalculator.CalculatePerItemDropCountDistributions(
                lootTable,
                _commonWorldItems
            )
            : SerializedActualDropDistributions(lootTable);
        var expectedDrops = _probabilityCalculator.ComputeExpectedDrops(perItemDistributions);
        var records = new List<LootTableRecord>();
        foreach (var item in EnumerateAllUniqueItems(lootTable, initializerRuns))
        {
            perItemDistributions.TryGetValue(item.StableKey, out var dist);
            records.Add(
                new LootTableRecord
                {
                    LootTableStableKey = snapshot.Source.StableKey,
                    CharacterStableKey = snapshot.Source.CharacterStableKey!,
                    ItemStableKey = item.StableKey,
                    DropProbability = dist is { Length: > 0 } ? (1.0 - dist[0]) * 100.0 : null,
                    ExpectedPerKill = expectedDrops.TryGetValue(item.StableKey, out var expected)
                        ? expected
                        : null,
                    DropCountDistribution = dist != null ? JsonConvert.SerializeObject(dist) : null,
                    IsActual = lootTable.ActualDrops.Contains(item),
                    IsGuaranteed = lootTable.GuaranteeOneDrop.Contains(item),
                    IsCommon = lootTable.CommonDrop.Contains(item),
                    IsCommonWorldItem =
                        initializerRuns
                        && lootTable.CommonDrop.Count > 0
                        && _commonWorldItems.Contains(item),
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

    private static Dictionary<string, double[]> SerializedActualDropDistributions(
        LootTableInputs inputs
    )
    {
        // Disabled components do not run their Start initializer. Preserve only serialized ActualDrops.
        var counts = new Dictionary<string, int>();
        foreach (var item in inputs.ActualDrops)
        {
            if (item != null)
                counts[item.StableKey] = counts.GetValueOrDefault(item.StableKey) + 1;
        }
        var distributions = new Dictionary<string, double[]>(counts.Count);
        foreach (var pair in counts)
        {
            var distribution = new double[inputs.ActualDrops.Count + 1];
            distribution[pair.Value] = 1.0;
            distributions.Add(pair.Key, distribution);
        }
        return distributions;
    }

    private IEnumerable<LootItemInputs> EnumerateAllUniqueItems(
        LootTableInputs lootTable,
        bool initializerRuns
    )
    {
        var seen = new HashSet<string>();
        if (!initializerRuns)
        {
            foreach (var item in lootTable.ActualDrops)
                if (item != null && seen.Add(item.StableKey))
                    yield return item;
            yield break;
        }
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

    private static string SourceKey(LootTable asset, string? characterKey, int componentIndex)
    {
        string objectKey;
        if (characterKey != null)
            objectKey = characterKey;
        else if (
            asset.gameObject.scene.IsValid() && !PrefabUtility.IsPartOfPrefabAsset(asset.gameObject)
        )
            objectKey = ActivationTargetResolver.ObjectKey(asset.gameObject);
        else if (
            AssetDatabase.TryGetGUIDAndLocalFileIdentifier(
                asset.gameObject,
                out string guid,
                out long localId
            )
        )
            objectKey = "asset:" + guid + ":" + localId.ToString(CultureInfo.InvariantCulture);
        else
            throw new InvalidOperationException(
                $"LootTable '{asset.name}' has no stable scene or asset identity"
            );
        return objectKey
            + ":script:LootTable:"
            + componentIndex.ToString(CultureInfo.InvariantCulture);
    }

    private static void AddPoolSlots(
        List<LootTablePoolSlotRecord> slots,
        string sourceKey,
        string pool,
        List<LootItemInputs> items
    )
    {
        for (int position = 0; position < items.Count; position++)
            slots.Add(
                new LootTablePoolSlotRecord
                {
                    LootTableStableKey = sourceKey,
                    Pool = pool,
                    Position = position,
                    ItemStableKey = items[position]?.StableKey,
                }
            );
    }

    private static bool SameSnapshot(Snapshot left, Snapshot right)
    {
        var a = left.Source;
        var b = right.Source;
        return a.CharacterStableKey == b.CharacterStableKey
            && a.MiningNodeStableKey == b.MiningNodeStableKey
            && a.ComponentIndex == b.ComponentIndex
            && a.ComponentIsEnabled == b.ComponentIsEnabled
            && a.MaxNumberDrops == b.MaxNumberDrops
            && a.MaxNonCommonDrops == b.MaxNonCommonDrops
            && a.NumberOfGuaranteedDrops == b.NumberOfGuaranteedDrops
            && a.UltraRareDropCount == b.UltraRareDropCount
            && a.LegendaryDropCount == b.LegendaryDropCount
            && a.RareDropCount == b.RareDropCount
            && a.UncommonDropCount == b.UncommonDropCount
            && a.CommonDropCount == b.CommonDropCount
            && a.GuaranteeOneDropCount == b.GuaranteeOneDropCount
            && a.ActualDropsCount == b.ActualDropsCount
            && left.Inputs.Name == right.Inputs.Name
            && left.Inputs.UltraRareDrop.SequenceEqual(right.Inputs.UltraRareDrop)
            && left.Inputs.LegendaryDrop.SequenceEqual(right.Inputs.LegendaryDrop)
            && left.Inputs.RareDrop.SequenceEqual(right.Inputs.RareDrop)
            && left.Inputs.UncommonDrop.SequenceEqual(right.Inputs.UncommonDrop)
            && left.Inputs.CommonDrop.SequenceEqual(right.Inputs.CommonDrop)
            && left.Inputs.GuaranteeOneDrop.SequenceEqual(right.Inputs.GuaranteeOneDrop)
            && left.Inputs.ActualDrops.SequenceEqual(right.Inputs.ActualDrops)
            && left.VisiblePieces.SetEquals(right.VisiblePieces)
            && left.Zone == right.Zone;
    }

    private sealed class Snapshot
    {
        public LootTableSourceRecord Source = null!;
        public LootTableInputs Inputs = null!;
        public HashSet<string> VisiblePieces = new();
        public string Zone = string.Empty;
    }
}
