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
