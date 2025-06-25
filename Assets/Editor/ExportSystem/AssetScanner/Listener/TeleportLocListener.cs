using SQLite;
using UnityEngine;
using static CoordinateDBRecord;

public class TeleportLocListener : IAssetScanListener<Object>
{
    private readonly SQLiteConnection _db;

    public TeleportLocListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanStarted()
    {
        _db.CreateTable<CoordinateDBRecord>();
        _db.CreateTable<TeleportDBRecord>();
        
        _db.Execute("DELETE FROM Coordinates WHERE Category = ?", nameof(CoordinateCategory.Teleport));
        _db.DeleteAll<TeleportDBRecord>();

        InsertTeleport("Azure", 10.8f, 29.4f, 335.2f, "5016816");
        InsertTeleport("Silkengrass", 188.5f, 63.52f, 712.92f, "71979710");
        InsertTeleport("Braxonian", 382.6f, 49.3f, 878f, "2096280");
        InsertTeleport("Soluna", 225f, 77f, 249f, "5388624");
        InsertTeleport("Ripper", 572f, 54.4f, 293f, "2810120");
        
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
    
    private void InsertTeleport(string scene, float x, float y, float z, string itemId)
    {
        var coordinate = new CoordinateDBRecord
        {
            Scene = scene,
            X = x,
            Y = y,
            Z = z,
            Category = nameof(CoordinateCategory.Teleport)
        };
        
        _db.Insert(coordinate);

        var teleport = new TeleportDBRecord
        {
            CoordinateId = coordinate.Id,
            TeleportItemId = itemId,
        };
        
        _db.Insert(teleport);
    }
}