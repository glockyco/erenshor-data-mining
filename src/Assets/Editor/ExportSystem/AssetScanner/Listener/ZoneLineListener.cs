using System.Collections.Generic;
using SQLite;
using UnityEngine;

public class ZoneLineListener : IAssetScanListener<Zoneline>
{
    private readonly SQLiteConnection _db;
    private readonly List<ZoneLineRecord> _records = new();
    private readonly ZoneLineStableKeyResolver _keyResolver;

    public ZoneLineListener(SQLiteConnection db, ZoneLineStableKeyResolver keyResolver)
    {
        _db = db;
        _keyResolver = keyResolver;
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
        var stableKey = _keyResolver.GetStableKey(zoneLine);
        var sourceScene = zoneLine.gameObject.scene.name;

        return new ZoneLineRecord
        {
            StableKey = stableKey,
            Scene = sourceScene,
            X = zoneLine.transform.position.x,
            Y = zoneLine.transform.position.y,
            Z = zoneLine.transform.position.z,
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
