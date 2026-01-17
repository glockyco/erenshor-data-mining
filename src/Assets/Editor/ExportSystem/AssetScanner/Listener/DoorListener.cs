using System.Collections.Generic;
using SQLite;
using UnityEngine;
using static CoordinateRecord;

public class DoorListener : IAssetScanListener<Door>
{
    private readonly SQLiteConnection _db;
    private readonly List<DoorRecord> _records = new();

    public DoorListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanStarted()
    {
        _db.CreateTable<CoordinateRecord>();
        _db.CreateTable<DoorRecord>();

        _db.Execute("DELETE FROM Coordinates WHERE Category = ?", nameof(CoordinateCategory.Door));
        _db.DeleteAll<DoorRecord>();

        _records.Clear();
    }

    public void OnScanFinished()
    {
        _db.InsertAll(_records);

        _db.Execute(@"
            UPDATE Coordinates
            SET DoorId = (
                SELECT Id
                FROM Doors
                WHERE Doors.CoordinateId = Coordinates.Id
            )
            WHERE EXISTS (
                SELECT 1
                FROM Doors
                WHERE Doors.CoordinateId = Coordinates.Id
            );
        ");

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

        var coordinate = new CoordinateRecord
        {
            Scene = door.gameObject.scene.name,
            X = position.x,
            Y = position.y,
            Z = position.z,
            Category = nameof(CoordinateCategory.Door)
        };

        _db.Insert(coordinate);

        return new DoorRecord
        {
            CoordinateId = coordinate.Id,
            KeyItemStableKey = door.RequiredKey != null
                ? StableKeyGenerator.ForItem(door.RequiredKey)
                : null
        };
    }
}
