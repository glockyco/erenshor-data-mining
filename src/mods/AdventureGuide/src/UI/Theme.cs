using ImGuiNET;

namespace AdventureGuide.UI;

/// <summary>
/// Central color palette and spacing constants for the guide window.
/// Colors stored as packed uint (ImGui ABGR format) because Vector4
/// P/Invoke marshalling is broken after ILRepack merges System.Numerics.
/// </summary>
public static class Theme
{
    // -- Surface colors --
    public static readonly uint Background    = Rgba(0.10f, 0.10f, 0.12f, 0.95f);
    public static readonly uint Surface       = Rgba(0.15f, 0.15f, 0.18f, 1.00f);

    // -- Text --
    public static readonly uint TextPrimary   = Rgba(1.00f, 1.00f, 1.00f, 1.00f);
    public static readonly uint TextSecondary = Rgba(0.60f, 0.60f, 0.60f, 1.00f);

    // -- Semantic --
    public static readonly uint Accent  = Rgba(0.20f, 0.35f, 0.55f, 1.00f);
    public static readonly uint Success = Rgba(0.40f, 0.80f, 0.40f, 1.00f);
    public static readonly uint Warning = Rgba(1.00f, 0.50f, 0.30f, 1.00f);
    public static readonly uint Error   = Rgba(1.00f, 0.30f, 0.30f, 1.00f);

    // -- Quest status --
    public static readonly uint QuestActive    = Rgba(1.00f, 0.90f, 0.30f, 1.00f);
    public static readonly uint QuestImplicit   = Rgba(0.55f, 0.80f, 0.75f, 1.00f);
    public static readonly uint QuestCompleted = Rgba(0.40f, 0.70f, 0.40f, 1.00f);
    public static readonly uint QuestAvailable = Rgba(0.50f, 0.70f, 0.90f, 1.00f);

    // -- Decorative --
    public static readonly uint Header = Rgba(0.90f, 0.85f, 0.60f, 1.00f);

    // -- Level badge difficulty --
    public static readonly uint LevelSafe    = Rgba(0.40f, 0.80f, 0.40f, 1.00f);
    public static readonly uint LevelCaution = Rgba(1.00f, 0.90f, 0.30f, 1.00f);
    public static readonly uint LevelDanger  = Rgba(1.00f, 0.30f, 0.30f, 1.00f);

    // -- Tracker flash --
    public static readonly uint TrackerFlashGreen  = Rgba(0.20f, 0.80f, 0.20f, 0.30f);
    public static readonly uint TrackerFlashYellow = Rgba(0.80f, 0.70f, 0.10f, 0.20f);

    // -- Spacing --
    public const float WindowPadding  = 8f;
    public const float ItemSpacing    = 4f;
    public const float SectionGap     = 8f;
    public const float IndentWidth    = 16f;
    public const float LeftPanelRatio = 0.32f;

    /// <summary>Push window + child background colors. Call PopWindowStyle after End().</summary>
    public static void PushWindowStyle()
    {
        ImGui.PushStyleColor(ImGuiCol.WindowBg, Background);
        ImGui.PushStyleColor(ImGuiCol.ChildBg, Surface);
    }

    /// <summary>Pop the two style colors pushed by PushWindowStyle.</summary>
    public static void PopWindowStyle()
    {
        ImGui.PopStyleColor(2);
    }

    /// <summary>Convert RGBA floats (0-1) to packed uint in ImGui's ABGR format.</summary>
    public static uint Rgba(float r, float g, float b, float a)
    {
        byte br = (byte)(r * 255f + 0.5f);
        byte bg = (byte)(g * 255f + 0.5f);
        byte bb = (byte)(b * 255f + 0.5f);
        byte ba = (byte)(a * 255f + 0.5f);
        return (uint)(br | (bg << 8) | (bb << 16) | (ba << 24));
    }

    /// <summary>
    /// Apply saved window geometry from config. Call before ImGui.Begin.
    /// Values of -1 mean "use ImGui default" (FirstUseEver).
    /// </summary>
    public static void ApplyWindowGeometry(
        BepInEx.Configuration.ConfigEntry<float> x,
        BepInEx.Configuration.ConfigEntry<float> y,
        BepInEx.Configuration.ConfigEntry<float> w,
        BepInEx.Configuration.ConfigEntry<float> h,
        float defaultW, float defaultH)
    {
        float sw = w.Value > 0 ? w.Value : defaultW;
        float sh = h.Value > 0 ? h.Value : defaultH;
        ImGui.SetNextWindowSize(new System.Numerics.Vector2(sw, sh), ImGuiCond.FirstUseEver);
        if (x.Value >= 0 && y.Value >= 0)
            ImGui.SetNextWindowPos(new System.Numerics.Vector2(x.Value, y.Value), ImGuiCond.FirstUseEver);
    }

    /// <summary>
    /// Read current window geometry into config entries. Must be called
    /// between Begin and End while the window is current.
    /// </summary>
    public static void UpdateWindowGeometry(
        BepInEx.Configuration.ConfigEntry<float> x,
        BepInEx.Configuration.ConfigEntry<float> y,
        BepInEx.Configuration.ConfigEntry<float> w,
        BepInEx.Configuration.ConfigEntry<float> h)
    {
        var pos = ImGui.GetWindowPos();
        var size = ImGui.GetWindowSize();
        x.Value = pos.X;
        y.Value = pos.Y;
        w.Value = size.X;
        h.Value = size.Y;
    }

}
