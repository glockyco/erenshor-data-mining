#nullable enable

using System.Collections.Generic;
using System.Linq;
using SQLite;
using UnityEditor;
using UnityEngine;

public class LootTableListener : IAssetScanListener<LootTable>
{
    private readonly SQLiteConnection _db;
    private readonly List<LootTableDBRecord> _records = new();
    private readonly LootTableProbabilityCalculator _probabilityCalculator = new();

    public LootTableListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanFinished()
    {
        _db.CreateTable<LootTableDBRecord>();
        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<LootTableDBRecord>();
            _db.InsertAll(_records);
        });
        _records.Clear();
    }

    public void OnAssetFound(LootTable asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        var records = CreateRecord(asset);

        _records.AddRange(records);
    }

    private List<LootTableDBRecord> CreateRecord(LootTable lootTable)
    {
        Dictionary<string, double> dropProbabilities = _probabilityCalculator.CalculateDropProbabilities(lootTable);

        string guid;
        var prefabType = PrefabUtility.GetPrefabAssetType(lootTable.gameObject);
        if (prefabType != PrefabAssetType.NotAPrefab)
        {
            var prefabPath = AssetDatabase.GetAssetPath(lootTable.gameObject);
            guid = AssetDatabase.AssetPathToGUID(prefabPath);
        }
        else
        {
            var sceneName = lootTable.gameObject.scene.name;
            guid = $"scene:{sceneName}:{lootTable.gameObject.GetInstanceID()}";
        }

        var records = new List<LootTableDBRecord>();
        records.AddRange(CollectLootDrops(lootTable.GuaranteeOneDrop, lootTable.VisiblePieces, "Guaranteed", guid, dropProbabilities));
        records.AddRange(CollectLootDrops(lootTable.CommonDrop, lootTable.VisiblePieces, "Common", guid, dropProbabilities));
        records.AddRange(CollectLootDrops(lootTable.UncommonDrop, lootTable.VisiblePieces, "Uncommon", guid, dropProbabilities));
        records.AddRange(CollectLootDrops(lootTable.RareDrop, lootTable.VisiblePieces, "Rare", guid, dropProbabilities));
        records.AddRange(CollectLootDrops(lootTable.LegendaryDrop, lootTable.VisiblePieces, "Legendary", guid, dropProbabilities));
        records.AddRange(CollectLootDrops(lootTable.ActualDrops, lootTable.VisiblePieces, "Always", guid, dropProbabilities));
        return records;
    }

    private static List<LootTableDBRecord> CollectLootDrops(
        List<Item> items,
        List<Transform> visiblePieces,
        string dropType,
        string guid,
        Dictionary<string, double> dropProbabilities)
    {
        var lootRecords = new List<LootTableDBRecord>();

        for (var i = 0; i < items.Count; i++)
        {
            var item = items[i];
            dropProbabilities.TryGetValue(item.name, out var probability);

            lootRecords.Add(new LootTableDBRecord
            {
                CharacterPrefabGuid = guid,
                ItemId = item.Id,
                DropType = dropType,
                DropIndex = i,
                Probability = probability,
                IsVisible = visiblePieces.Select(t => t.name).Contains(item.EquipmentToActivate)
            });
        }

        return lootRecords;
    }
}