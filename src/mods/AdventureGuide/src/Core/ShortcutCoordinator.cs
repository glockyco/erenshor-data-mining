using ErenshorMods.Input;
using UnityEngine;

namespace AdventureGuide.Core;

/// <summary>
/// Samples configured shortcut edges from the loader-neutral keyboard and maps
/// them to one frame of actions. Disabled or text-suppressed shortcuts are not
/// queried, matching the runtime's previous short-circuit behavior.
/// </summary>
internal static class ShortcutCoordinator
{
    internal static ShortcutAction Sample(
        IKeyboardInput keyboard,
        KeyCode guideKey,
        KeyCode journalKey,
        KeyCode trackerKey,
        KeyCode groundPathKey,
        bool playerTyping,
        bool imguiTextInput,
        bool replacementJournalEnabled,
        bool trackerEnabled
    )
    {
        if (keyboard == null)
            throw new ArgumentNullException(nameof(keyboard));
        if (playerTyping || imguiTextInput)
            return ShortcutAction.None;

        return ShortcutPolicy.Decide(
            playerTyping: false,
            imguiTextInput: false,
            guidePressed: KeyboardShortcuts.WasPressed(guideKey, keyboard),
            replacementJournalPressed: replacementJournalEnabled
                && KeyboardShortcuts.WasPressed(journalKey, keyboard),
            trackerPressed: trackerEnabled && KeyboardShortcuts.WasPressed(trackerKey, keyboard),
            groundPathPressed: KeyboardShortcuts.WasPressed(groundPathKey, keyboard),
            replacementJournalEnabled,
            trackerEnabled
        );
    }
}
