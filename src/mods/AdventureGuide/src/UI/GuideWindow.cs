using System.Numerics;
using AdventureGuide.Data;
using AdventureGuide.Navigation;
using AdventureGuide.State;
using ImGuiNET;

namespace AdventureGuide.UI;

/// <summary>
/// Main AdventureGuide window rendered via Dear ImGui.
/// Orchestrates QuestListPanel, QuestDetailPanel, and ProgressPanel.
/// </summary>
public sealed class GuideWindow
{
    private readonly GuideData _data;
    private readonly QuestStateTracker _state;
    private readonly FilterState _filter = new();
    private readonly QuestListPanel _listPanel;
    private readonly QuestDetailPanel _detailPanel;
    private readonly ProgressPanel _progressPanel;
    private readonly NavigationHistory _history;

    private bool _visible;


    public bool Visible => _visible;

    public FilterState Filter => _filter;

    public GuideWindow(GuideData data, QuestStateTracker state, NavigationController nav, NavigationHistory history)
    {
        _data = data;
        _state = state;
        _history = history;
        _listPanel = new QuestListPanel(data, state, _filter);
        _detailPanel = new QuestDetailPanel(data, state, nav, history);
        _progressPanel = new ProgressPanel(data, state);
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
        {
            // Navigation history buttons in window header
            ImGui.SameLine(ImGui.GetWindowWidth() - 90); // right-align
            bool canBack = _history.CanGoBack;
            bool canFwd = _history.CanGoForward;
            if (!canBack) ImGui.BeginDisabled();
            if (ImGui.SmallButton("<"))
            {
                var page = _history.Back();
                if (page.HasValue && page.Value.Type == NavigationHistory.PageType.Quest)
                    _state.SelectedQuestDBName = page.Value.Key;
            }
            if (!canBack) ImGui.EndDisabled();
            ImGui.SameLine();
            if (!canFwd) ImGui.BeginDisabled();
            if (ImGui.SmallButton(">"))
            {
                var page = _history.Forward();
                if (page.HasValue && page.Value.Type == NavigationHistory.PageType.Quest)
                    _state.SelectedQuestDBName = page.Value.Key;
            }
            if (!canFwd) ImGui.EndDisabled();

            DrawTabBar();
        }

        ImGui.End();
        Theme.PopWindowStyle();
    }

    private void DrawTabBar()
    {
        if (ImGui.BeginTabBar("##GuideTabs"))
        {
            if (ImGui.BeginTabItem("Quests"))
            {
                _filter.SelectedTab = 0;
                DrawQuestsTab();
                ImGui.EndTabItem();
            }

            if (ImGui.BeginTabItem("Progress"))
            {
                _filter.SelectedTab = 1;
                _progressPanel.Draw();
                ImGui.EndTabItem();
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
}
