#nullable enable

using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// Centralized resolver for character stable keys.
///
/// Multiple listeners need character stable keys during the asset scan
/// (CharacterListener, LootTableListener, SpawnPointListener, etc.).
/// When two prefabs share the same Unity object name, the base key from
/// <see cref="StableKeyGenerator.ForCharacter"/> is ambiguous and must be
/// deduplicated with a variant suffix (:1, :2, etc.).
///
/// This resolver ensures all listeners agree on the same deduplicated key
/// for a given Character instance. It lazily generates and caches keys on
/// first access, so listeners can call <see cref="GetStableKey"/> in any
/// order during the scan without coordination.
/// </summary>
public class CharacterStableKeyResolver
{
    private readonly DuplicateKeyTracker _keyTracker = new("CharacterStableKeyResolver");
    private readonly Dictionary<int, string> _keysByInstanceId = new();

    /// <summary>
    /// Returns the deduplicated stable key for a Character.
    ///
    /// On first call for a given instance, generates the base key via
    /// <see cref="StableKeyGenerator.ForCharacter"/>, deduplicates it,
    /// and caches the result. Subsequent calls return the cached key.
    /// </summary>
    /// <param name="character">Character component (must not be null)</param>
    /// <returns>Deduplicated stable key (e.g., "character:foo" or "character:foo:1")</returns>
    public string GetStableKey(Character character)
    {
        var instanceId = character.GetInstanceID();

        if (_keysByInstanceId.TryGetValue(instanceId, out var cachedKey))
            return cachedKey;

        var baseKey = StableKeyGenerator.ForCharacter(character);
        var stableKey = _keyTracker.GetUniqueKey(baseKey, character.gameObject.name);
        _keysByInstanceId[instanceId] = stableKey;

        return stableKey;
    }
}
