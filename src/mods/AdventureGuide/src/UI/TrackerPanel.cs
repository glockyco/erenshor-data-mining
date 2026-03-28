using System.Numerics;
using AdventureGuide.Frontier;
using AdventureGuide.Graph;
using AdventureGuide.State;
using AdventureGuide.Views;
using ImGuiNET;

namespace AdventureGuide.UI;

/// <summary>
/// Compact quest tracker sidebar. Two lines per tracked quest:
/// Line 1: quest name + status badge
/// Line 2: closest frontier node summary (what to do next)
///
/// Replaces TrackerWindow with a simpler, graph-driven design.
/// </summary>
public sealed class TrackerPanel
{
    private readonly EntityGraph _graph;
    private readonly QuestStateTracker _tracker;
    private readonly GameState _state;
    private readonly TrackerState _trackerState;
    private readonly QuestViewBuilder _viewBuilder;
    private readonly NavigationSet _navSet;

    public TrackerPanel(
        EntityGraph graph,
        QuestStateTracker tracker,
        GameState state,
        TrackerState trackerState,
        QuestViewBuilder viewBuilder,
        NavigationSet navSet)
    {
        _graph = graph;
        _tracker = tracker;
        _state = state;
        _trackerState = trackerState;
        _viewBuilder = viewBuilder;
        _navSet = navSet;
    }

    private bool _visible = true;
    public bool Visible => _visible;
    public void Toggle() => _visible = !_visible;
    public void Show() => _visible = true;
    public void Hide() => _visible = false;

    public void Draw()
    {
        if (!_visible) return;
        var tracked = _trackerState.TrackedQuests;
        if (tracked.Count == 0) return;

        ImGui.SetNextWindowSize(new Vector2(340f, 260f), ImGuiCond.FirstUseEver);
        ImGui.SetNextWindowPos(new Vector2(10f, 10f), ImGuiCond.FirstUseEver);

        Theme.PushWindowStyle();

        var flags = ImGuiWindowFlags.NoFocusOnAppearing;
        if (ImGui.Begin("Quest Tracker", ref _visible, flags))
        {
            foreach (var questKey in tracked)
            {
                var node = _graph.GetNode(questKey);
                if (node == null || node.Type != NodeType.Quest) continue;

                DrawTrackedQuest(questKey, node);
                ImGui.Spacing();
            }
        }

        Theme.ClampWindowPosition();
        ImGui.End();
        Theme.PopWindowStyle();
    }

    private void DrawTrackedQuest(string questKey, Node node)
    {
        var questState = _state.GetState(questKey);

        // Line 1: name + status
        uint nameColor = questState switch
        {
            QuestCompleted => Theme.QuestCompleted,
            QuestActive => Theme.QuestActive,
            QuestImplicitlyActive => Theme.QuestImplicit,
            _ => Theme.TextPrimary,
        };

        ImGui.PushStyleColor(ImGuiCol.Text, nameColor);
        ImGui.Text(node.DisplayName);
        ImGui.PopStyleColor();

        // NAV button
        ImGui.SameLine();
        bool isNav = _navSet.Contains(questKey);
        if (isNav)
            ImGui.PushStyleColor(ImGuiCol.Button, Theme.Accent);

        if (ImGui.SmallButton($"NAV###{questKey}_tracker"))
        {
            if (ImGui.GetIO().KeyShift)
                _navSet.Toggle(questKey);
            else
                _navSet.Override(questKey);
        }

        if (isNav)
            ImGui.PopStyleColor();

        // Line 2: frontier summary
        if (questState is QuestCompleted)
        {
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.QuestCompleted);
            ImGui.Text("  ✓ Completed");
            ImGui.PopStyleColor();
        }
        else
        {
            string summary = GetFrontierSummary(questKey);
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
            ImGui.Text($"  → {summary}");
            ImGui.PopStyleColor();
        }
    }

    /// <summary>
    /// Build a one-line summary of the closest frontier node.
    /// </summary>
    private string GetFrontierSummary(string questKey)
    {
        var root = _viewBuilder.Build(questKey);
        if (root == null) return "Unknown";

        var frontier = FrontierComputer.ComputeFrontier(root, _state);
        if (frontier.Count == 0) return "Ready to turn in";

        // Pick the first frontier node for summary (closest would
        // require position resolution — deferred to NavigationEngine)
        foreach (var key in frontier)
        {
            var node = _graph.GetNode(key);
            if (node == null) continue;
            string suffix = frontier.Count > 1 ? $" (+{frontier.Count - 1} more)" : "";
            return $"{node.DisplayName}{suffix}";
        }

        return "In progress";
    }
}
