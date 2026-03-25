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
    /// <see cref="HasDistance"/> is true. For cross-zone quests with active
    /// navigation, this is the distance to the zone line waypoint.
    /// </summary>
    public readonly float Meters;

    /// <summary>Whether a displayable distance is available.</summary>
    public bool HasDistance => Meters < float.MaxValue;

    public StepDistance(bool inCurrentZone, float meters)
    {
        InCurrentZone = inCurrentZone;
        Meters = meters;
    }
}
