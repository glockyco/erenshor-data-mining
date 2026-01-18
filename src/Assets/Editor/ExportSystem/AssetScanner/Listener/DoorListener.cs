using System.Collections.Generic;
using SQLite;
using UnityEngine;

public class DoorListener : IAssetScanListener<Door>
{
    private readonly SQLiteConnection _db;
    private readonly List<DoorRecord> _records = new();
    private readonly DuplicateKeyTracker _keyTracker = new("DoorListener");

    public DoorListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanStarted()
    {
        _db.CreateTable<DoorRecord>();

        _db.DeleteAll<DoorRecord>();

        _records.Clear();
    }

    public void OnScanFinished()
    {
        _db.InsertAll(_records);
        _records.Clear();
    }

    public void OnAssetFound(Door asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        _records.Add(CreateRecord(asset));
    }

    private DoorRecord CreateRecord(Door door)
    {
        var renderer = door.GetComponent<Renderer>();
        var position = renderer != null ? renderer.bounds.center : door.transform.position;

        var scene = door.gameObject.scene.name;
        var x = position.x;
        var y = position.y;
        var z = position.z;

        var baseStableKey = StableKeyGenerator.ForDoor(scene, x, y, z);
        var stableKey = _keyTracker.GetUniqueKey(baseStableKey, door.gameObject.name);

        return new DoorRecord
        {
            StableKey = stableKey,
            Scene = scene,
            X = x,
            Y = y,
            Z = z,
            KeyItemStableKey = door.RequiredKey != null
                ? StableKeyGenerator.ForItem(door.RequiredKey)
                : null
        };
    }
}
