using AdventureGuide.Graph;
using AdventureGuide.State;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace AdventureGuide.Position.Resolvers;

/// <summary>
/// Resolves a Character node to world positions.
///
/// Returns a position for every spawn edge so that each spawn point
/// produces its own marker and NAV candidate. Live NPC positions are
/// preferred over static spawn coordinates; dead spawns produce
/// non-actionable candidates so NAV deprioritises them.
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
        var currentScene = SceneManager.GetActiveScene().name;
        bool anyFromSpawns = false;

        var spawnEdges = _graph.OutEdges(node.Key, EdgeType.HasSpawn);
        for (int i = 0; i < spawnEdges.Count; i++)
        {
            var spawnNode = _graph.GetNode(spawnEdges[i].Target);
            if (spawnNode == null || !HasPosition(spawnNode))
                continue;

            var staticPos = new Vector3(spawnNode.X!.Value, spawnNode.Y!.Value, spawnNode.Z!.Value);

            // Only the loaded scene has live NPCs. Off-scene spawns must stay on
            // their static graph positions rather than probing current-scene objects.
            if (!LiveSceneScope.CanUseLiveSceneState(spawnNode.Scene, currentScene))
            {
                results.Add(new ResolvedPosition(staticPos, spawnNode.Scene, spawnNode.Key, isActionable: true));
                anyFromSpawns = true;
                continue;
            }

            var info = _liveState.GetSpawnState(spawnNode);
            switch (info.State)
            {
                case SpawnAlive:
                {
                    // Prefer the live NPC transform; fall back to static spawn coords.
                    var pos = info.LiveNPC != null && info.LiveNPC.gameObject != null
                        ? info.LiveNPC.transform.position
                        : staticPos;
                    var scene = info.LiveNPC != null && info.LiveNPC.gameObject != null
                        ? currentScene
                        : spawnNode.Scene;
                    results.Add(new ResolvedPosition(pos, scene, spawnNode.Key, isActionable: true));
                    anyFromSpawns = true;
                    break;
                }

                case SpawnDead:
                {
                    // Corpse still present: navigate to it (actionable).
                    // No corpse: show static spawn position (non-actionable respawn timer).
                    bool corpsePresent = info.LiveNPC != null && info.LiveNPC.gameObject != null;
                    var pos = corpsePresent ? info.LiveNPC!.transform.position : staticPos;
                    var scene = corpsePresent ? currentScene : spawnNode.Scene;
                    results.Add(new ResolvedPosition(pos, scene, spawnNode.Key, isActionable: corpsePresent));
                    anyFromSpawns = true;
                    break;
                }

                default:
                    // NightLocked, QuestGated, Disabled, Unknown — static position, non-actionable.
                    results.Add(new ResolvedPosition(staticPos, spawnNode.Scene, spawnNode.Key, isActionable: false));
                    anyFromSpawns = true;
                    break;
            }
        }

        if (anyFromSpawns)
            return;

        // No spawn edges — fall back to live NPC entity or static character position.
        if (!LiveSceneScope.CharacterHasCurrentScenePresence(_graph, node, currentScene))
        {
            if (node.X.HasValue && node.Y.HasValue && node.Z.HasValue)
            {
                results.Add(new ResolvedPosition(
                    new Vector3(node.X.Value, node.Y.Value, node.Z.Value),
                    node.Scene,
                    node.Key,
                    isActionable: true));
            }
            return;
        }

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
                currentScene,
                sourceNodeKey,
                isActionable: true));
            return;
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
