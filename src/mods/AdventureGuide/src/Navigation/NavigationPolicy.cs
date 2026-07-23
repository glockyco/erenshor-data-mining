using AdventureGuide.Data;

namespace AdventureGuide.Navigation;

/// <summary>
/// Kind-independent description of a fixed-position navigation target.
/// Keeping this contract free of Unity types allows the target identity and
/// coordinates to be tested without a game or loader installation.
/// </summary>
public record struct FixedPositionTargetSpec(
    float X,
    float Y,
    float Z,
    string DisplayName,
    string Scene,
    string QuestKey,
    int StepOrder,
    string? SourceId,
    string OriginQuestKey,
    int OriginStepOrder
);

/// <summary>Pure policies used to resolve fixed-position navigation targets.</summary>
public static class NavigationPolicy
{
    /// <summary>
    /// Resolve a fixed-position step to its loader-neutral target description.
    /// </summary>
    public static FixedPositionTargetSpec CreateFixedPositionTargetSpec(
        QuestStep step,
        QuestEntry quest,
        string originQuestKey,
        int originStepOrder
    )
    {
        var location =
            step.Location
            ?? throw new ArgumentException("Fixed-position step has no location", nameof(step));

        return new FixedPositionTargetSpec(
            location.X,
            location.Y,
            location.Z,
            step.TargetName ?? step.Description,
            location.Scene,
            quest.RuntimeKey,
            step.Order,
            step.TargetKey,
            originQuestKey,
            originStepOrder
        );
    }

    /// <summary>Compute the Euclidean distance between two 3D points.</summary>
    public static float EuclideanDistance(
        float firstX,
        float firstY,
        float firstZ,
        float secondX,
        float secondY,
        float secondZ
    )
    {
        float dx = secondX - firstX;
        float dy = secondY - firstY;
        float dz = secondZ - firstZ;
        return MathF.Sqrt(dx * dx + dy * dy + dz * dz);
    }
}
