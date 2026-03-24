using System.Numerics;
using AdventureGuide.Data;
using AdventureGuide.Navigation;
using AdventureGuide.State;
using ImGuiNET;

namespace AdventureGuide.UI;

/// <summary>
/// Main AdventureGuide window rendered via Dear ImGui.
/// Orchestrates QuestListPanel and QuestDetailPanel.
/// </summary>
public sealed class GuideWindow
{
    private readonly GuideData _data;
    private readonly QuestStateTracker _state;
    private readonly FilterState _filter = new();
    private readonly QuestListPanel _listPanel;
    private readonly QuestDetailPanel _detailPanel;
    private readonly NavigationHistory _history;

    private bool _visible;


    public bool Visible => _visible;

    public FilterState Filter => _filter;

    public GuideWindow(GuideData data, QuestStateTracker state, NavigationController nav,
        NavigationHistory history, TrackerState tracker)
    {
        _data = data;
        _state = state;
        _history = history;
        _listPanel = new QuestListPanel(data, state, _filter, tracker);
        _detailPanel = new QuestDetailPanel(data, state, nav, tracker);
    }

    public void Toggle() => _visible = !_visible;
    public void Show() => _visible = true;
    public void Hide() => _visible = false;

    /// <summary>
    /// Call from the ImGuiRenderer.OnLayout callback.
    /// Renders the full guide window when visible.
    /// </summary>
    public void Draw()
    {
        if (!_visible)
            return;

        ImGui.SetNextWindowSize(new Vector2(800, 550), ImGuiCond.FirstUseEver);

        Theme.PushWindowStyle();

        if (ImGui.Begin("Adventure Guide", ref _visible, ImGuiWindowFlags.NoCollapse))
            DrawTabBar();

        // Clamp window position so the title bar stays reachable. Dear ImGui
        // has no built-in clamping — without this the user can drag the window
        // entirely off screen with no way to recover.
        ClampWindowPosition();

        ImGui.End();
        Theme.PopWindowStyle();
    }

    private void DrawTabBar()
    {
        if (ImGui.BeginTabBar("##GuideTabs"))
        {
            if (ImGui.BeginTabItem("Quests"))
            {
                DrawQuestsTab();
                ImGui.EndTabItem();
            }

            if (ImGui.TabItemButton("<"))
            {
                var page = _history.Back();
                if (page.HasValue && page.Value.Type == NavigationHistory.PageType.Quest)
                    _state.SelectedQuestDBName = page.Value.Key;
            }
            if (ImGui.TabItemButton(">"))
            {
                var page = _history.Forward();
                if (page.HasValue && page.Value.Type == NavigationHistory.PageType.Quest)
                    _state.SelectedQuestDBName = page.Value.Key;
            }

            ImGui.EndTabBar();
        }
    }

    private void DrawQuestsTab()
    {
        var contentRegion = ImGui.GetContentRegionAvail();
        float leftWidth = contentRegion.X * Theme.LeftPanelRatio;

        // Left panel: quest list
        ImGui.BeginChild("##LeftPanel", new Vector2(leftWidth, 0), true);
        _listPanel.Draw(leftWidth);
        ImGui.EndChild();

        ImGui.SameLine();

        // Right panel: quest detail
        ImGui.BeginChild("##RightPanel", Vector2.Zero, true);
        _detailPanel.Draw();
        ImGui.EndChild();
    }

    /// <summary>
    /// Ensure the window stays reachable by clamping its position so
    /// at least a grab-sized strip of the title bar is on screen.
    /// Must be called between Begin and End while the window is current.
    /// </summary>
    private static void ClampWindowPosition()
    {
        const float minVisible = 40f;
        var pos = ImGui.GetWindowPos();
        var size = ImGui.GetWindowSize();
        var display = ImGui.GetIO().DisplaySize;

        float x = pos.X;
        float y = pos.Y;

        // Horizontal: keep at least minVisible pixels of title bar on screen
        if (x + size.X < minVisible) x = minVisible - size.X;
        if (x > display.X - minVisible) x = display.X - minVisible;

        // Vertical: top edge can't go below screen bottom minus minVisible,
        // bottom of title bar (~20px) must stay above screen top
        if (y > display.Y - minVisible) y = display.Y - minVisible;
        if (y < 0) y = 0;

        if (x != pos.X || y != pos.Y)
            ImGui.SetWindowPos(new Vector2(x, y));
    }

}
