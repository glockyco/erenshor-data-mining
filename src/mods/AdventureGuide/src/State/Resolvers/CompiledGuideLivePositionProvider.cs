using AdventureGuide.Graph;
using AdventureGuide.Resolution;

namespace AdventureGuide.State.Resolvers;

public sealed class CompiledGuideLivePositionProvider : ILivePositionProvider
{
    private readonly CompiledGuide.CompiledGuide _guide;
    private readonly EntityGraph _graph;
    private readonly LiveStateTracker _liveState;

    public CompiledGuideLivePositionProvider(
        CompiledGuide.CompiledGuide guide,
        EntityGraph graph,
        LiveStateTracker liveState)
    {
        _guide = guide;
        _graph = graph;
        _liveState = liveState;
    }

    public WorldPosition? GetLivePosition(int spawnNodeId)
    {
        var spawnNode = ResolveGraphNode(spawnNodeId);
        if (spawnNode == null)
            return null;

        var live = _liveState.GetLiveNpcPosition(spawnNode);
        return live is null ? null : new WorldPosition(live.Value.x, live.Value.y, live.Value.z);
    }

    public bool IsAlive(int spawnNodeId)
    {
        var spawnNode = ResolveGraphNode(spawnNodeId);
        if (spawnNode == null)
            return false;

        return _liveState.GetSpawnState(spawnNode).State is SpawnAlive;
    }

    private Node? ResolveGraphNode(int nodeId)
    {
        string key = _guide.GetNodeKey(nodeId);
        return _graph.GetNode(key);
    }
}
