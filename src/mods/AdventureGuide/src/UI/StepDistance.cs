namespace AdventureGuide.UI;

/// <summary>
/// Distance from the player to a tracked quest's current step target.
/// Separates two independent concerns: whether the step is in the
/// player's zone (for sort grouping and "Travel to" display) and
/// whether a meaningful distance in meters is available (for display
/// and distance-based ordering).
/// </summary>
public readonly struct StepDistance
{
    /// <summary>Whether the current step's target is in the player's zone.</summary>
    public readonly bool InCurrentZone;

    /// <summary>
    /// Distance in meters to the target. Only meaningful when
    /// <see cref="HasDistance"/> is true.
    /// </summary>
    public readonly float Meters;

    /// <summary>
    /// Optional label shown instead of distance (e.g. "Fishing").
    /// When set, the tracker displays this label in parentheses
    /// instead of a meter value.
    /// </summary>
    public readonly string? Label;

    /// <summary>Whether a displayable distance is available.</summary>
    public bool HasDistance => Meters < float.MaxValue;

    /// <summary>Whether to show a label instead of distance.</summary>
    public bool HasLabel => Label != null;

    public StepDistance(bool inCurrentZone, float meters, string? label = null)
    {
        InCurrentZone = inCurrentZone;
        Meters = meters;
        Label = label;
    }
}
