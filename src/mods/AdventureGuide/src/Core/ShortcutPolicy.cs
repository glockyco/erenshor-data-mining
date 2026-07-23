namespace AdventureGuide.Core;

/// <summary>Actions produced by one frame of Adventure Guide shortcut input.</summary>
[Flags]
internal enum ShortcutAction : byte
{
    None = 0,
    ToggleGuide = 1 << 0,
    ToggleReplacementJournal = 1 << 1,
    ToggleTracker = 1 << 2,
    ToggleGroundPath = 1 << 3,
}

/// <summary>Allocation-free, loader-neutral shortcut gating and mapping.</summary>
internal static class ShortcutPolicy
{
    /// <summary>
    /// Maps already-sampled key edges to actions. Text input suppresses every
    /// action, while replacement-journal and tracker actions additionally honor
    /// their configuration enable flags. The policy intentionally does not read
    /// game or loader state; callers provide those observations and retain
    /// KeyboardShortcuts as the key-edge source.
    /// </summary>
    internal static ShortcutAction Decide(
        bool playerTyping,
        bool imguiTextInput,
        bool guidePressed,
        bool replacementJournalPressed,
        bool trackerPressed,
        bool groundPathPressed,
        bool replacementJournalEnabled,
        bool trackerEnabled
    )
    {
        if (playerTyping || imguiTextInput)
            return ShortcutAction.None;

        ShortcutAction actions = ShortcutAction.None;
        if (guidePressed)
            actions |= ShortcutAction.ToggleGuide;
        if (replacementJournalEnabled && replacementJournalPressed)
            actions |= ShortcutAction.ToggleReplacementJournal;
        if (trackerEnabled && trackerPressed)
            actions |= ShortcutAction.ToggleTracker;
        if (groundPathPressed)
            actions |= ShortcutAction.ToggleGroundPath;
        return actions;
    }
}
