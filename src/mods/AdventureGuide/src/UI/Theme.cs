using System.Numerics;
using ImGuiNET;

namespace AdventureGuide.UI;

/// <summary>
/// Central color palette and spacing constants for the guide window.
/// All colors are Vector4 (r,g,b,a) for direct use with ImGui color APIs.
/// </summary>
public static class Theme
{
    // -- Surface colors --
    public static readonly Vector4 Background    = new(0.10f, 0.10f, 0.12f, 0.95f);
    public static readonly Vector4 Surface       = new(0.15f, 0.15f, 0.18f, 1.00f);

    // -- Text --
    public static readonly Vector4 TextPrimary   = new(1.00f, 1.00f, 1.00f, 1.00f);
    public static readonly Vector4 TextSecondary = new(0.60f, 0.60f, 0.60f, 1.00f);

    // -- Semantic --
    public static readonly Vector4 Accent  = new(0.20f, 0.35f, 0.55f, 1.00f);
    public static readonly Vector4 Success = new(0.40f, 0.80f, 0.40f, 1.00f);
    public static readonly Vector4 Warning = new(1.00f, 0.50f, 0.30f, 1.00f);
    public static readonly Vector4 Error   = new(1.00f, 0.30f, 0.30f, 1.00f);

    // -- Quest status --
    public static readonly Vector4 QuestActive    = new(1.00f, 0.90f, 0.30f, 1.00f);
    public static readonly Vector4 QuestCompleted = new(0.40f, 0.70f, 0.40f, 1.00f);
    public static readonly Vector4 QuestAvailable = new(0.50f, 0.70f, 0.90f, 1.00f);

    // -- Decorative --
    public static readonly Vector4 Header = new(0.90f, 0.85f, 0.60f, 1.00f);

    // -- Level badge difficulty --
    public static readonly Vector4 LevelSafe    = new(0.40f, 0.80f, 0.40f, 1.00f);
    public static readonly Vector4 LevelCaution = new(1.00f, 0.90f, 0.30f, 1.00f);
    public static readonly Vector4 LevelDanger  = new(1.00f, 0.30f, 0.30f, 1.00f);

    // -- Spacing --
    public const float WindowPadding  = 8f;
    public const float ItemSpacing    = 4f;
    public const float SectionGap     = 8f;
    public const float IndentWidth    = 16f;
    public const float LeftPanelRatio = 0.32f;

    /// <summary>
    /// Pushes window background and child background style colors.
    /// Caller MUST call <see cref="PopWindowStyle"/> after the window End().
    /// </summary>
    public static void PushWindowStyle()
    {
        ImGui.PushStyleColor(ImGuiCol.WindowBg, Background);
        ImGui.PushStyleColor(ImGuiCol.ChildBg, Surface);
    }

    /// <summary>
    /// Pops the two style colors pushed by <see cref="PushWindowStyle"/>.
    /// </summary>
    public static void PopWindowStyle()
    {
        ImGui.PopStyleColor(2);
    }
}
