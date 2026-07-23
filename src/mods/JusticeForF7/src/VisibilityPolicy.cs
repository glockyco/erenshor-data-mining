namespace JusticeForF7;

/// <summary>Action for synchronizing Justice-owned UI with the game's Canvas.</summary>
internal enum CanvasVisibilityAction
{
    None,
    Tick,
    Show,
    Hide,
}

/// <summary>Immutable canvas observation state. The default value is uninitialized.</summary>
internal readonly struct CanvasVisibilityState
{
    internal CanvasVisibilityState(bool enabled)
    {
        IsInitialized = true;
        IsEnabled = enabled;
    }

    internal bool IsInitialized { get; }
    internal bool IsEnabled { get; }
}

/// <summary>Result of observing one Canvas sample.</summary>
internal readonly struct CanvasVisibilityObservation
{
    internal CanvasVisibilityObservation(CanvasVisibilityState state, CanvasVisibilityAction action)
    {
        State = state;
        Action = action;
    }

    internal CanvasVisibilityState State { get; }
    internal CanvasVisibilityAction Action { get; }
}

/// <summary>Dependency-free Canvas transition policy.</summary>
internal static class CanvasVisibilityPolicy
{
    internal static CanvasVisibilityState Reset() => default;

    internal static CanvasVisibilityObservation Observe(
        CanvasVisibilityState previous,
        bool enabled
    )
    {
        var state = new CanvasVisibilityState(enabled);
        if (!previous.IsInitialized)
            return new CanvasVisibilityObservation(state, CanvasVisibilityAction.None);

        if (previous.IsEnabled == enabled)
            return new CanvasVisibilityObservation(state, CanvasVisibilityAction.Tick);

        return new CanvasVisibilityObservation(
            state,
            enabled ? CanvasVisibilityAction.Show : CanvasVisibilityAction.Hide
        );
    }
}

/// <summary>World-space UI categories controlled by Justice settings.</summary>
internal enum WorldElementKind
{
    Nameplates,
    DamageNumbers,
    TargetRings,
    XPOrbs,
    CastBars,
    OtherWorldText,
}

/// <summary>Immutable frame-counter state for hidden-world-UI rescans.</summary>
internal readonly struct RescanState
{
    internal RescanState(int framesSinceLastScan)
    {
        FramesSinceLastScan = framesSinceLastScan;
    }

    internal int FramesSinceLastScan { get; }
}

/// <summary>Result of advancing the hidden-world-UI rescan cadence.</summary>
internal readonly struct RescanDecision
{
    internal RescanDecision(RescanState state, bool shouldScan)
    {
        State = state;
        ShouldScan = shouldScan;
    }

    internal RescanState State { get; }
    internal bool ShouldScan { get; }
}

/// <summary>Shared dependency-free visibility and rescan decisions.</summary>
internal static class VisibilityPolicy
{
    internal static RescanState ResetRescan() => default;

    internal static bool IsCategoryEnabled(IJusticeSettings settings, WorldElementKind kind)
    {
        return kind switch
        {
            WorldElementKind.Nameplates => settings.HideNameplates,
            WorldElementKind.DamageNumbers => settings.HideDamageNumbers,
            WorldElementKind.TargetRings => settings.HideTargetRings,
            WorldElementKind.XPOrbs => settings.HideXPOrbs,
            WorldElementKind.CastBars => settings.HideCastBars,
            WorldElementKind.OtherWorldText => settings.HideOtherWorldText,
            _ => throw new ArgumentOutOfRangeException(
                nameof(kind),
                kind,
                "Unknown world element kind"
            ),
        };
    }

    internal static bool ShouldSuppressTransient(
        bool hidden,
        IJusticeSettings settings,
        WorldElementKind kind
    )
    {
        return hidden && IsCategoryEnabled(settings, kind);
    }

    internal static RescanDecision AdvanceRescan(RescanState previous, bool hidden, int interval)
    {
        if (!hidden || interval <= 0)
            return new RescanDecision(previous, shouldScan: false);

        int frames = previous.FramesSinceLastScan + 1;
        if (frames < interval)
            return new RescanDecision(new RescanState(frames), shouldScan: false);

        return new RescanDecision(new RescanState(0), shouldScan: true);
    }
}
