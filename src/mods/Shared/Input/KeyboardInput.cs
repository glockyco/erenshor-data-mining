using UnityEngine;

namespace ErenshorMods.Input;

/// <summary>Loader-neutral keyboard state read once from Unity's legacy input system.</summary>
public interface IKeyboardInput
{
    bool IsHeld(KeyCode key);

    bool WasPressed(KeyCode key);
}

/// <summary>Production keyboard adapter shared by native BepInEx and Lunaris plugins.</summary>
public sealed class UnityKeyboardInput : IKeyboardInput
{
    public static UnityKeyboardInput Instance { get; } = new();

    private UnityKeyboardInput() { }

    public bool IsHeld(KeyCode key) => UnityEngine.Input.GetKey(key);

    public bool WasPressed(KeyCode key) => UnityEngine.Input.GetKeyDown(key);
}

/// <summary>Evaluates configured keys and chords without depending on a mod loader.</summary>
public static class KeyboardShortcuts
{
    public static bool WasPressed(KeyCode key, IKeyboardInput keyboard) =>
        key != KeyCode.None && keyboard.WasPressed(key);

    public static bool IsHeld(IReadOnlyList<KeyCode> keys, IKeyboardInput keyboard)
    {
        if (keys.Count == 0)
            return false;

        for (int i = 0; i < keys.Count; i++)
        {
            if (keys[i] == KeyCode.None || !keyboard.IsHeld(keys[i]))
                return false;
        }

        return true;
    }

    public static bool IsHeld(
        KeyCode mainKey,
        IReadOnlyList<KeyCode> modifiers,
        IKeyboardInput keyboard
    )
    {
        if (mainKey == KeyCode.None || !keyboard.IsHeld(mainKey))
            return false;

        for (int i = 0; i < modifiers.Count; i++)
        {
            if (modifiers[i] == KeyCode.None || !keyboard.IsHeld(modifiers[i]))
                return false;
        }

        return true;
    }
}
