using System.Collections.Generic;
using System.Linq;
using SQLite;
using UnityEngine;
using static CoordinateDBRecord;

public class SecretPassageListener : IAssetScanListener<Component>
{
    private readonly SQLiteConnection _db;
    private readonly List<SecretPassageDBRecord> _records = new();
    private readonly HashSet<GameObject> _processedGameObjects = new();

    public SecretPassageListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanStarted()
    {
        _db.CreateTable<CoordinateDBRecord>();
        _db.CreateTable<SecretPassageDBRecord>();

        _db.Execute("DELETE FROM Coordinates WHERE Category = ?", nameof(CoordinateCategory.SecretPassage));
        _db.DeleteAll<SecretPassageDBRecord>();

        _records.Clear();
        _processedGameObjects.Clear();
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

    public void OnAssetFound(Component component)
    {
        if (component.gameObject.scene.name == null || !component.gameObject.activeInHierarchy || _processedGameObjects.Contains(component.gameObject))
        {
            return;
        }

        if (component.gameObject.scene.name is "Menu" or "LoadScene")
        {
            return;
        }

        string[] keywords =
        {
            "ASCHIEVEMENT", "AUDIO", "AggroArea", "BLOCKER", "BonePile", "Bush", "Candle", "Chandelier", "Chess",
            "Cube", "Curtain", "Event", "Flowers", "Furnace", "Halberd", "LOD", "Leaves", "MemorySphere", "Mushroom",
            "Navmesh", "Pickaxe", "Plane", "PlanterBox", "PointOfInterest", "Pole", "Rubble", "SAFESPOT",
            "Shiver Intro", "Spear", "Sphere", "Statue", "Sword", "Torch", "Tree", "Trigger", "Tut", "Tutorial",
            "WATER", "Water", "ZoneLine", "Zoneline", "water", "Bounds", "FishingRod"
        };
        if (keywords.Any(keyword => component.gameObject.name.Contains(keyword)))
        {
            return;
        }

        if (component.gameObject.scene.name == "Rockshade" && component.gameObject.name == "SM_Bld_Castle_Wall_01 (66)")
        {
            return;
        }

        var colliders = component.gameObject.GetComponents<Collider>();
        var enabledCollider = colliders.FirstOrDefault(c => c.enabled);
        
        var renderers = component.gameObject.GetComponents<Renderer>();
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

        Debug.Log($"[{GetType().Name}] Found: {component.name} ({component.GetType().Name})");

        _records.Add(CreateRecord(component, enabledCollider, enabledRenderer));
        _processedGameObjects.Add(component.gameObject);
    }

    private SecretPassageDBRecord CreateRecord(Component component, Collider collider, Renderer renderer)
    {
        var position = collider != null ? collider.bounds.center : renderer.bounds.center;

        var coordinate = new CoordinateDBRecord
        {
            Scene = component.gameObject.scene.name,
            X = position.x,
            Y = position.y,
            Z = position.z,
            Category = nameof(CoordinateCategory.SecretPassage)
        };

        _db.Insert(coordinate);

        return new SecretPassageDBRecord
        {
            CoordinateId = coordinate.Id,
            ObjectName = component.gameObject.name
        };
    }
}