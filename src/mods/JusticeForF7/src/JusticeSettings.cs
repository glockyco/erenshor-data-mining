using Lunaris.Config;

namespace JusticeForF7;

/// <summary>
/// Lunaris-registered settings for Justice for F7. Each world-UI category can be
/// toggled independently; values bind live from the Lunaris config UI.
/// </summary>
public sealed class JusticeSettings
{
    [Config("Enabled", "General", "Master switch. When false, F7 behaves as vanilla.")]
    public bool Enabled { get; set; } = true;

    [Config(
        "Enable Logging",
        "General",
        "Enable debug logging. Set to false to silence all mod log output."
    )]
    public bool EnableLogging { get; set; } = true;

    [Config(
        "Rescan Interval",
        "General",
        "Frames between re-scans while UI is hidden (0 = disable re-scan)."
    )]
    public int RescanInterval { get; set; } = 30;

    [Config("Hide Nameplates", "Elements", "Hide NPC, SimPlayer, and player nameplates.")]
    public bool HideNameplates { get; set; } = true;

    [Config("Hide Damage Numbers", "Elements", "Hide floating damage and heal numbers.")]
    public bool HideDamageNumbers { get; set; } = true;

    [Config("Hide Target Rings", "Elements", "Hide the selection ring under targeted characters.")]
    public bool HideTargetRings { get; set; } = true;

    [Config("Hide XP Orbs", "Elements", "Hide XP orb particles.")]
    public bool HideXPOrbs { get; set; } = true;

    [Config("Hide Cast Bars", "Elements", "Hide NPC and SimPlayer cast bars above nameplates.")]
    public bool HideCastBars { get; set; } = true;

    [Config(
        "Hide Other World Text",
        "Elements",
        "Hide remaining world-space text (loot prompts, etc.)."
    )]
    public bool HideOtherWorldText { get; set; } = true;
}
