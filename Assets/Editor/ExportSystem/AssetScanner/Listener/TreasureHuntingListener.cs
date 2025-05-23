using System.Collections.Generic;
using System.Linq;
using SQLite;
using UnityEngine;

public class TreasureHuntingListener : IAssetScanListener<TreasureHunting>
{
    private readonly SQLiteConnection _db;
    private readonly List<TreasureHuntingDBRecord> _records = new();

    public TreasureHuntingListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanFinished()
    {
        _db.CreateTable<TreasureHuntingDBRecord>();
        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<TreasureHuntingDBRecord>();
            _db.InsertAll(_records);
        });
        _records.Clear();
    }

    public void OnAssetFound(TreasureHunting asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        _records.AddRange(CreateRecords(asset));
    }

    private List<TreasureHuntingDBRecord> CreateRecords(TreasureHunting treasureHunting)
    {
        return treasureHunting.PossibleZones.Select((zoneName, i) => new TreasureHuntingDBRecord
        {
            ZoneName = zoneName,
            ZoneDisplayName = treasureHunting.ZoneDisplayNames[i],
            IsPickableAlways = i < 3,
            IsPickableGreater20 = i < 6,
            IsPickableGreater30 = i < 9
        }).ToList();
    }
}