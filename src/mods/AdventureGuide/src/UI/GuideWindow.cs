using System.Numerics;
using AdventureGuide.Config;
using AdventureGuide.Graph;
using AdventureGuide.State;
using AdventureGuide.Views;
using ImGuiNET;

namespace AdventureGuide.UI;

/// <summary>
/// Main AdventureGuide window rendered via Dear ImGui.
/// Orchestrates QuestListPanel (left) and ViewRenderer (right).
/// </summary>
public sealed class GuideWindow
{
    private readonly EntityGraph _graph;
    private readonly QuestStateTracker _state;
    private readonly FilterState _filter = new();
    private readonly QuestViewBuilder _viewBuilder;
    private readonly NavigationHistory _history;
    private readonly GuideConfig _config;
    private readonly ViewRenderer _viewRenderer;
    private readonly QuestListPanel _listPanel;

    private bool _visible;

    public bool Visible => _visible;

    public FilterState Filter => _filter;

    public GuideWindow(EntityGraph graph, QuestStateTracker state, QuestViewBuilder viewBuilder,
        NavigationHistory history, TrackerState tracker, GuideConfig config,
        ViewRenderer viewRenderer, QuestListPanel listPanel)
    {
        _graph = graph;
        _state = state;
        _viewBuilder = viewBuilder;
        _history = history;
        _config = config;
        _viewRenderer = viewRenderer;
        _listPanel = listPanel;
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

        // Right panel: quest dependency tree
        ImGui.BeginChild("##RightPanel", Vector2.Zero, true);
        var selectedKey = _state.SelectedQuestDBName;
        ViewNode? tree = null;
        if (selectedKey != null)
            tree = FindAndBuild(selectedKey);
        _viewRenderer.Draw(tree);
        ImGui.EndChild();
    }

    /// <summary>
    /// Resolves a quest DB name (e.g. "ANGLERRING") to a node key, then builds
    /// the view tree for the detail panel.
    /// </summary>
    private ViewNode? FindAndBuild(string dbName)
    {
        var quest = _graph.GetQuestByDbName(dbName);
        return quest != null ? _viewBuilder.Build(quest.Key) : null;
    }
}
