using AdventureGuide.Core;
using ErenshorMods.Input;
using UnityEngine;

namespace AdventureGuide.Tests;

public sealed class ShortcutPolicyTests
{
    [Theory]
    [InlineData(true, false)]
    [InlineData(false, true)]
    public void Text_input_suppresses_every_shortcut_without_sampling_keys(
        bool playerTyping,
        bool imguiTextInput
    )
    {
        var keyboard = new RecordingKeyboard(KeyCode.L, KeyCode.J, KeyCode.K, KeyCode.P);

        var actions = Sample(
            keyboard,
            playerTyping,
            imguiTextInput,
            replacementJournalEnabled: true,
            trackerEnabled: true
        );

        Assert.Equal(ShortcutAction.None, actions);
        Assert.Empty(keyboard.PressedQueries);
    }

    [Fact]
    public void Configured_edges_are_sampled_from_the_injected_keyboard_and_mapped()
    {
        var keyboard = new RecordingKeyboard(KeyCode.L, KeyCode.J, KeyCode.K, KeyCode.P);

        var actions = Sample(
            keyboard,
            playerTyping: false,
            imguiTextInput: false,
            replacementJournalEnabled: true,
            trackerEnabled: true
        );

        Assert.Equal(
            ShortcutAction.ToggleGuide
                | ShortcutAction.ToggleReplacementJournal
                | ShortcutAction.ToggleTracker
                | ShortcutAction.ToggleGroundPath,
            actions
        );
        Assert.Equal(new[] { KeyCode.L, KeyCode.J, KeyCode.K, KeyCode.P }, keyboard.PressedQueries);
    }

    [Fact]
    public void Disabled_optional_shortcuts_are_not_sampled_or_emitted()
    {
        var keyboard = new RecordingKeyboard(KeyCode.L, KeyCode.J, KeyCode.K, KeyCode.P);

        var actions = Sample(
            keyboard,
            playerTyping: false,
            imguiTextInput: false,
            replacementJournalEnabled: false,
            trackerEnabled: false
        );

        Assert.Equal(ShortcutAction.ToggleGuide | ShortcutAction.ToggleGroundPath, actions);
        Assert.Equal(new[] { KeyCode.L, KeyCode.P }, keyboard.PressedQueries);
    }

    [Fact]
    public void Idle_configured_keys_emit_no_actions()
    {
        var keyboard = new RecordingKeyboard();

        var actions = Sample(
            keyboard,
            playerTyping: false,
            imguiTextInput: false,
            replacementJournalEnabled: true,
            trackerEnabled: true
        );

        Assert.Equal(ShortcutAction.None, actions);
        Assert.Equal(new[] { KeyCode.L, KeyCode.J, KeyCode.K, KeyCode.P }, keyboard.PressedQueries);
    }

    private static ShortcutAction Sample(
        IKeyboardInput keyboard,
        bool playerTyping,
        bool imguiTextInput,
        bool replacementJournalEnabled,
        bool trackerEnabled
    ) =>
        ShortcutCoordinator.Sample(
            keyboard,
            guideKey: KeyCode.L,
            journalKey: KeyCode.J,
            trackerKey: KeyCode.K,
            groundPathKey: KeyCode.P,
            playerTyping,
            imguiTextInput,
            replacementJournalEnabled,
            trackerEnabled
        );

    private sealed class RecordingKeyboard : IKeyboardInput
    {
        private readonly HashSet<KeyCode> _pressed;

        public RecordingKeyboard(params KeyCode[] pressed)
        {
            _pressed = new HashSet<KeyCode>(pressed);
        }

        public List<KeyCode> PressedQueries { get; } = new();

        public bool IsHeld(KeyCode key) => false;

        public bool WasPressed(KeyCode key)
        {
            PressedQueries.Add(key);
            return _pressed.Contains(key);
        }
    }
}
