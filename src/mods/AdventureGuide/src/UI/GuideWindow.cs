using System.Numerics;
using AdventureGuide.Config;
using AdventureGuide.Resolution;
using AdventureGuide.State;
using ImGuiNET;

namespace AdventureGuide.UI;

/// <summary>
/// Main AdventureGuide window rendered via Dear ImGui.
/// The quest detail tree is now sourced from <see cref="QuestResolutionService"/>
/// so the window renders the same semantics layer as tracker, navigation, and markers.
/// </summary>
public sealed class GuideWindow
{
    private readonly QuestStateTracker _state;
    private readonly FilterState _filter;
    private readonly NavigationHistory _history;
    private readonly GuideConfig _config;
    private readonly ViewRenderer _viewRenderer;
    private readonly QuestListPanel _listPanel;
    private readonly QuestResolutionService _resolution;

    private bool _visible;

    public bool Visible => _visible;
    public FilterState Filter => _filter;

    public GuideWindow(
        QuestStateTracker state,
        NavigationHistory history,
        GuideConfig config,
        ViewRenderer viewRenderer,
        QuestListPanel listPanel,
        FilterState filter,
        QuestResolutionService resolution)
    {
        _state = state;
        _history = history;
        _config = config;
        _viewRenderer = viewRenderer;
        _listPanel = listPanel;
        _filter = filter;
        _resolution = resolution;
    }

    public void Toggle() => _visible = !_visible;
    public void Show() => _visible = true;
    public void Hide() => _visible = false;

    public void Draw()
    {
        if (!_visible)
            return;

        var cond = _config.LayoutResetRequested ? ImGuiCond.Always : ImGuiCond.FirstUseEver;
        var scale = _config.ResolvedUiScale;
        var display = ImGui.GetIO().DisplaySize;
        ImGui.SetNextWindowSize(new Vector2(780f * scale, 530f * scale), cond);
        ImGui.SetNextWindowPos(
            new Vector2(display.X * 0.5f, display.Y * 0.5f), cond,
            new Vector2(0.5f, 0.5f));

        Theme.PushWindowStyle();
        if (ImGui.Begin("Adventure Guide", ref _visible, ImGuiWindowFlags.NoCollapse))
            DrawTabBar();
        Theme.ClampWindowPosition();
        ImGui.End();
        Theme.PopWindowStyle();
    }

    private void DrawTabBar()
    {
        if (!ImGui.BeginTabBar("##GuideTabs"))
            return;

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

    private void DrawQuestsTab()
    {
        var contentRegion = ImGui.GetContentRegionAvail();
        float leftWidth = contentRegion.X * Theme.LeftPanelRatio;

        ImGui.BeginChild("##LeftPanel", new Vector2(leftWidth, 0), true);
        _listPanel.Draw(leftWidth);
        ImGui.EndChild();

        ImGui.SameLine();

        ImGui.BeginChild("##RightPanel", Vector2.Zero, true);
        QuestResolution? resolution = null;
        if (_state.SelectedQuestDBName != null)
            resolution = _resolution.GetQuestResolutionByDbName(_state.SelectedQuestDBName);
        _viewRenderer.Draw(resolution);
        ImGui.EndChild();
    }
}
