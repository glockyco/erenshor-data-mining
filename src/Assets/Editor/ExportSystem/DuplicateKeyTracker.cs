#nullable enable

using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// Tracks and assigns unique variant indices to duplicate stable keys.
///
/// When multiple entities share the same coordinate-based stable key (e.g.,
/// multiple spawn points at identical positions), this class appends variant
/// indices (:1, :2, etc.) to ensure uniqueness.
/// </summary>
public class DuplicateKeyTracker
{
    private readonly string _listenerName;
    private readonly Dictionary<string, int> _counters = new();

    public DuplicateKeyTracker(string listenerName)
    {
        _listenerName = listenerName;
    }

    /// <summary>
    /// Creates a tracker pre-seeded with existing keys.
    /// Useful when appending to an existing table to avoid key collisions.
    /// </summary>
    /// <param name="listenerName">Name for logging</param>
    /// <param name="existingKeys">Set of keys already in use</param>
    public DuplicateKeyTracker(string listenerName, IEnumerable<string> existingKeys)
    {
        _listenerName = listenerName;

        // Parse existing keys to initialize counters
        foreach (var key in existingKeys)
        {
            // Check if key has variant suffix (e.g., "base:1", "base:2")
            var lastColonIndex = key.LastIndexOf(':');
            if (lastColonIndex > 0 && int.TryParse(key.Substring(lastColonIndex + 1), out var variant))
            {
                // Key has variant - extract base key
                var baseKey = key.Substring(0, lastColonIndex);
                if (!_counters.TryGetValue(baseKey, out var currentMax) || variant > currentMax)
                {
                    _counters[baseKey] = variant;
                }
            }
            else
            {
                // Key has no variant - mark base as used (counter = 0)
                if (!_counters.ContainsKey(key))
                {
                    _counters[key] = 0;
                }
            }
        }
    }

    /// <summary>
    /// Returns a unique stable key by appending variant index if needed.
    /// </summary>
    /// <param name="baseKey">Base stable key (e.g., spawn:scene:x:y:z)</param>
    /// <param name="assetName">Optional asset name for logging</param>
    /// <returns>Unique stable key (baseKey or baseKey:N)</returns>
    public string GetUniqueKey(string baseKey, string? assetName = null)
    {
        if (!_counters.TryGetValue(baseKey, out var count))
        {
            _counters[baseKey] = 0;
            return baseKey;
        }

        _counters[baseKey] = ++count;
        var uniqueKey = $"{baseKey}:{count}";

        Debug.LogWarning(
            $"[{_listenerName}] Duplicate StableKey: '{baseKey}'. " +
            $"Asset: '{assetName ?? "unknown"}'. Assigning variant index |{count}."
        );

        return uniqueKey;
    }
}
