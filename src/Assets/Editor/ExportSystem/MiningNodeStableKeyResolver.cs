#nullable enable

using System.Collections.Generic;

public sealed class MiningNodeStableKeyResolver
{
    private DuplicateKeyTracker _keyTracker = new("MiningNodeStableKeyResolver");
    private readonly Dictionary<int, string> _keysByInstanceId = new();

    public void Reset()
    {
        _keyTracker = new DuplicateKeyTracker("MiningNodeStableKeyResolver");
        _keysByInstanceId.Clear();
    }

    public string GetStableKey(MiningNode node)
    {
        int instanceId = node.GetInstanceID();
        if (_keysByInstanceId.TryGetValue(instanceId, out var key))
            return key;
        var position = node.transform.position;
        var baseKey = StableKeyGenerator.ForMiningNode(
            node.gameObject.scene.name,
            position.x,
            position.y,
            position.z
        );
        key = _keyTracker.GetUniqueKey(baseKey, node.gameObject.name);
        _keysByInstanceId.Add(instanceId, key);
        return key;
    }
}
