using System.Collections.Generic;
using SQLite;
using UnityEngine;

public class TeleportLocListener : IAssetScanListener<Object>
{
    private readonly SQLiteConnection _db;
    private readonly List<TeleportRecord> _teleportRecords = new();
    private readonly DuplicateKeyTracker _keyTracker = new("TeleportLocListener");

    public TeleportLocListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanStarted()
    {
        _db.CreateTable<TeleportRecord>();

        _db.DeleteAll<TeleportRecord>();

        _teleportRecords.Clear();

        // Teleport destinations from SpellVessel.cs "Portal to X" cases
        AddTeleport("Windwashed", 755.27f, 66f, 474.4f, "GEN - Rune of Winds");
        AddTeleport("Silkengrass", 188.5f, 63.52f, 712.92f, "GEN - Rune of Silkengrass");
        AddTeleport("Braxonian", 382.6f, 49.3f, 878f, "GEN - Rune of Sands");
        AddTeleport("Soluna", 225f, 77f, 249f, "GEN - Rune of Soluna's Landing");
        AddTeleport("Ripper", 572f, 54.4f, 293f, "GEN - Rune of Ripper's Keep");
        AddTeleport("Hidden", 9.34f, 1f, -114.33f, "GEN - Rune of The Hills");
        AddTeleport("Reliquary", 275f, 1.82f, 309f, "GEN - Box of Portals");
    }

    public void OnScanFinished()
    {
        _db.InsertAll(_teleportRecords);
        _teleportRecords.Clear();
    }

    public void OnAssetFound(Object asset)
    {
        // do nothing
    }

    private void AddTeleport(string scene, float x, float y, float z, string itemResourceName)
    {
        var baseStableKey = StableKeyGenerator.ForTeleport(scene, x, y, z);
        var stableKey = _keyTracker.GetUniqueKey(baseStableKey, scene);

        var teleport = new TeleportRecord
        {
            StableKey = stableKey,
            Scene = scene,
            X = x,
            Y = y,
            Z = z,
            TeleportItemStableKey = StableKeyGenerator.ForItemFromResourceName(itemResourceName),
        };

        _teleportRecords.Add(teleport);
    }
}
