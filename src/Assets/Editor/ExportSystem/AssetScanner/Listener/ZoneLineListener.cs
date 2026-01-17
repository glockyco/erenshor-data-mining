using System.Collections.Generic;
using SQLite;
using UnityEngine;
using static CoordinateRecord;

public class ZoneLineListener : IAssetScanListener<Zoneline>
{
    private readonly SQLiteConnection _db;
    private readonly List<ZoneLineRecord> _records = new();

    public ZoneLineListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanStarted()
    {
        _db.CreateTable<CoordinateRecord>();
        _db.CreateTable<ZoneLineRecord>();

        _db.Execute("DELETE FROM Coordinates WHERE Category = ?", nameof(CoordinateCategory.ZoneLine));
        _db.DeleteAll<ZoneLineRecord>();

        _records.Clear();
    }

    public void OnScanFinished()
    {
        _db.InsertAll(_records);

        _db.Execute(@"
            UPDATE Coordinates
            SET ZoneLineId = (
                SELECT Id
                FROM ZoneLines
                WHERE ZoneLines.CoordinateId = Coordinates.Id
            )
            WHERE EXISTS (
                SELECT 1
                FROM ZoneLines
                WHERE ZoneLines.CoordinateId = Coordinates.Id
            );
        ");

        _records.Clear();
    }

    public void OnAssetFound(Zoneline asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        _records.Add(CreateRecord(asset));
    }

    private ZoneLineRecord CreateRecord(Zoneline zoneLine)
    {
        var coordinate = new CoordinateRecord
        {
            Scene = zoneLine.gameObject.scene.name,
            X = zoneLine.transform.position.x,
            Y = zoneLine.transform.position.y,
            Z = zoneLine.transform.position.z,
            Category = nameof(CoordinateCategory.ZoneLine)
        };

        _db.Insert(coordinate);

        return new ZoneLineRecord
        {
            CoordinateId = coordinate.Id,
            IsEnabled = zoneLine.isActiveAndEnabled,
            DisplayText = zoneLine.DisplayText,
            DestinationZoneStableKey = !string.IsNullOrEmpty(zoneLine.DestinationZone)
                ? StableKeyGenerator.ForZoneFromSceneName(zoneLine.DestinationZone)
                : null,
            LandingPositionX = zoneLine.LandingPosition.x,
            LandingPositionY = zoneLine.LandingPosition.y,
            LandingPositionZ = zoneLine.LandingPosition.z,
            RemoveParty = zoneLine.RemoveParty,
        };
    }
}
