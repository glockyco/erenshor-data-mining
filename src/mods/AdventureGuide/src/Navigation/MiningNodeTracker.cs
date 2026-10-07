using System.Reflection;
using HarmonyLib;

namespace AdventureGuide.Navigation;

/// <summary>
/// Tracks mining node respawn timers in the current scene. Mining nodes
/// are NPCs with a MiningNode component that manages its own timer
/// (no SpawnPoint involved). When mined, the node's MeshRenderer is
/// disabled and a private Respawn field counts down at 60 ticks/second.
///
/// Unlike SpawnTimerTracker which is event-driven (death/spawn patches),
/// this tracker scans scene MiningNodes because mining doesn't trigger
/// NPC death events — the node stays alive with its character disabled.
/// </summary>
public sealed class MiningNodeTracker
{
    // MiningNode.Respawn is private — cache the FieldInfo
    private static readonly FieldInfo? RespawnField = typeof(MiningNode).GetField(
        "Respawn",
        BindingFlags.NonPublic | BindingFlags.Instance
    );

    private const float TickRate = 60f;

    private MiningNode[] _nodes = System.Array.Empty<MiningNode>();
    private int _rescanAfterFrame = -1;
    private static MiningNodeTracker? _current;

    /// <summary>
    /// Rescan MiningNode components in the current scene. Call on scene
    /// load and after hot reload.
    /// </summary>
    public void Rescan()
    {
        _current = this;
        _nodes = UnityEngine.Object.FindObjectsOfType<MiningNode>();
        // SpawnPoint.Update can create nodes after sceneLoaded. Scan again
        // after the first frame, then invalidate as late nodes start.
        _rescanAfterFrame = UnityEngine.Time.frameCount;
    }

    /// <summary>Clear cached nodes. Call on scene transition.</summary>
    public void Clear()
    {
        _nodes = System.Array.Empty<MiningNode>();
        _rescanAfterFrame = -1;
        if (ReferenceEquals(_current, this))
            _current = null;
    }

    internal static void OnNodeStarted()
    {
        if (_current != null)
            _current._rescanAfterFrame = UnityEngine.Time.frameCount;
    }

    /// <summary>
    /// Check if a mining node is currently mined (regenerating).
    /// Detected by MeshRenderer being disabled.
    /// </summary>
    public static bool IsMined(MiningNode node)
    {
        return node.MyRender != null && !node.MyRender.enabled;
    }

    /// <summary>
    /// Get remaining real seconds until a mined node respawns.
    /// Returns null if not mined, field inaccessible, or already respawned.
    /// </summary>
    public static float? GetRemainingSeconds(MiningNode node)
    {
        if (RespawnField == null)
            return null;
        if (!IsMined(node))
            return null;

        float ticks = (float)RespawnField.GetValue(node);
        if (ticks <= 0f)
            return null;

        return ticks / TickRate;
    }

    /// <summary>
    /// Find the mined node with the shortest remaining respawn time.
    /// Returns null if no nodes are currently mined.
    /// </summary>
    public (MiningNode node, float seconds)? FindShortestRespawn()
    {
        MiningNode? best = null;
        float bestSeconds = float.MaxValue;

        EnsureScanned();
        foreach (var node in _nodes)
        {
            if (node == null)
                continue;
            float? remaining = GetRemainingSeconds(node);
            if (remaining.HasValue && remaining.Value < bestSeconds)
            {
                best = node;
                bestSeconds = remaining.Value;
            }
        }

        return best != null ? (best, bestSeconds) : null;
    }

    /// <summary>
    /// Find the closest alive (not mined) mining node to the given position.
    /// Returns null if all nodes are currently mined or none exist.
    /// </summary>
    public MiningNode? FindClosestAlive(UnityEngine.Vector3 playerPos)
    {
        MiningNode? best = null;
        float bestDist = float.MaxValue;
        EnsureScanned();

        foreach (var node in _nodes)
        {
            if (node == null)
                continue;
            if (IsMined(node))
                continue;
            float dist = (node.transform.position - playerPos).sqrMagnitude;
            if (dist < bestDist)
            {
                best = node;
                bestDist = dist;
            }
        }

        return best;
    }

    private void EnsureScanned()
    {
        if (_rescanAfterFrame < 0 || UnityEngine.Time.frameCount <= _rescanAfterFrame)
            return;
        _nodes = UnityEngine.Object.FindObjectsOfType<MiningNode>();
        _rescanAfterFrame = -1;
    }

    /// <summary>Match only the node represented by this positioned source.</summary>
    public MiningNode? FindAtPosition(UnityEngine.Vector3 position)
    {
        EnsureScanned();
        foreach (var node in _nodes)
            if (
                node != null
                && SourceSelectionPolicy.MatchesNode(
                    (node.transform.position - position).sqrMagnitude
                )
            )
                return node;
        return null;
    }

    /// <summary>All cached MiningNode references in the current scene.</summary>
    public MiningNode[] Nodes
    {
        get
        {
            EnsureScanned();
            return _nodes;
        }
    }
}

[HarmonyPatch(typeof(MiningNode), "Start")]
internal static class MiningNodeStartedPatch
{
    [HarmonyPostfix]
    private static void Postfix() => MiningNodeTracker.OnNodeStarted();
}
