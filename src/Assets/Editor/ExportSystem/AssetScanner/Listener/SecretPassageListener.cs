using System.Collections.Generic;
using System.Linq;
using SQLite;
using UnityEngine;
using static SecretPassageRecord;

public class SecretPassageListener : IAssetScanListener<GameObject>
{
    private readonly SQLiteConnection _db;
    private readonly List<SecretPassageRecord> _secretPassageRecords = new();

    public SecretPassageListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanFinished()
    {
        _db.CreateTable<SecretPassageRecord>();

        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<SecretPassageRecord>();

            _db.InsertAll(_secretPassageRecords);
        });

        _secretPassageRecords.Clear();
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

        if (colliders.Length == 0 || renderers.Length == 0 || (!enabledCollider && !enabledRenderer))
        {
            return;
        }

        var isHiddenDoor = asset.GetComponent<Door>() && !asset.name.ToLower().Contains("door") && !asset.name.ToLower().Contains("gate");
        var isIllusoryWall = !enabledCollider && enabledRenderer;
        var isInvisibleFloor = enabledCollider && !enabledRenderer;

        SecretPassageType type;
        if (isHiddenDoor)
        {
            type = SecretPassageType.HiddenDoor;
        }
        else if (isIllusoryWall)
        {
            type = SecretPassageType.IllusoryWall;
        }
        else if (isInvisibleFloor)
        {
            type = SecretPassageType.InvisibleFloor;
        }
        else
        {
            return;
        }

        Debug.Log($"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})");

        var position = enabledRenderer ? enabledRenderer.bounds.center : enabledCollider.bounds.center;
        var scene = asset.scene.name;
        var x = position.x;
        var y = position.y;
        var z = position.z;

        var secretPassage = new SecretPassageRecord
        {
            StableKey = StableKeyGenerator.ForSecretPassage(scene, x, y, z),
            Scene = scene,
            X = x,
            Y = y,
            Z = z,
            ObjectName = asset.name,
            Type = type.ToString(),
        };

        _secretPassageRecords.Add(secretPassage);
    }
}
