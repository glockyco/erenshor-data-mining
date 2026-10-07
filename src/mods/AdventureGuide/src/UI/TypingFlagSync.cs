namespace AdventureGuide.UI;

internal static class TypingFlagSync
{
    public static bool? Next(bool textActive, bool wasActive, bool chatActive) =>
        textActive ? true
        : wasActive && !chatActive ? false
        : (bool?)null;
}
