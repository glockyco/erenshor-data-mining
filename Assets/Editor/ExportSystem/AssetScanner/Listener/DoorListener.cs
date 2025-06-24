using System.Collections.Generic;
using SQLite;
using UnityEngine;
using static CoordinateDBRecord;

public class DoorListener : IAssetScanListener<Door>
{
    private readonly SQLiteConnection _db;
    private readonly List<DoorDBRecord> _records = new();

    public DoorListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanStarted()
    {
        _db.CreateTable<CoordinateDBRecord>();
        _db.CreateTable<DoorDBRecord>();

        _db.Execute("DELETE FROM Coordinates WHERE Category = ?", nameof(CoordinateCategory.Door));
        _db.DeleteAll<DoorDBRecord>();

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

    private DoorDBRecord CreateRecord(Door door)
    {
        var coordinate = new CoordinateDBRecord
        {
            Scene = door.gameObject.scene.name,
            X = door.transform.position.x,
            Y = door.transform.position.y,
            Z = door.transform.position.z,
            Category = nameof(CoordinateCategory.Door)
        };

        _db.Insert(coordinate);

        return new DoorDBRecord
        {
            CoordinateId = coordinate.Id,
            KeyItemId = door.RequiredKey?.Id
        };
    }
}