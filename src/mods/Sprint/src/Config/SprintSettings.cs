using Lunaris.Config;
using UnityEngine;

namespace Sprint.Config;

/// <summary>
/// Lunaris-registered settings for the Sprint mod. Values bind live: Lunaris
/// updates this instance (and the keybind entry) when the player edits options
/// in the config UI, so the plugin can read fields directly each frame.
/// </summary>
public sealed class SprintSettings
{
    [Keybind(KeyCode.LeftShift)]
    [Config(
        "Sprint Key",
        "Controls",
        "Hold to sprint, or tap to toggle when Toggle Mode is enabled."
    )]
    public IKeybind SprintKey { get; set; } = null!;

    [Config(
        "Toggle Mode",
        "Controls",
        "Tap the sprint key to toggle sprint on/off instead of holding it."
    )]
    public bool ToggleMode { get; set; }

    [Config(
        "Speed Multiplier",
        "Speed",
        "Run-speed multiplier while sprinting. 1.0 = normal, 1.5 = 50% faster, 10 = ludicrous speed."
    )]
    [ConfigRange(1f, 10f)]
    public float SprintMultiplier { get; set; } = 1.5f;
}
