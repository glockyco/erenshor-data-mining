using System.Numerics;
using AdventureGuide.Data;
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

    private bool _visible;

    /// <summary>True when the ImGui window is hovered (for input blocking).</summary>
    public bool IsMouseOver { get; private set; }

    public bool Visible => _visible;

    public FilterState Filter => _filter;

    public GuideWindow(GuideData data, QuestStateTracker state)
    {
        _data = data;
        _state = state;
        _listPanel = new QuestListPanel(data, state, _filter);
        _detailPanel = new QuestDetailPanel(data, state);
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
        {
            IsMouseOver = false;
            return;
        }

        ImGui.SetNextWindowSize(new Vector2(800, 550), ImGuiCond.FirstUseEver);

        Theme.PushWindowStyle();

        if (ImGui.Begin("Adventure Guide", ref _visible, ImGuiWindowFlags.NoCollapse))
        {
            IsMouseOver = ImGui.IsWindowHovered(ImGuiHoveredFlags.RootAndChildWindows)
                       || ImGui.IsAnyItemHovered();

            DrawTabBar();
        }
        else
        {
            IsMouseOver = false;
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
