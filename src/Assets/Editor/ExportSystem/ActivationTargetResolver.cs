#nullable enable

using System;
using System.Collections.Generic;
using System.Globalization;
using UnityEditor;
using UnityEngine;
using UnityEngine.SceneManagement;

public sealed class ActivationTarget
{
    public string Kind { get; set; } = "";
    public string Key { get; set; } = "";
    public string Scene { get; set; } = "";
    public string ObjectName { get; set; } = "";
    public bool IsEnabled { get; set; }
}

public sealed class ActivationTargetResolver
{
    private readonly CharacterStableKeyResolver _characterKeys;
    private readonly ZoneLineStableKeyResolver _zoneLineKeys;
    private readonly DuplicateKeyTracker _placementKeys = new("ActivationTargetResolver");
    private readonly Dictionary<int, string> _keys = new();
    private readonly Dictionary<(int trigger, int index), string> _triggerKeys = new();
    private readonly HashSet<int> _seededScenes = new();

    public ActivationTargetResolver(
        CharacterStableKeyResolver characterKeys,
        ZoneLineStableKeyResolver zoneLineKeys
    )
    {
        _characterKeys = characterKeys;
        _zoneLineKeys = zoneLineKeys;
    }

    public static string ObjectKey(GameObject target)
    {
        RequireScene(target);
        var path = new Stack<string>();
        for (var current = target.transform; current != null; current = current.parent)
            path.Push(
                Uri.EscapeDataString(current.name.Normalize().ToLowerInvariant())
                    + "["
                    + current.GetSiblingIndex().ToString(CultureInfo.InvariantCulture)
                    + "]"
            );
        return "object:"
            + Uri.EscapeDataString(target.scene.name.Normalize().ToLowerInvariant())
            + ":"
            + string.Join("/", path);
    }

    public string GetStableKey(SpawnPoint target) => PlacementKey(target);

    public string GetStableKey(ItemBag target) => PlacementKey(target);

    public string GetStableKey(Door target) => PlacementKey(target);

    public string GetStableKey(Zoneline target) => _zoneLineKeys.GetStableKey(target);

    public string GetTriggerSpawnKey(SpawnPointTrigger trigger, int index)
    {
        RequireScene(trigger.gameObject);
        SeedScene(trigger.gameObject.scene);
        if (_triggerKeys.TryGetValue((trigger.GetInstanceID(), index), out var key))
            return key;
        throw new InvalidOperationException(
            $"Trigger {ObjectKey(trigger.gameObject)} has no exported spawn at index {index}"
        );
    }

    public IEnumerable<ActivationTarget> Resolve(GameObject target, bool enabling)
    {
        RequireScene(target);
        yield return Subject("object", ObjectKey(target), target, target.activeInHierarchy);
        var stack = new Stack<Transform>();
        stack.Push(target.transform);
        while (stack.Count > 0)
        {
            var current = stack.Pop();
            var go = current.gameObject;
            foreach (var component in go.GetComponents<Component>())
            {
                if (component == null)
                    continue;
                bool active = component is Behaviour behaviour
                    ? behaviour.isActiveAndEnabled
                    : go.activeInHierarchy;
                switch (component)
                {
                    case Character character:
                        yield return Subject(
                            "character",
                            _characterKeys.GetStableKey(character),
                            go,
                            active
                        );
                        break;
                    case SpawnPoint spawnPoint:
                        yield return Subject("spawn_point", GetStableKey(spawnPoint), go, active);
                        break;
                    case Zoneline zoneLine:
                        yield return Subject(
                            "zone_line",
                            _zoneLineKeys.GetStableKey(zoneLine),
                            go,
                            active
                        );
                        break;
                    case ItemBag bag:
                        yield return Subject("item_bag", GetStableKey(bag), go, active);
                        break;
                    case Door door:
                        yield return Subject("door", GetStableKey(door), go, active);
                        break;
                    case SpawnPointTrigger trigger:
                        if (!HasTriggerCharacters(trigger) || trigger.SpawnSpots == null)
                            break;
                        for (int index = 0; index < trigger.SpawnSpots.Count; index++)
                        {
                            var spot = trigger.SpawnSpots[index];
                            if (spot != null)
                                yield return Subject(
                                    "spawn_point",
                                    GetTriggerSpawnKey(trigger, index),
                                    spot,
                                    active
                                );
                        }
                        break;
                }
            }
            // SetActive(true) changes only the root activeSelf. An inactive
            // descendant blocks its entire subtree, even when its leaf is activeSelf.
            for (int index = 0; index < current.childCount; index++)
            {
                var child = current.GetChild(index);
                if (!enabling || child.gameObject.activeSelf)
                    stack.Push(child);
            }
        }
    }

    private static ActivationTarget Subject(string kind, string key, GameObject go, bool enabled) =>
        new()
        {
            Kind = kind,
            Key = key,
            Scene = go.scene.name,
            ObjectName = go.name,
            IsEnabled = enabled,
        };

    private string PlacementKey(Component target)
    {
        RequireScene(target.gameObject);
        SeedScene(target.gameObject.scene);
        if (_keys.TryGetValue(target.GetInstanceID(), out var key))
            return key;
        throw new InvalidOperationException($"Unscanned placement: {ObjectKey(target.gameObject)}");
    }

    private void SeedScene(Scene scene)
    {
        if (!_seededScenes.Add(scene.handle))
            return;
        // Match AssetScanner: roots in scene order, stack DFS with children
        // pushed in ascending order, then components in serialized order.
        foreach (var root in scene.GetRootGameObjects())
        {
            var stack = new Stack<GameObject>();
            stack.Push(root);
            while (stack.Count > 0)
            {
                var go = stack.Pop();
                foreach (var component in go.GetComponents<Component>())
                {
                    var position = go.transform.position;
                    string? baseKey = null;
                    switch (component)
                    {
                        case SpawnPoint:
                            baseKey = StableKeyGenerator.ForSpawnPoint(
                                scene.name,
                                position.x,
                                position.y,
                                position.z
                            );
                            break;
                        case ItemBag:
                            baseKey = StableKeyGenerator.ForItemBag(
                                scene.name,
                                position.x,
                                position.y,
                                position.z
                            );
                            break;
                        case Door door:
                            var renderer = door.GetComponent<Renderer>();
                            position = renderer != null ? renderer.bounds.center : position;
                            baseKey = StableKeyGenerator.ForDoor(
                                scene.name,
                                position.x,
                                position.y,
                                position.z
                            );
                            break;
                        case SpawnPointTrigger trigger:
                            SeedTrigger(trigger, scene.name);
                            break;
                    }
                    if (baseKey != null)
                        _keys.Add(
                            component.GetInstanceID(),
                            _placementKeys.GetUniqueKey(baseKey, go.name)
                        );
                }
                foreach (Transform child in go.transform)
                    stack.Push(child.gameObject);
            }
        }
    }

    private void SeedTrigger(SpawnPointTrigger trigger, string scene)
    {
        if (trigger.SpawnSpots == null || !HasTriggerCharacters(trigger))
            return;
        for (int index = 0; index < trigger.SpawnSpots.Count; index++)
        {
            var spot = trigger.SpawnSpots[index];
            if (spot == null)
                continue;
            var position = spot.transform.position;
            var baseKey = StableKeyGenerator.ForSpawnPointTrigger(
                scene,
                position.x,
                position.y,
                position.z
            );
            _triggerKeys.Add(
                (trigger.GetInstanceID(), index),
                _placementKeys.GetUniqueKey(baseKey, $"{trigger.gameObject.name}/{spot.name}")
            );
        }
    }

    private static bool HasTriggerCharacters(SpawnPointTrigger trigger)
    {
        if (trigger.Alt != null && trigger.Alt.GetComponent<Character>() != null)
            return true;
        if (trigger.Spawnables != null)
            foreach (var spawnable in trigger.Spawnables)
                if (spawnable != null && spawnable.GetComponent<Character>() != null)
                    return true;
        return false;
    }

    private static void RequireScene(GameObject target)
    {
        if (target == null || !target.scene.IsValid() || PrefabUtility.IsPartOfPrefabAsset(target))
            throw new InvalidOperationException(
                "Activation object keys require a placed scene object"
            );
    }
}
