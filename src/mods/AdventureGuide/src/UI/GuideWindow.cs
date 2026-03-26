using System.Numerics;
using AdventureGuide.Config;
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
    private readonly GuideConfig _config;

    private readonly float _uiScale;

    private bool _visible;


    public bool Visible => _visible;

    public FilterState Filter => _filter;

    public GuideWindow(GuideData data, QuestStateTracker state, NavigationController nav,
        NavigationHistory history, TrackerState tracker, GuideConfig config, float uiScale)
    {
        _data = data;
        _state = state;
        _history = history;
        _config = config;
        _uiScale = uiScale;
        _listPanel = new QuestListPanel(data, state, _filter, tracker);
        _detailPanel = new QuestDetailPanel(data, state, nav, tracker, config);
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

        ImGui.SetNextWindowSize(new Vector2(800f * _uiScale, 550f * _uiScale), ImGuiCond.FirstUseEver);

        Theme.PushWindowStyle();

        if (ImGui.Begin("Adventure Guide", ref _visible, ImGuiWindowFlags.NoCollapse))
            DrawTabBar();

        Theme.ClampWindowPosition();

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


}
