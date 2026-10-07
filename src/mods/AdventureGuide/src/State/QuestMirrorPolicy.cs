namespace AdventureGuide.State;

internal static class QuestMirrorPolicy
{
    // A call is not an event: the game ignores held/completed quest assignments
    // and repeated completions. Only a newly added membership is mirrored.
    internal static bool WasAdded(bool containedBefore, bool containsAfter) =>
        !containedBefore && containsAfter;
}
