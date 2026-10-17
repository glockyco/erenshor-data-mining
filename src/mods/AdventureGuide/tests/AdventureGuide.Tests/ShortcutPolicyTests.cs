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
    }

    [Theory]
    [InlineData(true)]
    [InlineData(false)]
    public void Escape_closes_guide_and_stays_consumed_for_both_update_orders(bool runtimeFirst)
    {
        var coordinator = new ShortcutCoordinator();
        bool guideVisible = true;
        bool nativeMenuOpened = false;
        int closeCount = 0;

        bool HandleEscape()
        {
            bool consumed = coordinator.ConsumeEscape(42, escapePressed: true, guideVisible);
            if (consumed && guideVisible)
            {
                guideVisible = false;
                closeCount++;
            }
            return consumed;
        }

        if (runtimeFirst)
            HandleEscape();
        nativeMenuOpened = !HandleEscape();
        if (!runtimeFirst)
            HandleEscape();

        Assert.False(guideVisible);
        Assert.False(nativeMenuOpened);
        Assert.Equal(1, closeCount);
        Assert.False(coordinator.ConsumeEscape(43, escapePressed: false, guideVisible));
        Assert.False(coordinator.ConsumeEscape(44, escapePressed: true, guideVisible));
    }

    [Fact]
    public void Escape_is_not_claimed_without_a_visible_guide_and_a_key_edge()
    {
        var coordinator = new ShortcutCoordinator();

        Assert.False(coordinator.ConsumeEscape(1, escapePressed: true, guideVisible: false));
        Assert.False(coordinator.ConsumeEscape(2, escapePressed: false, guideVisible: true));
        Assert.True(coordinator.ConsumeEscape(3, escapePressed: true, guideVisible: true));
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
