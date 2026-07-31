using System;
using System.Collections.Generic;
using System.Linq;
using SQLite;
using UnityEngine;
using static SecretPassageRecord;

public class SecretPassageListener : IAssetScanListener<GameObject>
{
    private readonly SQLiteConnection _db;
    private readonly List<SecretPassageRecord> _secretPassageRecords = new();
    private readonly DuplicateKeyTracker _keyTracker = new("SecretPassageListener");

    private const string NavigationLinkExclusion = "navigation_link";
    private const string EventAnchorExclusion = "event_anchor";
    private const string OffNavMarkerExclusion = "off_nav_marker";
    private const string RoomMarkerExclusion = "room_marker";
    private const string EnvironmentVolumeExclusion = "environment_volume";
    private const string LegacyKeywordExclusion = "legacy_keyword";
    private const string KnownExceptionExclusion = "known_exception";

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

        var exclusionReason = GetExclusionReason(asset.name);
        string[] keywords =
        {
            "ASCHIEVEMENT",
            "AUDIO",
            "AggroArea",
            "BLOCKER",
            "BonePile",
            "Bush",
            "Candle",
            "Chandelier",
            "Chess",
            "Cube",
            "Curtain",
            "Event",
            "Flowers",
            "Furnace",
            "Halberd",
            "LOD",
            "Leaves",
            "MemorySphere",
            "Mushroom",
            "Pickaxe",
            "Plane",
            "PlanterBox",
            "PointOfInterest",
            "Pole",
            "Rubble",
            "SAFESPOT",
            "Shiver Intro",
            "Spear",
            "Sphere",
            "Statue",
            "Sword",
            "Torch",
            "Tree",
            "Trigger",
            "Tut",
            "Tutorial",
            "Water",
            "ZoneLine",
            "Bounds",
            "FishingRod",
            "Wall_Frame_Curved",
        };
        var matchedKeyword = keywords.FirstOrDefault(keyword =>
            asset.name.IndexOf(keyword, StringComparison.OrdinalIgnoreCase) >= 0
        );
        if (exclusionReason is null && matchedKeyword is not null)
        {
            exclusionReason = $"{LegacyKeywordExclusion}:{matchedKeyword}";
        }

        if (asset.scene.name == "Rockshade" && asset.name == "SM_Bld_Castle_Wall_01 (66)")
        {
            exclusionReason ??= KnownExceptionExclusion;
        }

        var colliders = asset.GetComponents<Collider>();
        var noCollisionLayer = LayerMask.NameToLayer("NoCollision");
        var enabledCollider = colliders.FirstOrDefault(c =>
            c.enabled && asset.layer != noCollisionLayer
        );

        var renderers = asset.GetComponents<Renderer>();
        var enabledRenderer = renderers.FirstOrDefault(r => r.enabled);

        if (
            colliders.Length == 0
            || renderers.Length == 0
            || (!enabledCollider && !enabledRenderer)
        )
        {
            return;
        }

        var isHiddenDoor =
            asset.GetComponent<Door>()
            && !asset.name.ToLower().Contains("door")
            && !asset.name.ToLower().Contains("gate");
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

        var isExcluded = exclusionReason is not null;
        if (isExcluded != !string.IsNullOrEmpty(exclusionReason))
        {
            throw new InvalidOperationException("Secret passage exclusion must include a reason");
        }

        Debug.Log(
            isExcluded
                ? $"[{GetType().Name}] Excluded: {asset.name} ({exclusionReason})"
                : $"[{GetType().Name}] Found: {asset.name} ({asset.GetType().Name})"
        );

        var position = enabledRenderer
            ? enabledRenderer.bounds.center
            : enabledCollider.bounds.center;
        var scene = asset.scene.name;
        var x = position.x;
        var y = position.y;
        var z = position.z;

        var baseStableKey = StableKeyGenerator.ForSecretPassage(scene, x, y, z);
        var stableKey = _keyTracker.GetUniqueKey(baseStableKey, asset.name);

        var secretPassage = new SecretPassageRecord
        {
            StableKey = stableKey,
            Scene = scene,
            X = x,
            Y = y,
            Z = z,
            ObjectName = asset.name,
            Type = type.ToString(),
            IsExcluded = isExcluded,
            ExclusionReason = exclusionReason,
        };

        _secretPassageRecords.Add(secretPassage);
    }

    private static string? GetExclusionReason(string objectName)
    {
        var normalized = objectName.Trim();

        if (normalized.StartsWith("NavMeshLink", StringComparison.OrdinalIgnoreCase))
        {
            return NavigationLinkExclusion;
        }

        if (
            normalized.Equals("RAIDWELCOME", StringComparison.OrdinalIgnoreCase)
            || normalized.Equals("ARENA EVENT", StringComparison.OrdinalIgnoreCase)
        )
        {
            return EventAnchorExclusion;
        }

        if (normalized.StartsWith("OFFNAV", StringComparison.OrdinalIgnoreCase))
        {
            return OffNavMarkerExclusion;
        }

        if (IsRoomMarker(normalized))
        {
            return RoomMarkerExclusion;
        }

        if (normalized.Equals("ShiverClouds", StringComparison.OrdinalIgnoreCase))
        {
            return EnvironmentVolumeExclusion;
        }

        return null;
    }

    private static bool IsRoomMarker(string objectName)
    {
        if (
            objectName.Length != 7
            || !objectName.StartsWith("Room ", StringComparison.OrdinalIgnoreCase)
        )
        {
            return false;
        }

        var side = char.ToUpperInvariant(objectName[5]);
        return (side == 'L' || side == 'R') && objectName[6] is >= '1' and <= '4';
    }
}
