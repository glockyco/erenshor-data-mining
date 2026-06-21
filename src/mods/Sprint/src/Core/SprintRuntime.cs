using HarmonyLib;

namespace Sprint.Core;

/// <summary>
/// Shared sprint state, written by the plugin's per-frame Update and read by
/// the CalcStats Harmony patch. Static because the patch has no instance
/// context yet must reapply the multiplier whenever the game recalculates
/// stats (equipment swaps, buff expiry, ...).
/// </summary>
internal static class SprintRuntime
{
    /// <summary>The player's Stats, cached by the plugin once the player spawns.</summary>
    public static Stats? PlayerStats { get; set; }

    /// <summary>Whether sprint is currently engaged.</summary>
    public static bool Active { get; set; }

    /// <summary>Current run-speed multiplier, mirrored from config.</summary>
    public static float Multiplier { get; set; } = 1.5f;

    /// <summary>True when sprint should apply to <paramref name="stats"/> (player only, engaged).</summary>
    public static bool IsActiveFor(Stats stats) =>
        Active && PlayerStats != null && stats == PlayerStats;

    /// <summary>
    /// Recompute actualRunSpeed from the game's base components, multiplying the
    /// total (base + status-effect) speed when sprint is engaged. Mirrors the
    /// vanilla calculation when disengaged so it composes with CalcStats.
    /// </summary>
    public static void Apply(Stats stats, bool shouldSprint)
    {
        if (stats == null)
            return;

        // seRunSpeed (status-effect speed delta) is private; read it via Traverse.
        float seRunSpeed = Traverse.Create(stats).Field("seRunSpeed").GetValue<float>();

        stats.actualRunSpeed = shouldSprint
            ? (stats.RunSpeed + seRunSpeed) * Multiplier
            : stats.RunSpeed + seRunSpeed;

        // Respect the game's minimum speed cap.
        if (stats.actualRunSpeed < 2f)
            stats.actualRunSpeed = 2f;
    }

    /// <summary>Clear state on plugin unload so a Lunaris hot reload starts clean.</summary>
    public static void Reset()
    {
        PlayerStats = null;
        Active = false;
        Multiplier = 1.5f;
    }
}
