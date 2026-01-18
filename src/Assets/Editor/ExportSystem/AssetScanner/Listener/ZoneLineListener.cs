using System.Collections.Generic;
using SQLite;
using UnityEngine;

public class ZoneLineListener : IAssetScanListener<Zoneline>
{
    private readonly SQLiteConnection _db;
    private readonly List<ZoneLineRecord> _records = new();
    private readonly DuplicateKeyTracker _keyTracker = new("ZoneLineListener");

    public ZoneLineListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanStarted()
    {
        _db.CreateTable<ZoneLineRecord>();

        _db.DeleteAll<ZoneLineRecord>();

        _records.Clear();
    }

    public void OnScanFinished()
    {
        _db.InsertAll(_records);
        _records.Clear();
    }

    public void OnAssetFound(Zoneline asset)
    {
        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        _records.Add(CreateRecord(asset));
    }

    private ZoneLineRecord CreateRecord(Zoneline zoneLine)
    {
        var sourceScene = zoneLine.gameObject.scene.name;
        var destScene = zoneLine.DestinationZone ?? string.Empty;
        var x = zoneLine.transform.position.x;
        var y = zoneLine.transform.position.y;
        var z = zoneLine.transform.position.z;

        var baseStableKey = StableKeyGenerator.ForZoneLine(sourceScene, destScene, x, y, z);
        var stableKey = _keyTracker.GetUniqueKey(baseStableKey, zoneLine.gameObject.name);

        return new ZoneLineRecord
        {
            StableKey = stableKey,
            Scene = sourceScene,
            X = x,
            Y = y,
            Z = z,
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
