using AdventureGuide.Rendering;
using AdventureGuide.State;
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
    public static readonly uint Background    = ImGuiColors.Rgba(0.10f, 0.10f, 0.12f, 0.95f);
    public static readonly uint Surface       = ImGuiColors.Rgba(0.15f, 0.15f, 0.18f, 1.00f);

    // -- Text --
    public static readonly uint TextPrimary   = ImGuiColors.Rgba(1.00f, 1.00f, 1.00f, 1.00f);
    public static readonly uint TextSecondary = ImGuiColors.Rgba(0.60f, 0.60f, 0.60f, 1.00f);

    // -- Semantic --
    public static readonly uint Accent  = ImGuiColors.Rgba(0.22f, 0.55f, 0.30f, 1.00f);
    public static readonly uint Success = ImGuiColors.Rgba(0.40f, 0.80f, 0.40f, 1.00f);
    public static readonly uint Warning = ImGuiColors.Rgba(1.00f, 0.50f, 0.30f, 1.00f);
    public static readonly uint Error   = ImGuiColors.Rgba(1.00f, 0.30f, 0.30f, 1.00f);

    // -- Quest status --
    public static readonly uint QuestActive    = ImGuiColors.Rgba(1.00f, 0.90f, 0.30f, 1.00f);
    public static readonly uint QuestImplicit   = ImGuiColors.Rgba(0.55f, 0.80f, 0.75f, 1.00f);
    public static readonly uint QuestCompleted = ImGuiColors.Rgba(0.40f, 0.70f, 0.40f, 1.00f);
    public static readonly uint QuestAvailable = ImGuiColors.Rgba(0.50f, 0.70f, 0.90f, 1.00f);
    public static readonly uint NavManualOverride = ImGuiColors.Rgba(0.45f, 0.85f, 0.90f, 1.00f);
    public static readonly uint SourceDimmed = ImGuiColors.Rgba(0.50f, 0.50f, 0.50f, 1.00f);

    // -- Decorative --
    public static readonly uint Header = ImGuiColors.Rgba(0.90f, 0.85f, 0.60f, 1.00f);

    // -- Level badge difficulty --
    public static readonly uint LevelSafe    = ImGuiColors.Rgba(0.40f, 0.80f, 0.40f, 1.00f);
    public static readonly uint LevelCaution = ImGuiColors.Rgba(1.00f, 0.90f, 0.30f, 1.00f);
    public static readonly uint LevelDanger  = ImGuiColors.Rgba(1.00f, 0.30f, 0.30f, 1.00f);

    // -- Tracker flash --
    public static readonly uint TrackerFlashGreen  = ImGuiColors.Rgba(0.20f, 0.80f, 0.20f, 0.30f);
    public static readonly uint TrackerFlashYellow = ImGuiColors.Rgba(0.80f, 0.70f, 0.10f, 0.20f);

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

    /// <summary>
    /// Clamp the current ImGui window so it stays partially on screen.
    /// Call between Begin and End.
    /// </summary>
    public static void ClampWindowPosition()
    {
        const float minVisible = 40f;
        var pos = ImGui.GetWindowPos();
        var size = ImGui.GetWindowSize();
        var display = ImGui.GetIO().DisplaySize;

        float x = pos.X;
        float y = pos.Y;

        if (x + size.X < minVisible) x = minVisible - size.X;
        if (x > display.X - minVisible) x = display.X - minVisible;
        if (y > display.Y - minVisible) y = display.Y - minVisible;
        if (y < 0) y = 0;

        if (x != pos.X || y != pos.Y)
            ImGui.SetWindowPos(new System.Numerics.Vector2(x, y));
    }

    /// <summary>
    /// Resolve quest status color from tracker state. Shared by QuestListPanel
    /// and TrackerWindow to keep color semantics consistent.
    /// </summary>
    public static uint GetQuestColor(QuestStateTracker state, string dbName)
    {
        if (state.IsImplicitlyAvailable(dbName)) return QuestImplicit;
        if (state.IsActive(dbName))           return QuestActive;
        if (state.IsCompleted(dbName))        return QuestCompleted;
        return QuestAvailable;
    }

}
