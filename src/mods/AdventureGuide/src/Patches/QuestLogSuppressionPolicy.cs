namespace AdventureGuide.Patches;

internal static class QuestLogSuppressionPolicy
{
    internal static bool ShouldRunOriginal(bool replaceEnabled, bool journalKeyDown) =>
        !replaceEnabled || !journalKeyDown;
}
