using AdventureGuide.Graph;

namespace AdventureGuide.Plan;

/// <summary>
/// Runtime policy governing which item drop sources are shown to the player.
/// Encapsulates the hostile-preference rule: when at least one hostile DropsItem
/// source exists, friendly DropsItem sources are suppressed.
///
/// Lives in the Plan layer so both Resolution (blueprint path) and UI.Tree
/// (plan-tree path) can consume it without layering violations. Both layers
/// already import Plan. Faction hostility is delegated to
/// <see cref="FactionChecker.IsCurrentlyHostile(Node, EntityGraph)"/>
/// </summary>
internal sealed class SourceVisibilityPolicy
{
    private readonly EntityGraph _graph;
    private readonly Func<string, float?> _factionLookup;

    public SourceVisibilityPolicy(EntityGraph graph, Func<string, float?> factionLookup)
    {
        _graph = graph;
        _factionLookup = factionLookup;
    }

    /// <summary>
    /// Returns true if <paramref name="node"/> is a currently hostile character:
    /// either unconditionally hostile (IsFriendly=false) or dynamically hostile
    /// via negative faction reputation. Null input returns false (fail-open).
    /// </summary>
    public bool IsHostileDropSource(Node? node)
        => node != null && FactionChecker.IsCurrentlyHostile(node, _graph, _factionLookup);

    /// <summary>
    /// Returns a filtered copy of <paramref name="sources"/> suppressing friendly
    /// DropsItem sources when at least one hostile DropsItem source exists.
    /// Non-drop sources (SellsItem, GivesItem, etc.) are always preserved.
    /// Returns <paramref name="sources"/> unchanged if no hostile drop source exists.
    /// </summary>
    public IReadOnlyList<SourceSiteBlueprint> FilterBlueprints(
        IReadOnlyList<SourceSiteBlueprint> sources)
    {
        bool hasHostileDrop = false;
        for (int i = 0; i < sources.Count && !hasHostileDrop; i++)
        {
            if (sources[i].AcquisitionEdge != EdgeType.DropsItem) continue;
            if (IsHostileDropSource(_graph.GetNode(sources[i].SourceNodeKey)))
                hasHostileDrop = true;
        }
        if (!hasHostileDrop) return sources;

        var filtered = new List<SourceSiteBlueprint>(sources.Count);
        for (int i = 0; i < sources.Count; i++)
        {
            var s = sources[i];
            if (s.AcquisitionEdge != EdgeType.DropsItem) { filtered.Add(s); continue; }
            // Fail-open: unknown source node is kept; hostile nodes are kept.
            var node = _graph.GetNode(s.SourceNodeKey);
            if (node == null || IsHostileDropSource(node)) filtered.Add(s);
        }
        return filtered;
    }
}
