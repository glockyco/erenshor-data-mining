using AdventureGuide.Graph;

namespace AdventureGuide.Plan;

/// <summary>
/// Determines whether a character node is currently hostile to the player.
///
/// A character is hostile when either its static faction is a hostile faction
/// (IsFriendly = false), or it belongs to a world faction whose current player
/// reputation has dropped below zero.
///
/// When no live game state is available (GlobalFactionManager not initialised,
/// unit tests), friendly characters default to non-hostile and no filtering
/// occurs — all sources are shown.
/// </summary>
internal static class FactionChecker
{
    /// <summary>
    /// Production overload: reads live reputation from GlobalFactionManager.
    /// </summary>
    public static bool IsCurrentlyHostile(Node node, EntityGraph graph)
        => IsCurrentlyHostile(node, graph, LookupGameFaction);

    /// <summary>
    /// Testable overload: faction value is supplied by the caller.
    /// <paramref name="getFactionValue"/> receives a faction REFNAME and
    /// returns the current reputation value, or null when unknown.
    /// </summary>
    public static bool IsCurrentlyHostile(
        Node node, EntityGraph graph, Func<string, float?> getFactionValue)
    {
        // Statically hostile factions are always hostile regardless of
        // current FactionValue (their AggressiveTowards list is hostile
        // by default and is only augmented — not cleared — by NPC.Tick).
        if (!node.IsFriendly) return true;

        // No world faction — purely static friendly NPC (town merchant etc.)
        if (node.FactionKey == null) return false;

        var factionNode = graph.GetNode(node.FactionKey);
        if (factionNode?.Refname == null) return false;

        var value = getFactionValue(factionNode.Refname);
        return value.HasValue && value.Value < 0f;
    }

    private static float? LookupGameFaction(string refname)
        => GlobalFactionManager.FindFactionData(refname)?.Value;
}
