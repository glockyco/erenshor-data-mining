using UnityEngine;
using UnityEngine.SceneManagement;
using AdventureGuide.Graph;
using AdventureGuide.Markers;
using AdventureGuide.State;

namespace AdventureGuide.Navigation.Resolvers;

/// <summary>
/// Resolves a Character node to world positions. Priority order:
/// 1. Live NPC position from EntityRegistry (real-time tracking)
/// 2. When all NPCs are dead: spawn point with shortest respawn timer
/// 3. Static coordinates on the graph node
/// 4. All linked spawn point positions as fallback
/// </summary>
public sealed class CharacterPositionResolver : IPositionResolver
{
    private readonly EntityRegistry _entities;
    private readonly EntityGraph _graph;
    private readonly LiveStateTracker _liveState;

    public CharacterPositionResolver(EntityRegistry entities, EntityGraph graph, LiveStateTracker liveState)
    {
        _entities = entities;
        _graph = graph;
        _liveState = liveState;
    }

    public void Resolve(Node node, List<ResolvedPosition> results)
    {
        // Prefer live NPC position for real-time tracking
        var playerPos = GameData.PlayerControl?.transform.position ?? Vector3.zero;
        var liveNPC = _entities.FindClosest(node.Key, playerPos);
        if (liveNPC != null)
        {
            results.Add(new ResolvedPosition(liveNPC.transform.position, SceneManager.GetActiveScene().name));
            return;
        }

        // All NPCs dead or not in scene — find spawn with shortest respawn timer
        var spawnEdges = _graph.OutEdges(node.Key, EdgeType.HasSpawn);
        if (spawnEdges.Count > 0)
        {
            Node? bestSpawn = null;
            float bestRespawn = float.MaxValue;
            bool foundAny = false;

            for (int i = 0; i < spawnEdges.Count; i++)
            {
                var spawnNode = _graph.GetNode(spawnEdges[i].Target);
                if (spawnNode == null || !HasPosition(spawnNode)) continue;

                var info = _liveState.GetSpawnState(spawnNode);

                if (info.State is SpawnAlive)
                {
                    // Alive spawn we didn't find via EntityRegistry — use its static position
                    results.Add(new ResolvedPosition(
                        new Vector3(spawnNode.X!.Value, spawnNode.Y!.Value, spawnNode.Z!.Value),
                        spawnNode.Scene));
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
                    // Unknown/disabled/night-locked — still a candidate if nothing better
                    bestSpawn ??= spawnNode;
                }
            }

            if (bestSpawn != null)
            {
                results.Add(new ResolvedPosition(
                    new Vector3(bestSpawn.X!.Value, bestSpawn.Y!.Value, bestSpawn.Z!.Value),
                    bestSpawn.Scene));
                return;
            }
        }

        // Fallback: static coordinates baked into the graph node
        if (node.X.HasValue && node.Y.HasValue && node.Z.HasValue)
            results.Add(new ResolvedPosition(new Vector3(node.X.Value, node.Y.Value, node.Z.Value), node.Scene));
    }

    private static bool HasPosition(Node n) =>
        n.X.HasValue && n.Y.HasValue && n.Z.HasValue;
}
