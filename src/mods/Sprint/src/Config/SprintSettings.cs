#if LUNARIS
using Lunaris.Config;
using UnityEngine;

namespace Sprint.Config;

/// <summary>
/// Lunaris-registered settings for the Sprint mod. Values bind live: Lunaris
/// updates this instance when the player edits options, so the plugin can read
/// fields directly each frame.
/// </summary>
public sealed class SprintSettings : ISprintSettings
{
    [Config("Enabled", "General", "Master switch. When false, sprint is disabled.")]
    public bool Enabled { get; set; } = true;

    [Config(
        "Sprint Key",
        "Controls",
        "Controls sprinting. Hold it, or tap to toggle when Toggle Mode is enabled."
    )]
    public KeyCode SprintKey { get; set; } = KeyCode.LeftShift;

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

    float ISprintSettings.Multiplier => SprintMultiplier;
}
#endif
