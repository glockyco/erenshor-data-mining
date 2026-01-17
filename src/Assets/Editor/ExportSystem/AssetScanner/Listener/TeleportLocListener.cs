using SQLite;
using UnityEngine;
using static CoordinateRecord;

public class TeleportLocListener : IAssetScanListener<Object>
{
    private readonly SQLiteConnection _db;

    public TeleportLocListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanStarted()
    {
        _db.CreateTable<CoordinateRecord>();
        _db.CreateTable<TeleportRecord>();

        _db.Execute("DELETE FROM Coordinates WHERE Category = ?", nameof(CoordinateCategory.Teleport));
        _db.DeleteAll<TeleportRecord>();

        // Teleport destinations from SpellVessel.cs "Portal to X" cases
        InsertTeleport("Windwashed", 755.27f, 66f, 474.4f, "GEN - Rune of Winds");
        InsertTeleport("Silkengrass", 188.5f, 63.52f, 712.92f, "GEN - Rune of Silkengrass");
        InsertTeleport("Braxonian", 382.6f, 49.3f, 878f, "GEN - Rune of Sands");
        InsertTeleport("Soluna", 225f, 77f, 249f, "GEN - Rune of Soluna's Landing");
        InsertTeleport("Ripper", 572f, 54.4f, 293f, "GEN - Rune of Ripper's Keep");
        InsertTeleport("Hidden", 9.34f, 1f, -114.33f, "GEN - Rune of The Hills");
        InsertTeleport("Reliquary", 275f, 1.82f, 309f, "GEN - Box of Portals");

        _db.Execute(@"
            UPDATE Coordinates
            SET TeleportId = (
                SELECT Id
                FROM Teleports
                WHERE Teleports.CoordinateId = Coordinates.Id
            )
            WHERE EXISTS (
                SELECT 1
                FROM Teleports
                WHERE Teleports.CoordinateId = Coordinates.Id
            );
        ");
    }

    public void OnScanFinished()
    {
        // do nothing
    }

    public void OnAssetFound(Object asset)
    {
        // do nothing
    }

    private void InsertTeleport(string scene, float x, float y, float z, string itemResourceName)
    {
        var coordinate = new CoordinateRecord
        {
            Scene = scene,
            X = x,
            Y = y,
            Z = z,
            Category = nameof(CoordinateCategory.Teleport)
        };

        _db.Insert(coordinate);

        var teleport = new TeleportRecord
        {
            CoordinateId = coordinate.Id,
            TeleportItemStableKey = StableKeyGenerator.ForItemFromResourceName(itemResourceName),
        };

        _db.Insert(teleport);
    }
}
