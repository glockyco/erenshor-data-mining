using BepInEx.Logging;
using UnityEngine;

namespace MapTileCapture.Capture;

/// <summary>
/// Static utilities for measuring zone geometry: world bounds, north bearing, roof counts.
/// </summary>
internal static class ZoneBoundsProbe
{
    /// <summary>
    /// Measured axis-aligned bounding box of the zone in world coordinates.
    /// </summary>
    public struct ZoneBounds
    {
        public float MinX;
        public float MinZ;
        public float MaxX;
        public float MaxZ;

        public override string ToString() =>
            $"ZoneBounds(minX={MinX:F1}, minZ={MinZ:F1}, maxX={MaxX:F1}, maxZ={MaxZ:F1})";
    }

    /// <summary>
    /// Measure the world-space bounds of the current scene.
    /// Prefers terrain union; falls back to renderer union if no terrain is active.
    /// </summary>
    public static ZoneBounds MeasureBounds()
    {
        var terrains = UnityEngine.Object.FindObjectsOfType<Terrain>();
        if (terrains.Length > 0)
            return MeasureTerrainBounds(terrains);

        return MeasureRendererBounds();
    }

    /// <summary>
    /// Returns the Y euler angle of the ZoneAnnounce object, which indicates north.
    /// Returns 0 and logs a warning if no ZoneAnnounce is found.
    /// </summary>
    public static float GetNorthBearing(ManualLogSource logger)
    {
        var announce = UnityEngine.Object.FindObjectOfType<ZoneAnnounce>();
        if (announce == null)
        {
            logger.LogWarning("No ZoneAnnounce found in scene — defaulting north bearing to 0");
            return 0f;
        }

        return announce.transform.eulerAngles.y;
    }

    /// <summary>
    /// Count renderers on the "Roof" layer.
    /// </summary>
    public static int CountRoofObjects()
    {
        int roofLayer = LayerMask.NameToLayer("Roof");
        int count = 0;

        foreach (var renderer in UnityEngine.Object.FindObjectsOfType<Renderer>())
        {
            if (renderer.gameObject.layer == roofLayer)
                count++;
        }

        return count;
    }

    private static ZoneBounds MeasureTerrainBounds(Terrain[] terrains)
    {
        float minX = float.MaxValue, minZ = float.MaxValue;
        float maxX = float.MinValue, maxZ = float.MinValue;

        foreach (var terrain in terrains)
        {
            var pos = terrain.transform.position;
            var size = terrain.terrainData.size;

            if (pos.x < minX) minX = pos.x;
            if (pos.z < minZ) minZ = pos.z;
            if (pos.x + size.x > maxX) maxX = pos.x + size.x;
            if (pos.z + size.z > maxZ) maxZ = pos.z + size.z;
        }

        return new ZoneBounds { MinX = minX, MinZ = minZ, MaxX = maxX, MaxZ = maxZ };
    }

    private static ZoneBounds MeasureRendererBounds()
    {
        var renderers = UnityEngine.Object.FindObjectsOfType<Renderer>();
        if (renderers.Length == 0)
            return default;

        float minX = float.MaxValue, minZ = float.MaxValue;
        float maxX = float.MinValue, maxZ = float.MinValue;

        foreach (var renderer in renderers)
        {
            var b = renderer.bounds;
            if (b.min.x < minX) minX = b.min.x;
            if (b.min.z < minZ) minZ = b.min.z;
            if (b.max.x > maxX) maxX = b.max.x;
            if (b.max.z > maxZ) maxZ = b.max.z;
        }

        return new ZoneBounds { MinX = minX, MinZ = minZ, MaxX = maxX, MaxZ = maxZ };
    }
}
