using ErenshorMods.Input;
using UnityEngine;

namespace AdventureGuide.Core;

/// <summary>
/// Samples configured shortcut edges and coordinates Escape consumption across
/// the runtime and native menu updates, regardless of their execution order.
/// </summary>
internal sealed class ShortcutCoordinator
{
    private int _escapeConsumedFrame = -1;

    internal bool ConsumeEscape(int frame, bool escapePressed, bool guideVisible)
    {
        if (_escapeConsumedFrame == frame)
            return true;
        if (!escapePressed || !guideVisible)
            return false;

        _escapeConsumedFrame = frame;
        return true;
    }

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
