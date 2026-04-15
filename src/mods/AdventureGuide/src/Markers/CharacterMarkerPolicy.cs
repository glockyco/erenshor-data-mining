using AdventureGuide.Graph;
using AdventureGuide.Resolution;

namespace AdventureGuide.Markers;

/// <summary>
/// Marker emission policy for character targets.
///
/// All character targets: once they are no longer actionable, the active
/// quest marker must disappear and the separate respawn-timer marker becomes
/// the only representation of that source.
/// </summary>
internal static class CharacterMarkerPolicy
{
    public static bool ShouldEmitActiveMarker(ResolvedQuestTarget target)
    {
        if (target.TargetNode.Node.Type != NodeType.Character)
            return true;

        return target.IsActionable;
    }

    public static bool ShouldKeepQuestMarkerOnCorpse(ResolvedQuestTarget target)
    {
        return target.TargetNode.Node.Type == NodeType.Character
            && target.Semantic.ActionKind == ResolvedActionKind.Kill
            && target.IsActionable;
    }

    public static bool ShouldEmitActiveMarker(ResolvedTarget target)
    {
        return target.IsActionable;
    }

    public static bool ShouldKeepQuestMarkerOnCorpse(ResolvedTarget target)
    {
        return target.Semantic.ActionKind == ResolvedActionKind.Kill
            && target.IsActionable;
    }
}
