using System.Collections.Generic;
using System.Linq;
using SQLite;
using UnityEngine;
using static CoordinateRecord;

public class SecretPassageListener : IAssetScanListener<GameObject>
{
    private readonly SQLiteConnection _db;
    private readonly List<SecretPassageRecord> _records = new();

    public SecretPassageListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanStarted()
    {
        _db.CreateTable<CoordinateRecord>();
        _db.CreateTable<SecretPassageRecord>();

        _db.Execute("DELETE FROM Coordinates WHERE Category = ?", nameof(CoordinateCategory.SecretPassage));
        _db.DeleteAll<SecretPassageRecord>();

        _records.Clear();
    }

    public void OnScanFinished()
    {
        _db.InsertAll(_records);

        _db.Execute(@"
            UPDATE Coordinates
            SET SecretPassageId = (
                SELECT Id
                FROM SecretPassages
                WHERE SecretPassages.CoordinateId = Coordinates.Id
            )
            WHERE EXISTS (
                SELECT 1
                FROM SecretPassages
                WHERE SecretPassages.CoordinateId = Coordinates.Id
            );
        ");

        _records.Clear();
    }

    public void OnAssetFound(GameObject asset)
    {
        if (asset.scene.name == null || !asset.activeInHierarchy)
        {
            return;
        }

        if (asset.scene.name is "Menu" or "LoadScene")
        {
            return;
        }

        string[] keywords =
        {
            "ASCHIEVEMENT", "AUDIO", "AggroArea", "BLOCKER", "BonePile", "Bush", "Candle", "Chandelier", "Chess",
            "Cube", "Curtain", "Event", "Flowers", "Furnace", "Halberd", "LOD", "Leaves", "MemorySphere", "Mushroom",
            "Navmesh", "Pickaxe", "Plane", "PlanterBox", "PointOfInterest", "Pole", "Rubble", "SAFESPOT",
            "Shiver Intro", "Spear", "Sphere", "Statue", "Sword", "Torch", "Tree", "Trigger", "Tut", "Tutorial",
            "WATER", "Water", "ZoneLine", "Zoneline", "water", "Bounds", "FishingRod", "Wall_Frame_Curved",
        };
        if (keywords.Any(keyword => asset.name.Contains(keyword)))
        {
            return;
        }

        if (asset.scene.name == "Rockshade" && asset.name == "SM_Bld_Castle_Wall_01 (66)")
        {
            return;
        }

        var colliders = asset.GetComponents<Collider>();
        var noCollisionLayer = LayerMask.NameToLayer("NoCollision");
        var enabledCollider = colliders.FirstOrDefault(c => c.enabled && asset.layer != noCollisionLayer);

        var renderers = asset.GetComponents<Renderer>();
        var enabledRenderer = renderers.FirstOrDefault(r => r.enabled);

        if (
            colliders.Length == 0 ||
            renderers.Length == 0 ||
            (enabledCollider != null && enabledRenderer != null) ||
            (enabledCollider == null && enabledRenderer == null)
        )
        {
            return;
        }

        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        _records.Add(CreateRecord(asset, enabledCollider, enabledRenderer));
    }

    private SecretPassageRecord CreateRecord(GameObject asset, Collider collider, Renderer renderer)
    {
        var position = collider != null ? collider.bounds.center : renderer.bounds.center;

        var coordinate = new CoordinateRecord
        {
            Scene = asset.scene.name,
            X = position.x,
            Y = position.y,
            Z = position.z,
            Category = nameof(CoordinateCategory.SecretPassage)
        };

        _db.Insert(coordinate);

        return new SecretPassageRecord
        {
            CoordinateId = coordinate.Id,
            ObjectName = asset.name
        };
    }
}