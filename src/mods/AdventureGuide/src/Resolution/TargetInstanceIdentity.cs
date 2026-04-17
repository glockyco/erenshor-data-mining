namespace AdventureGuide.Resolution;

/// <summary>
/// Resolves the concrete world-instance identity of a target.
///
/// Conceptual character keys are not sufficient for runtime cutover because
/// several character nodes can share one physical source, and one character can
/// have several physical sources. When a positioned source exists, it is the
/// canonical identity for NAV, marker dedupe, and resolution dedupe.
/// </summary>
internal static class TargetInstanceIdentity
{
    public static string Get(string targetNodeKey, string? sourceKey) => sourceKey ?? targetNodeKey;

    public static string BuildDedupeKey(
        string questKey,
        string goalNodeKey,
        string targetNodeKey,
        string? scene,
        string? sourceKey
    )
    {
        return string.Join(
            "|",
            new[]
            {
                questKey,
                Get(targetNodeKey, sourceKey),
                scene ?? string.Empty,
                sourceKey ?? string.Empty,
                goalNodeKey,
            }
        );
    }
}
