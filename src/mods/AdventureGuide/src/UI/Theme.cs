using AdventureGuide.Data;
using AdventureGuide.State;
using ImGuiNET;
using Vector2 = System.Numerics.Vector2;

namespace AdventureGuide.UI;

/// <summary>
/// Central color palette and spacing constants for the guide window.
/// Colors are stored as packed uints in ImGui ABGR format for draw-list APIs.
/// </summary>
public static class Theme
{
    // -- Surface colors --
    public static readonly uint Background = Rgba(0.10f, 0.10f, 0.12f, 0.95f);
    public static readonly uint Surface = Rgba(0.15f, 0.15f, 0.18f, 1.00f);

    // -- Text --
    public static readonly uint TextPrimary = Rgba(1.00f, 1.00f, 1.00f, 1.00f);
    public static readonly uint TextSecondary = Rgba(0.60f, 0.60f, 0.60f, 1.00f);

    // -- Semantic --
    public static readonly uint Accent = Rgba(0.20f, 0.35f, 0.55f, 1.00f);
    public static readonly uint Success = Rgba(0.40f, 0.80f, 0.40f, 1.00f);
    public static readonly uint Warning = Rgba(1.00f, 0.50f, 0.30f, 1.00f);
    public static readonly uint Error = Rgba(1.00f, 0.30f, 0.30f, 1.00f);

    // -- Quest status --
    public static readonly uint QuestActive = Rgba(1.00f, 0.90f, 0.30f, 1.00f);
    public static readonly uint QuestImplicit = Rgba(0.55f, 0.80f, 0.75f, 1.00f);
    public static readonly uint QuestCompleted = Rgba(0.40f, 0.70f, 0.40f, 1.00f);
    public static readonly uint QuestAvailable = Rgba(0.50f, 0.70f, 0.90f, 1.00f);
    public static readonly uint NavManualOverride = Rgba(0.45f, 0.85f, 0.90f, 1.00f);
    public static readonly uint SourceDimmed = Rgba(0.50f, 0.50f, 0.50f, 1.00f);

    // -- Decorative --
    public static readonly uint Header = Rgba(0.90f, 0.85f, 0.60f, 1.00f);

    // -- Level badge difficulty --
    public static readonly uint LevelSafe = Rgba(0.40f, 0.80f, 0.40f, 1.00f);
    public static readonly uint LevelCaution = Rgba(1.00f, 0.90f, 0.30f, 1.00f);
    public static readonly uint LevelDanger = Rgba(1.00f, 0.30f, 0.30f, 1.00f);

    // -- Tracker flash --
    public static readonly uint TrackerFlashGreen = Rgba(0.20f, 0.80f, 0.20f, 0.30f);
    public static readonly uint TrackerFlashYellow = Rgba(0.80f, 0.70f, 0.10f, 0.20f);

    // -- Spacing --
    public const float WindowPadding = 8f;
    public const float ItemSpacing = 4f;
    public const float SectionGap = 8f;
    public const float IndentWidth = 16f;
    public const float LeftPanelRatio = 0.32f;

    private const int WindowStyleColorCount = 15;
    private const int WindowStyleVarCount = 13;

    internal readonly struct WindowStyleScopeToken : System.IDisposable
    {
        public void Dispose() => PopWindowStyle();
    }

    internal static WindowStyleScopeToken WindowStyleScope()
    {
        PushWindowStyle();
        return default;
    }

    /// <summary>
    /// Push the Adventure Guide's scoped ImGui style baseline.
    /// Lunaris owns the global ImGui context, so never rely on its process-wide defaults.
    /// </summary>
    public static void PushWindowStyle()
    {
        ImGui.PushStyleColor(ImGuiCol.WindowBg, Background);
        ImGui.PushStyleColor(ImGuiCol.ChildBg, Surface);
        ImGui.PushStyleColor(ImGuiCol.Button, Rgba(0.26f, 0.59f, 0.98f, 0.40f));
        ImGui.PushStyleColor(ImGuiCol.ButtonHovered, Rgba(0.26f, 0.59f, 0.98f, 1.00f));
        ImGui.PushStyleColor(ImGuiCol.ButtonActive, Rgba(0.06f, 0.53f, 0.98f, 1.00f));
        ImGui.PushStyleColor(ImGuiCol.FrameBg, Rgba(0.16f, 0.29f, 0.48f, 0.54f));
        ImGui.PushStyleColor(ImGuiCol.FrameBgHovered, Rgba(0.26f, 0.59f, 0.98f, 0.40f));
        ImGui.PushStyleColor(ImGuiCol.FrameBgActive, Rgba(0.26f, 0.59f, 0.98f, 0.67f));
        ImGui.PushStyleColor(ImGuiCol.Border, Rgba(0.43f, 0.43f, 0.50f, 0.50f));
        ImGui.PushStyleColor(ImGuiCol.TitleBg, Rgba(0.04f, 0.04f, 0.04f, 1.00f));
        ImGui.PushStyleColor(ImGuiCol.TitleBgActive, Rgba(0.16f, 0.29f, 0.48f, 1.00f));
        ImGui.PushStyleColor(ImGuiCol.TitleBgCollapsed, Rgba(0.00f, 0.00f, 0.00f, 0.51f));
        ImGui.PushStyleColor(ImGuiCol.Header, Rgba(0.26f, 0.59f, 0.98f, 0.31f));
        ImGui.PushStyleColor(ImGuiCol.HeaderHovered, Rgba(0.26f, 0.59f, 0.98f, 0.80f));
        ImGui.PushStyleColor(ImGuiCol.HeaderActive, Rgba(0.26f, 0.59f, 0.98f, 1.00f));
        ImGui.PushStyleVar(ImGuiStyleVar.WindowRounding, 0f);
        ImGui.PushStyleVar(ImGuiStyleVar.ChildRounding, 0f);
        ImGui.PushStyleVar(ImGuiStyleVar.FrameRounding, 0f);
        ImGui.PushStyleVar(ImGuiStyleVar.PopupRounding, 0f);
        ImGui.PushStyleVar(ImGuiStyleVar.ScrollbarRounding, 0f);
        ImGui.PushStyleVar(ImGuiStyleVar.GrabRounding, 0f);
        ImGui.PushStyleVar(ImGuiStyleVar.TabRounding, 4f);
        ImGui.PushStyleVar(ImGuiStyleVar.ChildBorderSize, 1f);
        ImGui.PushStyleVar(ImGuiStyleVar.FrameBorderSize, 0f);
        ImGui.PushStyleVar(ImGuiStyleVar.FramePadding, new Vector2(4f, 3f));
        ImGui.PushStyleVar(ImGuiStyleVar.ItemSpacing, new Vector2(8f, 4f));
        ImGui.PushStyleVar(ImGuiStyleVar.IndentSpacing, IndentWidth);
        ImGui.PushStyleVar(ImGuiStyleVar.SelectableTextAlign, new Vector2(0f, 0f));
    }

    /// <summary>Pop the style baseline pushed by PushWindowStyle.</summary>
    public static void PopWindowStyle()
    {
        ImGui.PopStyleVar(WindowStyleVarCount);
        ImGui.PopStyleColor(WindowStyleColorCount);
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
    /// Current display size for the native ImGui layer.
    /// Use Unity's screen size so this code does not depend on ImGuiIOPtr's ref-return vector binding.
    /// </summary>
    public static Vector2 DisplaySize() => new(UnityEngine.Screen.width, UnityEngine.Screen.height);

    /// <summary>
    /// Clamp the current ImGui window so it stays partially on screen.
    /// Call between Begin and End.
    /// </summary>
    public static void ClampWindowPosition()
    {
        const float minVisible = 40f;
        var pos = ImGui.GetWindowPos();
        var size = ImGui.GetWindowSize();
        var display = DisplaySize();

        float x = pos.X;
        float y = pos.Y;

        if (x + size.X < minVisible)
            x = minVisible - size.X;
        if (x > display.X - minVisible)
            x = display.X - minVisible;
        if (y > display.Y - minVisible)
            y = display.Y - minVisible;
        if (y < 0)
            y = 0;

        if (x != pos.X || y != pos.Y)
            ImGui.SetWindowPos(new Vector2(x, y));
    }

    /// <summary>
    /// Resolve quest status color from tracker state. Shared by QuestListPanel
    /// and TrackerWindow to keep color semantics consistent.
    /// </summary>
    public static uint GetQuestColor(QuestStateTracker state, QuestEntry quest)
    {
        return state.GetStatus(quest) switch
        {
            QuestRuntimeStatus.ImplicitlyActive => QuestImplicit,
            QuestRuntimeStatus.Active => QuestActive,
            QuestRuntimeStatus.Completed => QuestCompleted,
            _ => QuestAvailable,
        };
    }
}
