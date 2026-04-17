using AdventureGuide.Diagnostics;

namespace AdventureGuide.Navigation;

/// <summary>
/// Decides when the shared navigation target selector must rebuild its target
/// lists from the current navigation-target source.
///
/// Any meaningful live-world change forces a rebuild, even if the source
/// version did not advance. That keeps NAV aligned with mined nodes,
/// despawned corpses, and other transient state changes that can change target
/// actionability without changing the selected quest set.
/// </summary>
internal readonly struct TargetSelectorRefreshDecision
{
    public static readonly TargetSelectorRefreshDecision No = new(false, DiagnosticTrigger.Unknown);

    public TargetSelectorRefreshDecision(bool force, DiagnosticTrigger reason)
    {
        Force = force;
        Reason = reason;
    }

    public bool Force { get; }

    public DiagnosticTrigger Reason { get; }
}

internal static class TargetSelectorRefreshPolicy
{
    public static TargetSelectorRefreshDecision Decide(
        bool liveWorldChanged,
        int targetSourceVersion,
        int lastTargetSourceVersion,
        int navSetVersion,
        int lastNavSetVersion
    )
    {
        if (liveWorldChanged)
            return new TargetSelectorRefreshDecision(true, DiagnosticTrigger.LiveWorldChanged);
        if (targetSourceVersion != lastTargetSourceVersion)
            return new TargetSelectorRefreshDecision(
                true,
                DiagnosticTrigger.TargetSourceVersionChanged
            );
        if (navSetVersion != lastNavSetVersion)
            return new TargetSelectorRefreshDecision(true, DiagnosticTrigger.NavSetChanged);
        return TargetSelectorRefreshDecision.No;
    }
}
