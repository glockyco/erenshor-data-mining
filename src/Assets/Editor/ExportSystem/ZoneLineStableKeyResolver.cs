#nullable enable

using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// Centralized resolver for zone line stable keys.
///
/// Multiple listeners need zone line stable keys during the asset scan
/// (ZoneLineListener, QuestActivationListener). When two zone lines share
/// the same base key (identical scene, destination, and coordinates), the
/// key must be deduplicated with a variant suffix (:1, :2, etc.).
///
/// This resolver ensures all listeners agree on the same deduplicated key
/// for a given Zoneline instance. It lazily generates and caches keys on
/// first access, so listeners can call <see cref="GetStableKey"/> in any
/// order during the scan without coordination.
/// </summary>
public class ZoneLineStableKeyResolver
{
    private readonly DuplicateKeyTracker _keyTracker = new("ZoneLineStableKeyResolver");
    private readonly Dictionary<int, string> _keysByInstanceId = new();

    /// <summary>
    /// Returns the deduplicated stable key for a Zoneline.
    ///
    /// On first call for a given instance, generates the base key via
    /// <see cref="StableKeyGenerator.ForZoneLine"/>, deduplicates it,
    /// and caches the result. Subsequent calls return the cached key.
    /// </summary>
    /// <param name="zoneLine">Zoneline component (must not be null)</param>
    /// <returns>Deduplicated stable key (e.g., "zoneline:scene:dest:x:y:z" or "zoneline:scene:dest:x:y:z:1")</returns>
    public string GetStableKey(Zoneline zoneLine)
    {
        var instanceId = zoneLine.GetInstanceID();

        if (_keysByInstanceId.TryGetValue(instanceId, out var cachedKey))
            return cachedKey;

        var sourceScene = zoneLine.gameObject.scene.name;
        var destScene = zoneLine.DestinationZone ?? string.Empty;
        var x = zoneLine.transform.position.x;
        var y = zoneLine.transform.position.y;
        var z = zoneLine.transform.position.z;

        var baseKey = StableKeyGenerator.ForZoneLine(sourceScene, destScene, x, y, z);
        var stableKey = _keyTracker.GetUniqueKey(baseKey, zoneLine.gameObject.name);
        _keysByInstanceId[instanceId] = stableKey;

        return stableKey;
    }
}
