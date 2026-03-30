using AdventureGuide.Graph;
using AdventureGuide.Markers;
using AdventureGuide.State;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace AdventureGuide.Navigation.Resolvers;

/// <summary>
/// Resolves a Character node to world positions. Priority order:
/// 1. live NPC position
/// 2. live spawn/static spawn position
/// 3. best dead/unknown spawn position
/// 4. static character position
/// </summary>
public sealed class CharacterPositionResolver : IPositionResolver
{
    private readonly EntityRegistry _entities;
    private readonly EntityGraph _graph;
    private readonly LiveStateTracker _liveState;
    private readonly GuideDependencyEngine _dependencies;

    public CharacterPositionResolver(
        EntityRegistry entities,
        EntityGraph graph,
        LiveStateTracker liveState,
        GuideDependencyEngine dependencies)
    {
        _entities = entities;
        _graph = graph;
        _liveState = liveState;
        _dependencies = dependencies;
    }

    public void Resolve(Node node, List<ResolvedPosition> results)
    {
        var playerPos = GameData.PlayerControl?.transform.position ?? Vector3.zero;
        var liveNpc = _entities.FindClosest(node.Key, playerPos);
        if (liveNpc != null)
        {
            var sourceNodeKey = FindClosestSpawnNodeKey(node, liveNpc.transform.position)
                ?? (node.X.HasValue && node.Y.HasValue && node.Z.HasValue ? node.Key : null);
            if (sourceNodeKey != null)
                _dependencies.RecordFact(new GuideFactKey(GuideFactKind.SourceState, sourceNodeKey));

            results.Add(new ResolvedPosition(
                liveNpc.transform.position,
                SceneManager.GetActiveScene().name,
                sourceNodeKey));
            return;
        }

        var spawnEdges = _graph.OutEdges(node.Key, EdgeType.HasSpawn);
        if (spawnEdges.Count > 0)
        {
            Node? bestSpawn = null;
            float bestRespawn = float.MaxValue;
            bool foundAny = false;

            for (int i = 0; i < spawnEdges.Count; i++)
            {
                var spawnNode = _graph.GetNode(spawnEdges[i].Target);
                if (spawnNode == null || !HasPosition(spawnNode))
                    continue;

                var info = _liveState.GetSpawnState(spawnNode);
                if (info.State is SpawnAlive)
                {
                    results.Add(new ResolvedPosition(
                        new Vector3(spawnNode.X!.Value, spawnNode.Y!.Value, spawnNode.Z!.Value),
                        spawnNode.Scene,
                        spawnNode.Key));
                    return;
                }

                if (info.State is SpawnDead dead)
                {
                    foundAny = true;
                    if (dead.RespawnSeconds < bestRespawn)
                    {
                        bestRespawn = dead.RespawnSeconds;
                        bestSpawn = spawnNode;
                    }
                }
                else if (!foundAny)
                {
                    bestSpawn ??= spawnNode;
                }
            }

            if (bestSpawn != null)
            {
                results.Add(new ResolvedPosition(
                    new Vector3(bestSpawn.X!.Value, bestSpawn.Y!.Value, bestSpawn.Z!.Value),
                    bestSpawn.Scene,
                    bestSpawn.Key));
                return;
            }
        }

        if (node.X.HasValue && node.Y.HasValue && node.Z.HasValue)
            results.Add(new ResolvedPosition(new Vector3(node.X.Value, node.Y.Value, node.Z.Value), node.Scene, node.Key));
    }

    private string? FindClosestSpawnNodeKey(Node characterNode, Vector3 livePosition)
    {
        var spawnEdges = _graph.OutEdges(characterNode.Key, EdgeType.HasSpawn);
        Node? bestSpawn = null;
        float bestDistance = float.MaxValue;

        for (int i = 0; i < spawnEdges.Count; i++)
        {
            var spawnNode = _graph.GetNode(spawnEdges[i].Target);
            if (spawnNode == null || !HasPosition(spawnNode))
                continue;

            float distance = Vector3.Distance(
                livePosition,
                new Vector3(spawnNode.X!.Value, spawnNode.Y!.Value, spawnNode.Z!.Value));
            if (distance < bestDistance)
            {
                bestDistance = distance;
                bestSpawn = spawnNode;
            }
        }

        return bestSpawn?.Key;
    }

    private static bool HasPosition(Node node) =>
        node.X.HasValue && node.Y.HasValue && node.Z.HasValue;
}
