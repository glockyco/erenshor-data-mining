using ErenshorMods.Input;
using UnityEngine;
using Xunit;

namespace InteractiveMapCompanion.Tests.Input;

public sealed class KeyboardShortcutsTests
{
    [Fact]
    public void IsHeld_requires_every_key_in_a_chord()
    {
        var keyboard = new FakeKeyboardInput(KeyCode.LeftControl, KeyCode.K);

        Assert.True(KeyboardShortcuts.IsHeld([KeyCode.LeftControl, KeyCode.K], keyboard));
        Assert.False(
            KeyboardShortcuts.IsHeld([KeyCode.LeftControl, KeyCode.K, KeyCode.LeftShift], keyboard)
        );
    }

    [Fact]
    public void IsHeld_rejects_an_empty_or_disabled_chord()
    {
        var keyboard = new FakeKeyboardInput(KeyCode.LeftShift);

        Assert.False(KeyboardShortcuts.IsHeld([], keyboard));
        Assert.False(KeyboardShortcuts.IsHeld([KeyCode.None], keyboard));
    }

    [Fact]
    public void BepInEx_style_shortcut_requires_main_key_and_modifiers()
    {
        var keyboard = new FakeKeyboardInput(KeyCode.K, KeyCode.LeftControl);

        Assert.True(KeyboardShortcuts.IsHeld(KeyCode.K, [KeyCode.LeftControl], keyboard));
        Assert.False(
            KeyboardShortcuts.IsHeld(KeyCode.K, [KeyCode.LeftControl, KeyCode.LeftShift], keyboard)
        );
    }

    [Fact]
    public void WasPressed_uses_frame_edge_state_and_rejects_none()
    {
        var keyboard = new FakeKeyboardInput(pressed: [KeyCode.F2]);

        Assert.True(KeyboardShortcuts.WasPressed(KeyCode.F2, keyboard));
        Assert.False(KeyboardShortcuts.WasPressed(KeyCode.F3, keyboard));
        Assert.False(KeyboardShortcuts.WasPressed(KeyCode.None, keyboard));
    }

    private sealed class FakeKeyboardInput : IKeyboardInput
    {
        private readonly HashSet<KeyCode> _held;
        private readonly HashSet<KeyCode> _pressed;

        internal FakeKeyboardInput(
            KeyCode held = KeyCode.None,
            KeyCode secondHeld = KeyCode.None,
            IReadOnlyList<KeyCode>? pressed = null
        )
        {
            _held = new HashSet<KeyCode>();
            if (held != KeyCode.None)
                _held.Add(held);
            if (secondHeld != KeyCode.None)
                _held.Add(secondHeld);
            _pressed = pressed == null ? [] : new HashSet<KeyCode>(pressed);
        }

        public bool IsHeld(KeyCode key) => _held.Contains(key);

        public bool WasPressed(KeyCode key) => _pressed.Contains(key);
    }
}
