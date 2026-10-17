using AdventureGuide.Config;
using AdventureGuide.Data;
using AdventureGuide.Navigation;
using AdventureGuide.State;
using ImGuiNET;

namespace AdventureGuide.UI;

/// <summary>
/// Renders the right-side quest detail view using Dear ImGui.
/// Sections ordered by importance: Header, Objectives, Rewards, Prerequisites, Chain.
/// </summary>
public sealed class QuestDetailPanel
{
    private readonly GuideData _data;
    private readonly QuestStateTracker _state;
    private readonly NavigationController _nav;
    private readonly TrackerState _tracker;
    private readonly GuideConfig _config;

    // Rebuilt only when selection or quest/inventory/workflow state changes.
    // Pre-cache closed trees too, so opening a tree does not allocate.
    private readonly Dictionary<QuestEntry, QuestDisplayCache> _questDisplay = new();
    private readonly HashSet<string> _visited = new();
    private readonly List<string> _acquisitionLines = new();
    private readonly List<string> _completionLines = new();
    private readonly List<(string Text, bool Secondary)> _rewardLines = new();
    private readonly List<(Prerequisite Prerequisite, string Label)> _prerequisites = new();
    private readonly Dictionary<QuestStep, ZoneLineAlternativeLabels> _zoneLineLabels = new();
    private readonly Dictionary<ZoneLineEntry, List<GateRequirement>> _zoneRequirements = new();
    private HashSet<string>? _stepTreeQuestKeys;
    private DisplayCacheRevision _displayCacheRevision;
    private string? _levelZoneLine;

    /// <summary>Max sub-quest nesting depth to prevent runaway recursion.</summary>
    private const int MaxSubQuestDepth = 5;

    public QuestDetailPanel(
        GuideData data,
        QuestStateTracker state,
        NavigationController nav,
        TrackerState tracker,
        GuideConfig config
    )
    {
        _data = data;
        _state = state;
        _nav = nav;
        _tracker = tracker;
        _config = config;
    }

    public void Draw()
    {
        var selectedKey = _state.SelectedQuestKey;
        var version = _state.Version;
        if (!_displayCacheRevision.IsCurrent(selectedKey, version))
        {
            _displayCacheRevision.Invalidate();
            RebuildDisplayCache(selectedKey);
            _displayCacheRevision.Commit(selectedKey, version);
        }

        if (_state.SelectedQuestKey == null)
        {
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
            Theme.TextWrapped("Select a quest from the list.");
            ImGui.PopStyleColor();
            return;
        }

        var quest = _data.GetByRuntimeKey(_state.SelectedQuestKey);
        if (quest == null)
        {
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
            Theme.TextWrapped("Quest not found in guide data.");
            ImGui.PopStyleColor();
            return;
        }

        DrawHeader(quest);
        DrawObjectives(quest);
        DrawRewards(quest);
        DrawPrerequisites(quest);
    }

    // ── Header ──────────────────────────────────────────────────────

    private void DrawHeader(QuestEntry quest)
    {
        // Track/Untrack button inline before quest name
        if (_tracker.Enabled)
        {
            bool tracked = _tracker.IsTracked(quest.RuntimeKey);
            bool completed = _state.IsCompleted(quest);
            if (!completed || tracked)
            {
                if (tracked)
                    ImGui.PushStyleColor(ImGuiCol.Button, Theme.Accent);
                if (ImGui.SmallButton(tracked ? "[Untrack]" : "[Track]"))
                {
                    if (tracked)
                        _tracker.Untrack(quest.RuntimeKey);
                    else
                        _tracker.Track(quest.RuntimeKey);
                }
                if (tracked)
                    ImGui.PopStyleColor();
                ImGui.SameLine();
            }
        }

        // Quest name in header color
        ImGui.PushStyleColor(ImGuiCol.Text, Theme.Header);
        Theme.TextWrapped(quest.DisplayName);
        ImGui.PopStyleColor();

        // Level + zone on one line (replaces separate "Zone:" line)
        DrawLevelZoneLine(quest);

        // All acquisition sources (not just dialog)
        foreach (var line in _acquisitionLines)
        {
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
            ImGui.TextUnformatted(line);
            ImGui.PopStyleColor();
        }

        // Turn-in location
        foreach (var line in _completionLines)
        {
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
            ImGui.TextUnformatted(line);
            ImGui.PopStyleColor();
        }

        // Description
        if (quest.Description != null)
        {
            ImGui.Spacing();
            Theme.TextWrapped(quest.Description);
        }

        ImGui.Spacing();
        ImGui.Separator();
        ImGui.Spacing();
    }

    private void DrawLevelZoneLine(QuestEntry quest)
    {
        if (_levelZoneLine == null)
            return;

        ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
        ImGui.TextUnformatted(_levelZoneLine);

        // Tooltip: show all steps with their levels, mark the driving step
        if (ImGui.IsItemHovered() && quest.Steps is { Count: > 0 })
        {
            ImGui.BeginTooltip();
            ImGui.TextUnformatted("Quest level: hardest step");
            ImGui.Separator();
            int? questLvl = quest.LevelEstimate?.Recommended;
            foreach (var step in quest.Steps)
            {
                int? stepLvl = step.LevelEstimate?.Recommended;
                string lvlStr = stepLvl.HasValue ? $"Lv {stepLvl, 2}" : "    ";
                bool isDriving = questLvl.HasValue && stepLvl == questLvl;
                string marker = isDriving ? " <" : "";
                uint tipColor = isDriving ? Theme.TextPrimary : Theme.TextSecondary;
                ImGui.PushStyleColor(ImGuiCol.Text, tipColor);
                ImGui.TextUnformatted($"  {step.Order}. {step.Description}  {lvlStr}{marker}");
                ImGui.PopStyleColor();
            }
            ImGui.EndTooltip();
        }

        ImGui.PopStyleColor();
    }

    // ── Objectives ──────────────────────────────────────────────────

    private void DrawObjectives(QuestEntry quest)
    {
        if (!quest.HasSteps)
        {
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
            Theme.TextWrapped("No guide data available for this quest.");
            ImGui.PopStyleColor();
            return;
        }

        if (_state.Workflows.IsUnverifiable(quest))
        {
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.Warning);
            Theme.TextWrapped(
                "Workflow state is ambiguous after reload. Re-enter the trigger area with the required item."
            );
            ImGui.PopStyleColor();
        }

        if (!ImGui.CollapsingHeader("Objectives", ImGuiTreeNodeFlags.DefaultOpen))
            return;

        _visited.Clear();
        _visited.Add(quest.StableKey);
        ImGui.Indent();
        DrawSteps(quest, _visited);
        ImGui.Unindent();
    }

    /// <summary>
    /// Render a quest's step list with or-group separators and step state coloring.
    /// Reused for both top-level objectives and inline sub-quest rendering.
    /// Caller handles indentation; this method handles PushID scoping.
    /// </summary>
    private void DrawSteps(QuestEntry quest, HashSet<string> visited)
    {
        if (quest.Steps == null || quest.Steps.Count == 0)
            return;

        ImGui.PushID(quest.RuntimeKey);

        int currentStepIndex = _questDisplay[quest].CurrentStepIndex;
        string? prevOrGroup = null;

        for (int i = 0; i < quest.Steps.Count; i++)
        {
            var step = quest.Steps[i];

            if (
                (step.OrGroup != null && step.OrGroup == prevOrGroup)
                || (
                    i > 0
                    && step.RequirementVariant != null
                    && quest.Steps[i - 1].RequirementVariant != null
                    && step.RequirementVariant != quest.Steps[i - 1].RequirementVariant
                )
            )
            {
                ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
                ImGui.TextUnformatted("  -- OR --");
                ImGui.PopStyleColor();
            }

            StepState state;
            if (
                step.RequirementVariant != null
                    ? currentStepIndex == quest.Steps.Count
                        || _questDisplay[quest].Steps[step].HasRequiredQuantity
                    : i < currentStepIndex
            )
                state = StepState.Completed;
            else if (i == currentStepIndex)
                state = StepState.Current;
            else
                state = StepState.Future;

            DrawStep(step, state, quest, visited);

            prevOrGroup = step.OrGroup;
        }

        ImGui.PopID();
    }

    private enum StepState
    {
        Completed,
        Current,
        Future,
    }

    private void DrawStep(
        QuestStep step,
        StepState state,
        QuestEntry quest,
        HashSet<string> visited
    )
    {
        ImGui.PushID(step.Order);
        uint color = state switch
        {
            StepState.Completed => Theme.QuestCompleted,
            StepState.Current => Theme.QuestActive,
            _ => Theme.TextPrimary,
        };
        var display = _questDisplay[quest].Steps[step];

        // Collect steps: show have/need count and override color
        // when items are in hand, regardless of step pointer position.
        if (
            (step.Action is "collect" or "obtain")
            && step.TargetKey != null
            && step.Quantity.HasValue
        )
        {
            if (display.HasRequiredQuantity)
                color = Theme.QuestCompleted;
        }

        // Complete-quest steps: override color when target quest is done.
        if (step.Action == "complete_quest" && step.TargetKey != null)
        {
            var target = _data.GetByStableKey(step.TargetKey);
            if (target != null && _state.IsCompleted(target))
                color = Theme.QuestCompleted;
        }

        // Step suffix (zone and level) is cached with the have/need count.

        // [NAV] button first (fixed width), then step text
        DrawNavButton(step, quest);

        ImGui.PushStyleColor(ImGuiCol.Text, color);
        Theme.TextWrapped(display.Text);
        ImGui.PopStyleColor();

        if (NavigationDisplay.IsOrigin(_nav, quest, step))
            NavigationDisplay.DrawRequirements(_nav, _state.CurrentZone);
        else
            DrawGateRequirements(display.Requirements);

        // Drop/vendor sources and tips for collect steps
        DrawStepSources(step, quest, visited);

        // Sub-quest tree for complete_quest steps: show the target
        // quest's steps inline so the player sees what they need to do.
        DrawSubQuestSteps(step, quest, visited);

        // Show alternative zone lines when cross-zone navigating this step
        if (_nav.IsNavigating(quest.RuntimeKey, step.Order))
        {
            var alternatives = _nav.GetAlternativeZoneLines(_state.CurrentZone);
            if (alternatives.Count > 1)
                DrawZoneLineAlternatives(alternatives, step);
        }
        ImGui.PopID();
    }

    private bool IsNavigationEnabled => _config.ShowArrow.Value || _config.ShowGroundPath.Value;

    private void DrawNavButton(QuestStep step, QuestEntry quest)
    {
        if (!IsNavigationEnabled)
            return;
        if (step.TargetKey == null)
            return;

        // Character targets need spawn data; item targets need at least one
        // available source with spawn data or a scene.
        var display = _questDisplay[quest].Steps[step];
        bool navigable = display.Navigable;
        bool isActive = _nav.IsNavigating(quest.RuntimeKey, step.Order);

        if (!navigable && !isActive)
        {
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
            ImGui.PushStyleVar(ImGuiStyleVar.Alpha, 0.4f);
            ImGui.SmallButton(display.NavLabel);
            ImGui.PopStyleVar();
            ImGui.PopStyleColor();

            if (ImGui.IsItemHovered(ImGuiHoveredFlags.AllowWhenDisabled))
            {
                ImGui.BeginTooltip();
                ImGui.TextUnformatted("No known source");
                ImGui.EndTooltip();
            }

            ImGui.SameLine();
            return;
        }

        if (isActive)
            ImGui.PushStyleColor(ImGuiCol.Button, Theme.QuestActive);

        if (ImGui.SmallButton(display.NavLabel))
        {
            if (isActive)
                _nav.Clear();
            else
                _nav.NavigateTo(step, quest, _state.CurrentZone);
        }

        if (isActive)
            ImGui.PopStyleColor();

        if (ImGui.IsItemHovered())
        {
            ImGui.BeginTooltip();
            if (isActive)
                ImGui.TextUnformatted("Click to stop navigating");
            else
                ImGui.TextUnformatted($"Navigate to {step.TargetName ?? step.Description}");
            ImGui.EndTooltip();
        }

        // Keep cursor on same line so the step text follows the button
        ImGui.SameLine();
    }

    /// <summary>One preview before navigation, with all alternatives behind an explicit picker.</summary>
    private void DrawStepSources(QuestStep step, QuestEntry quest, HashSet<string> visited)
    {
        if (
            (step.Action is not "collect" and not "obtain" and not "read")
            || step.TargetName == null
        )
        {
            DrawTips(step, quest);
            return;
        }

        var display = _questDisplay[quest].Steps[step];
        var visibleSources = display.VisibleSources;
        if (visibleSources.Count == 0)
        {
            DrawTips(step, quest);
            return;
        }

        ImGui.Indent();
        ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);

        ImGui.PushID(step.Order);
        if (visibleSources.Count == 1)
        {
            var choice = visibleSources[0];
            var source = choice.Primary;
            bool alreadyShown =
                NavigationDisplay.IsOrigin(_nav, quest, step)
                && _nav.SelectedItemSource is ItemSource selected
                && choice.Contains(selected)
                && source.Children is not { Count: > 0 }
                && source.Type != "quest_reward";
            if (!alreadyShown)
                DrawSource(choice, quest, step, visited);
        }
        else if (ImGui.TreeNode("Choose a source"))
        {
            foreach (var source in visibleSources)
                DrawSource(source, quest, step, visited);
            ImGui.TreePop();
        }
        else if (
            !NavigationDisplay.IsOrigin(_nav, quest, step)
            && display.PreviewSource is ItemSource preview
        )
            DrawSourceText(display.Sources[(preview, 0)]);
        ImGui.PopID();

        ImGui.PopStyleColor();
        ImGui.Unindent();

        DrawTips(step, quest);
    }

    private void DrawZoneLineAlternatives(
        List<(ZoneLineEntry line, float distance, bool isSelected, bool isAccessible)> alternatives,
        QuestStep step
    )
    {
        ImGui.Indent();
        ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);

        if (!_zoneLineLabels.TryGetValue(step, out var labels))
        {
            labels = new ZoneLineAlternativeLabels(step.Order);
            _zoneLineLabels.Add(step, labels);
        }
        if (ImGui.TreeNode(labels.Header(alternatives.Count)))
        {
            for (int i = 0; i < alternatives.Count; i++)
            {
                var (line, distance, isActive, isAccessible) = alternatives[i];
                var destination = _nav.GetZoneLineDestinationDisplay(line);
                if (destination == null)
                    continue;
                var row = labels.Row(i, destination, distance);
                if (!isAccessible)
                {
                    // Locked zone line: dimmed text
                    ImGui.PushStyleVar(ImGuiStyleVar.Alpha, 0.3f);
                    ImGui.TextUnformatted(row.Text);
                    ImGui.PopStyleVar();

                    if (!_zoneRequirements.TryGetValue(line, out var requirements))
                    {
                        requirements = CacheGateRequirements(_state.Gates.Explain(line.Condition));
                        _zoneRequirements.Add(line, requirements);
                    }
                    ImGui.PushID(i);
                    DrawGateRequirements(requirements);
                    ImGui.PopID();
                }
                else
                {
                    if (isActive)
                        ImGui.PushStyleColor(ImGuiCol.Text, Theme.QuestActive);

                    if (ImGui.Selectable(row.Selectable))
                        _nav.PinZoneLine(line);

                    if (isActive)
                        ImGui.PopStyleColor();

                    if (ImGui.IsItemHovered())
                    {
                        ImGui.BeginTooltip();
                        ImGui.TextUnformatted(row.Tooltip);
                        ImGui.EndTooltip();
                    }
                }
            }
            ImGui.TreePop();
        }

        ImGui.PopStyleColor();
        ImGui.Unindent();
    }

    private void DrawSource(
        SourceChoice choice,
        QuestEntry quest,
        QuestStep step,
        HashSet<string> visited,
        int depth = 0,
        bool allowNavigation = true
    )
    {
        var stepDisplay = _questDisplay[quest].Steps[step];
        var choiceDisplay = stepDisplay.Choices[(choice, depth)];
        var src =
            _nav.SelectedItemSource is ItemSource endpoint && choice.Contains(endpoint)
                ? endpoint
                : choiceDisplay.Representative;
        var display = stepDisplay.Sources[(src, depth)];
        bool isOrigin = NavigationDisplay.IsOrigin(_nav, quest, step);
        bool chosen = isOrigin && ReferenceEquals(_nav.ChosenSourceChoice, choice);
        bool selected =
            isOrigin && _nav.SelectedItemSource is ItemSource current && choice.Contains(current);
        ImGui.PushID(choiceDisplay.RowId);
        if (
            allowNavigation
            && (depth > 0 || stepDisplay.VisibleSources.Count > 1)
            && choiceDisplay.Navigable
            && IsNavigationEnabled
        )
        {
            bool activeChoice = chosen || (_nav.ChosenSourceChoice == null && selected);
            if (activeChoice)
                ImGui.PushStyleColor(ImGuiCol.Button, Theme.Accent);
            if (ImGui.SmallButton("[NAV]") && !activeChoice)
                _nav.NavigateToSource(choice, step, quest, _state.CurrentZone);
            if (activeChoice)
                ImGui.PopStyleColor();
            ImGui.SameLine(0, 4f * _config.ResolvedUiScale);
        }
        ImGui.BeginGroup();
        DrawSourceText(display);

        DrawGateRequirements(display.Requirements, isOrigin ? _nav.ImmediateRequirement : null);

        if (choiceDisplay.LocationsLabel is string locations && ImGui.TreeNode(locations))
        {
            foreach (var location in choice.Locations)
            {
                var locationDisplay = stepDisplay.Sources[(location.Primary, depth)];
                if (locationDisplay.Label != display.Label)
                    Theme.TextWrapped(locationDisplay.Label);
                Theme.TextWrapped(locationDisplay.PlacementLabel);
                if (locationDisplay.Odds is string odds && odds != display.Odds)
                    Theme.TextWrapped(odds);
                if (
                    locationDisplay.Instruction is string preparation
                    && preparation != display.Instruction
                )
                    Theme.TextWrapped(preparation);
                DrawGateRequirements(locationDisplay.Requirements);
            }
            ImGui.TreePop();
        }

        bool questTree = false;
        if (src.Type == "quest_reward" && src.QuestKey != null)
        {
            var subQuest = _data.GetByStableKey(src.QuestKey);
            if (
                subQuest?.Steps is { Count: > 0 }
                && visited.Count <= MaxSubQuestDepth
                && !visited.Contains(subQuest.StableKey)
            )
            {
                DrawQuestRewardTree(subQuest, display, visited);
                questTree = true;
            }
            else if (subQuest != null && ImGui.SmallButton("Open quest"))
                _state.SelectQuest(subQuest);
        }
        if (!questTree && display.Children.Count > 0 && ImGui.TreeNode("Sources and ingredients"))
        {
            foreach (var child in display.Children)
                DrawSource(
                    child,
                    quest,
                    step,
                    visited,
                    depth + 1,
                    allowNavigation && display.NeedsInput
                );
            ImGui.TreePop();
        }
        ImGui.EndGroup();
        ImGui.PopID();
    }

    private static void DrawSourceText(SourceDisplayCache display)
    {
        float fontSize = ImGui.GetFontSize();
        if (display.FontSize != fontSize)
        {
            display.FontSize = fontSize;
            display.InlineWidth = ImGui.CalcTextSize(display.InlineLabel).X;
        }
        bool inline =
            display.KeepLocationWithAction
            || display.InlineWidth <= ImGui.GetContentRegionAvail().X;
        if (!display.Available)
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.SourceDimmed);
        Theme.TextWrapped(inline ? display.InlineLabel : display.Label);
        if (!inline && display.Location is string location)
            Theme.TextWrapped(location);
        if (!display.Available)
            ImGui.PopStyleColor();
        if (display.Odds is string odds)
            Theme.TextWrapped(odds);
        if (display.Instruction is string preparation)
            Theme.TextWrapped(preparation);
    }

    /// <summary>
    /// For complete_quest steps, render the target quest's steps inline
    /// as an indented sub-tree. Shows an "Open quest" link and the full
    /// step list with NAV buttons, sources, and tips.
    /// </summary>
    private void DrawSubQuestSteps(QuestStep step, QuestEntry quest, HashSet<string> visited)
    {
        if (step.Action != "complete_quest" || step.TargetKey == null)
            return;

        var subQuest = _data.GetByStableKey(step.TargetKey);
        if (subQuest?.Steps == null || subQuest.Steps.Count == 0)
            return;
        if (visited.Count > MaxSubQuestDepth || visited.Contains(subQuest.StableKey))
            return;

        ImGui.Indent();

        // "Open quest" link
        ImGui.PushStyleColor(ImGuiCol.Text, Theme.QuestActive);
        if (ImGui.Selectable(_questDisplay[quest].Steps[step].SubQuestLabel!))
            _state.SelectQuest(subQuest);
        ImGui.PopStyleColor();

        // Render the sub-quest's steps inline
        visited.Add(subQuest.StableKey);
        DrawSteps(subQuest, visited);
        visited.Remove(subQuest.StableKey);

        ImGui.Unindent();
    }

    /// <summary>
    /// Render a quest_reward source as an inline sub-quest tree: the TreeNode
    /// header shows the source label, and the body contains the sub-quest's
    /// steps with full treatment (NAV buttons, sources, tips).
    /// </summary>
    private void DrawQuestRewardTree(
        QuestEntry subQuest,
        SourceDisplayCache display,
        HashSet<string> visited
    )
    {
        bool isCompleted = _state.IsCompleted(subQuest);
        var flags = ImGuiTreeNodeFlags.None;

        if (isCompleted)
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.QuestCompleted);

        bool open = ImGui.TreeNodeEx(display.QuestTreeLabel!, flags);

        if (isCompleted)
            ImGui.PopStyleColor();

        if (!open)
            return;

        // "Open quest" link — jump to the full quest detail page
        ImGui.PushStyleColor(ImGuiCol.Text, Theme.QuestActive);
        if (ImGui.Selectable(display.OpenQuestLabel!))
        {
            _state.SelectQuest(subQuest);
        }
        ImGui.PopStyleColor();

        // Render the sub-quest's steps inline
        visited.Add(subQuest.StableKey);
        DrawSteps(subQuest, visited);
        visited.Remove(subQuest.StableKey);

        ImGui.TreePop();
    }

    private void DrawTips(QuestStep step, QuestEntry quest)
    {
        if (step.Tips == null || step.Tips.Count == 0)
            return;

        ImGui.Indent();
        if (ImGui.TreeNode(_questDisplay[quest].Steps[step].TipsLabel))
        {
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
            foreach (var tip in step.Tips)
                Theme.TextWrapped(tip);
            ImGui.PopStyleColor();
            ImGui.TreePop();
        }
        ImGui.Unindent();
    }

    // ── Rewards ─────────────────────────────────────────────────────

    private void DrawRewards(QuestEntry quest)
    {
        var r = quest.Rewards;
        if (r == null)
            return;
        if (!HasAnyRewards(r))
            return;

        // Expanded by default — rewards are primary motivation
        if (!ImGui.CollapsingHeader("Rewards", ImGuiTreeNodeFlags.DefaultOpen))
            return;

        ImGui.Indent();

        foreach (var line in _rewardLines)
        {
            if (line.Secondary)
                ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
            ImGui.TextUnformatted(line.Text);
            if (line.Secondary)
                ImGui.PopStyleColor();
        }

        ImGui.Unindent();
    }

    private static bool HasAnyRewards(RewardInfo r) =>
        r.XP > 0
        || r.Gold > 0
        || r.ItemName != null
        || r.VendorUnlock != null
        || r.UnlockedZoneLines is { Count: > 0 }
        || r.UnlockedCharacters is { Count: > 0 }
        || r.NextQuestName != null
        || r.FactionEffects is { Count: > 0 }
        || r.AlsoCompletes is { Count: > 0 };

    // ── Prerequisites ───────────────────────────────────────────────

    private void DrawPrerequisites(QuestEntry quest)
    {
        // Prerequisites already visible in the step tree are filtered at
        // cache rebuild (quest_reward sources and complete_quest targets).
        var filtered = _prerequisites;
        if (filtered.Count == 0)
            return;

        // Auto-expand when any prerequisite is incomplete
        bool anyIncomplete = false;
        foreach (var p in filtered)
        {
            if (!IsPrerequisiteCompleted(p.Prerequisite))
            {
                anyIncomplete = true;
                break;
            }
        }

        var flags = anyIncomplete ? ImGuiTreeNodeFlags.DefaultOpen : ImGuiTreeNodeFlags.None;
        if (!ImGui.CollapsingHeader("Prerequisites", flags))
            return;

        ImGui.Indent();
        foreach (var prereq in filtered)
        {
            bool completed = IsPrerequisiteCompleted(prereq.Prerequisite);
            var color = completed ? Theme.QuestCompleted : Theme.TextPrimary;

            ImGui.PushStyleColor(ImGuiCol.Text, color);
            if (ImGui.Selectable(prereq.Label))
            {
                var target = _data.GetByStableKey(prereq.Prerequisite.QuestKey);
                if (target != null)
                    _state.SelectQuest(target);
            }
            ImGui.PopStyleColor();
        }
        ImGui.Unindent();
    }

    /// <summary>
    /// Collect quest stable keys that are already visible in the step tree:
    /// complete_quest step targets and quest_reward item sources.
    /// Called once per display-cache rebuild, not during frame rendering.
    /// </summary>
    private static HashSet<string> CollectStepTreeQuestKeys(QuestEntry quest)
    {
        var keys = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        if (quest.Steps != null)
        {
            foreach (var step in quest.Steps)
            {
                if (step.Action == "complete_quest" && step.TargetKey != null)
                    keys.Add(step.TargetKey);
                if (step.Sources != null)
                    CollectQuestRewardKeys(step.Sources, keys);
            }
        }
        if (quest.RequiredItems != null)
        {
            foreach (var ri in quest.RequiredItems)
            {
                if (ri.Sources != null)
                    CollectQuestRewardKeys(ri.Sources, keys);
            }
        }
        return keys;
    }

    private static void CollectQuestRewardKeys(List<ItemSource> sources, HashSet<string> keys)
    {
        foreach (var src in sources)
        {
            if (src.Type == "quest_reward" && src.QuestKey != null)
                keys.Add(src.QuestKey);
            if (src.Children != null)
                CollectQuestRewardKeys(src.Children, keys);
        }
    }

    private bool IsPrerequisiteCompleted(Prerequisite prereq)
    {
        var quest = _data.GetByStableKey(prereq.QuestKey);
        return quest != null && _state.IsCompleted(quest);
    }

    // ── Display cache ────────────────────────────────────────────────

    private sealed class QuestDisplayCache
    {
        public int CurrentStepIndex;
        public readonly Dictionary<QuestStep, StepDisplayCache> Steps = new();
    }

    private sealed class StepDisplayCache
    {
        public string Text = "";
        public string NavLabel = "";
        public string TipsLabel = "";
        public ItemSource? PreviewSource;
        public string? SubQuestLabel;

        public List<GateRequirement>? Requirements;
        public bool HasRequiredQuantity;
        public bool Navigable;
        public readonly List<SourceChoice> VisibleSources = new();
        public readonly Dictionary<
            (SourceChoice Choice, int Depth),
            SourceChoiceDisplayCache
        > Choices = new();
        public readonly Dictionary<(ItemSource Source, int Depth), SourceDisplayCache> Sources =
            new();
    }

    private sealed class SourceChoiceDisplayCache
    {
        public int RowId;
        public ItemSource Representative = null!;
        public bool Navigable;
        public string? LocationsLabel;
    }

    private sealed class SourceDisplayCache
    {
        public string Label = "";
        public string PlacementLabel = "";
        public string? Instruction;
        public string? Odds;
        public string? Location;
        public string InlineLabel = "";
        public bool KeepLocationWithAction;
        public float InlineWidth;
        public float FontSize;
        public bool Navigable;
        public bool Available;
        public string? QuestTreeLabel;
        public string? OpenQuestLabel;
        public List<GateRequirement>? Requirements;
        public bool NeedsInput;
        public IReadOnlyList<SourceChoice> Children = Array.Empty<SourceChoice>();
    }

    private sealed class GateRequirement
    {
        public string Text = "";
        public QuestEntry? Quest;
    }

    private List<GateRequirement> CacheGateRequirements(IReadOnlyList<GateAtom> atoms)
    {
        var requirements = new List<GateRequirement>(atoms.Count);
        foreach (var atom in atoms)
        {
            requirements.Add(
                new GateRequirement
                {
                    Text = _state.Gates.Describe(atom),
                    Quest = atom.Kind is GateAtomKind.QuestDone or GateAtomKind.QuestNotDone
                        ? _data.GetByDBName(atom.Ref)
                        : null,
                }
            );
        }
        return requirements;
    }

    private void DrawGateRequirements(
        List<GateRequirement>? requirements,
        string? alreadyShown = null
    )
    {
        if (requirements == null || requirements.Count == 0)
            return;
        ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
        for (int i = 0; i < requirements.Count; i++)
        {
            var requirement = requirements[i];
            if (string.Equals(requirement.Text, alreadyShown, StringComparison.Ordinal))
                continue;
            if (requirement.Quest is QuestEntry quest)
            {
                ImGui.PushID(i);
                if (ImGui.Selectable(requirement.Text))
                    _state.SelectQuest(quest);
                ImGui.PopID();
            }
            else
                Theme.TextWrapped(requirement.Text);
        }
        ImGui.PopStyleColor();
    }

    /// <summary>
    /// Rebuild formatted labels and filtered collections for the selected
    /// quest and all drawable inline sub-quests, including closed trees.
    /// Nothing is retained across a selection or state-version change.
    /// </summary>
    private void RebuildDisplayCache(string? questKey)
    {
        _questDisplay.Clear();
        _zoneLineLabels.Clear();
        _zoneRequirements.Clear();
        _visited.Clear();
        _acquisitionLines.Clear();
        _completionLines.Clear();
        _rewardLines.Clear();
        _prerequisites.Clear();
        _stepTreeQuestKeys = null;
        _levelZoneLine = null;

        var quest = questKey == null ? null : _data.GetByRuntimeKey(questKey);
        if (quest == null)
            return;

        CacheHeader(quest);
        CacheRewards(quest.Rewards);
        _stepTreeQuestKeys = CollectStepTreeQuestKeys(quest);
        if (quest.Prerequisites != null)
        {
            foreach (var prereq in quest.Prerequisites)
            {
                if (_stepTreeQuestKeys.Contains(prereq.QuestKey))
                    continue;
                string label =
                    prereq.Item != null ? $"{prereq.QuestName} ({prereq.Item})" : prereq.QuestName;
                _prerequisites.Add((prereq, $"{label}##prereq_{prereq.QuestKey}"));
            }
        }

        // Use the drawing set here too, warming its capacity for every
        // possible expanded path before allocation-free frame rendering.
        _visited.Add(quest.StableKey);
        CacheStepTree(quest, _visited);
        _visited.Clear();
    }

    private void CacheHeader(QuestEntry quest)
    {
        int? level = quest.LevelEstimate?.Recommended;
        string? zone = quest.ZoneContext;
        bool repeatable = quest.Flags is { Repeatable: true };
        if (level != null || zone != null || repeatable)
        {
            string meta = level != null ? $"Lv {level}" : "";
            if (zone != null)
            {
                if (meta.Length > 0)
                    meta += "  \u00b7  ";
                meta += zone;
            }
            if (repeatable)
            {
                if (meta.Length > 0)
                    meta += "  \u00b7  ";
                meta += "Repeatable";
            }
            _levelZoneLine = meta;
        }

        if (quest.Acquisition != null)
        {
            foreach (var acq in quest.Acquisition)
            {
                string? line = acq.Method switch
                {
                    "dialog" when acq.SourceName != null => $"Given by: {acq.SourceName}",
                    "item_read" when acq.SourceName != null => $"Read: {acq.SourceName}",
                    "zone_entry" when acq.SourceName != null => $"Enter: {acq.SourceName}",
                    "quest_chain" when acq.SourceName != null => $"Chain from: {acq.SourceName}",
                    _ => acq.SourceName != null ? $"From: {acq.SourceName}" : null,
                };
                if (line == null)
                    continue;
                if (acq.ZoneName != null && acq.Method == "dialog")
                    line += $" ({acq.ZoneName})";
                _acquisitionLines.Add(line);
            }
        }

        if (quest.Completion != null)
        {
            foreach (var comp in quest.Completion)
            {
                string? line = comp.Method switch
                {
                    "item_turnin" or "dialog" when comp.SourceName != null =>
                        $"Turn in to: {comp.SourceName}",
                    "zone" when comp.SourceName != null => $"Complete at: {comp.SourceName}",
                    _ when comp.SourceName != null => $"Complete: {comp.SourceName}",
                    _ => null,
                };
                if (line == null)
                    continue;
                if (comp.ZoneName != null && comp.Method is "item_turnin" or "dialog")
                    line += $" ({comp.ZoneName})";
                _completionLines.Add(line);
            }
        }
    }

    private void CacheRewards(RewardInfo? r)
    {
        if (r == null)
            return;
        if (r.XP > 0)
            _rewardLines.Add(($"{r.XP} XP", false));
        if (r.Gold > 0)
            _rewardLines.Add(($"{r.Gold} Gold", false));
        if (r.ItemName != null)
            _rewardLines.Add((r.ItemName, false));

        // Vendor item unlock
        if (r.VendorUnlock != null)
            _rewardLines.Add(
                ($"Unlocks {r.VendorUnlock.ItemName} at {r.VendorUnlock.VendorName}", false)
            );

        // Zone line unlocks
        if (r.UnlockedZoneLines != null)
        {
            foreach (var zl in r.UnlockedZoneLines)
            {
                string text = $"Opens path from {zl.FromZone} to {zl.ToZone}";
                if (zl.CoRequirements is { Count: > 0 })
                    text += $" (also requires {string.Join(", ", zl.CoRequirements)})";
                _rewardLines.Add((text, false));
            }
        }

        // Character spawn unlocks
        if (r.UnlockedCharacters != null)
        {
            foreach (var ch in r.UnlockedCharacters)
            {
                string text =
                    ch.Zone != null ? $"Enables {ch.Name} in {ch.Zone}" : $"Enables {ch.Name}";
                _rewardLines.Add((text, false));
            }
        }

        // Next quest in chain
        if (r.NextQuestName != null)
            _rewardLines.Add(($"Next: {r.NextQuestName}", true));
        if (r.FactionEffects != null)
        {
            foreach (var fe in r.FactionEffects)
            {
                string sign = fe.Amount >= 0 ? "+" : "";
                _rewardLines.Add(($"{fe.FactionName}: {sign}{fe.Amount}", false));
            }
        }
        if (r.AlsoCompletes is { Count: > 0 })
            _rewardLines.Add(($"Also completes: {string.Join(", ", r.AlsoCompletes)}", true));
    }

    private void CacheStepTree(QuestEntry quest, HashSet<string> visited)
    {
        if (!_questDisplay.TryGetValue(quest, out var display))
        {
            display = new QuestDisplayCache
            {
                CurrentStepIndex = StepProgress.GetCurrentStepIndex(quest, _state, _data),
            };
            _questDisplay.Add(quest, display);
            if (quest.Steps != null)
            {
                foreach (var step in quest.Steps)
                    display.Steps.Add(step, CacheStep(quest, step));
            }
        }
        if (quest.Steps == null)
            return;

        // Traverse each drawable path even for already cached quests:
        // cycle/depth fallbacks depend on the current ancestor set.
        foreach (var step in quest.Steps)
        {
            foreach (var choice in display.Steps[step].VisibleSources)
            foreach (var member in choice.Members)
                CacheSourceQuestTree(member, visited);

            if (step.Action == "complete_quest" && step.TargetKey != null)
                CacheInlineQuest(_data.GetByStableKey(step.TargetKey), visited);
        }
    }

    private void CacheInlineQuest(QuestEntry? quest, HashSet<string> visited)
    {
        if (
            quest?.Steps is not { Count: > 0 }
            || visited.Count > MaxSubQuestDepth
            || visited.Contains(quest.StableKey)
        )
            return;
        visited.Add(quest.StableKey);
        CacheStepTree(quest, visited);
        visited.Remove(quest.StableKey);
    }

    private void CacheSourceQuestTree(ItemSource src, HashSet<string> visited, int depth = 0)
    {
        if (src.Type == "quest_reward" && src.QuestKey != null)
        {
            var subQuest = _data.GetByStableKey(src.QuestKey);
            if (
                subQuest?.Steps is { Count: > 0 }
                && visited.Count <= MaxSubQuestDepth
                && !visited.Contains(subQuest.StableKey)
            )
            {
                CacheInlineQuest(subQuest, visited);
                return;
            }
        }
        if (src.Children != null)
        {
            foreach (var child in src.Children)
                CacheSourceQuestTree(child, visited, depth + 1);
        }
    }

    private StepDisplayCache CacheStep(QuestEntry quest, QuestStep step)
    {
        var display = new StepDisplayCache
        {
            Text = $"{step.Order}. {step.Description}",
            NavLabel = $"[NAV]##{step.Order}",
            TipsLabel = $"Tips##{step.Order}",
        };

        // Collect steps: have/need counts change only with the state version.
        if (StepCountPolicy.ShowsInventoryCount(step))
        {
            int have = _state.CountItem(step.TargetKey!);
            display.Text += $" ({have}/{step.Quantity})";
            display.HasRequiredQuantity = have >= step.Quantity!.Value;
        }

        // The header carries the quest level. Keep collect rows focused on progress.
        if (step.Action is not "collect" and not "obtain" and not "read")
        {
            if (
                step.LevelEstimate?.Factors is { Count: > 0 } factors
                && !string.Equals(
                    factors[0].Name,
                    step.TargetName,
                    StringComparison.OrdinalIgnoreCase
                )
            )
                display.Text += $"  \u00b7  {factors[0].Name}";
            if (
                step.Action is "kill" or "loot"
                && step.LevelEstimate?.Recommended is int level
                && level != quest.LevelEstimate?.Recommended
            )
                display.Text += $" (Lv {level})";
        }

        var sources = ItemSourcePolicy.SourcesFor(quest, step);
        if (step.TargetType == "item" && sources != null)
        {
            foreach (var source in sources)
            {
                if (HasNavigableSource(source))
                {
                    display.Navigable = true;
                    break;
                }
            }
        }
        else if (step.TargetType == "character")
        {
            display.Navigable =
                step.TargetKey != null
                && _data.CharacterSpawns.ContainsKey(step.TargetKey)
                && _state.Gates.IsCharacterAvailable(step.TargetKey);
            if (step.TargetKey != null)
                display.Requirements = CacheGateRequirements(
                    _state.Gates.ExplainCharacter(step.TargetKey)
                );
        }
        else if (step.TargetType == "zone")
            display.Navigable = step.ZoneName != null || step.TargetKey != null;

        if (
            (step.Action is "collect" or "obtain" or "read")
            && step.TargetName != null
            && sources != null
        )
        {
            foreach (var choice in SourceChoice.ForSources(sources))
            {
                display.VisibleSources.Add(choice);
                CacheSourceChoice(choice, step, display);
            }
        }
        foreach (var choice in display.VisibleSources)
        {
            var source = display.Choices[(choice, 0)].Representative;
            if (HasNavigableSource(source))
            {
                display.PreviewSource = source;
                break;
            }
        }
        if (display.PreviewSource == null && display.VisibleSources.Count > 0)
        {
            foreach (var choice in display.VisibleSources)
            {
                var source = display.Choices[(choice, 0)].Representative;
                if (IsSourceAvailable(source))
                {
                    display.PreviewSource = source;
                    break;
                }
            }
            display.PreviewSource ??= display
                .Choices[(display.VisibleSources[0], 0)]
                .Representative;
        }
        if (display.PreviewSource != null)
            display.Navigable |= display.Sources[(display.PreviewSource, 0)].Navigable;

        if (step.Action == "complete_quest" && step.TargetKey != null)
        {
            var subQuest = _data.GetByStableKey(step.TargetKey);
            if (subQuest != null)
                display.SubQuestLabel =
                    $"Open quest: {subQuest.DisplayName}##cq_{step.Order}_{step.TargetKey}";
        }
        return display;
    }

    private void CacheSourceChoice(
        SourceChoice choice,
        QuestStep step,
        StepDisplayCache stepDisplay,
        int depth = 0,
        List<ItemSource>? inputSiblings = null
    )
    {
        if (stepDisplay.Choices.ContainsKey((choice, depth)))
            return;
        var display = new SourceChoiceDisplayCache
        {
            RowId = stepDisplay.Choices.Count,
            Representative = choice.Primary,
            LocationsLabel =
                choice.Locations.Count > 1 ? $"Locations ({choice.Locations.Count})" : null,
        };
        bool available = false;
        bool reachable = false;
        foreach (var member in choice.Members)
        {
            CacheSourceLabels(member, step, stepDisplay, depth, inputSiblings);
            display.Navigable |= CanChooseSource(member, inputSiblings);
            bool candidate = HasNavigableSource(member, inputSiblings);
            if (!reachable && candidate)
                display.Representative = member;
            else if (!reachable && !available && stepDisplay.Sources[(member, depth)].Available)
                display.Representative = member;
            reachable |= candidate;
            available |= stepDisplay.Sources[(member, depth)].Available;
        }
        stepDisplay.Choices.Add((choice, depth), display);
    }

    private void CacheSourceLabels(
        ItemSource src,
        QuestStep step,
        StepDisplayCache stepDisplay,
        int depth = 0,
        List<ItemSource>? inputSiblings = null
    )
    {
        if (stepDisplay.Sources.ContainsKey((src, depth)))
            return;
        double? inputQuantity =
            src.Type == "ingredient"
                ? ItemSourcePolicy.RequiredInputQuantity(src, inputSiblings)
                : null;
        string label = SourceListText.Action(src, inputQuantity: inputQuantity);

        var display = new SourceDisplayCache
        {
            Label = label,
            Location = SourceListText.Location(src),
            KeepLocationWithAction = src.Type is "fishing" or "mining",
            Odds = src.Type == "fishing" ? SourceListText.OptionOdds(src) : null,
            Navigable = CanChooseSource(src, inputSiblings),
            Available = IsSourceAvailable(src),
            NeedsInput = ItemSourcePolicy.NeedsUsedItem(
                src,
                _state.CountItemDelegate,
                inputSiblings
            ),
            Children =
                src.Children == null
                    ? Array.Empty<SourceChoice>()
                    : ItemSourcePolicy.PresentationSources(src.Children),
        };
        display.InlineLabel =
            display.Location == null
                ? label
                : label + (src.Type is "fishing" or "mining" ? " in " : " · ") + display.Location;
        display.PlacementLabel =
            src.X is float x && src.Y is float y && src.Z is float z
                ? $"{display.Location ?? label} · ({x:0.##}, {y:0.##}, {z:0.##})"
                : display.InlineLabel;
        if (
            src.Type != "vendor"
            && src.Instruction is string instruction
            && !SourceListText.RepeatsAction(src, instruction)
        )
            display.Instruction = instruction;
        display.Requirements = CacheGateRequirements(_state.Gates.Explain(src.Condition));
        if (src.AcquisitionKey != null)
            display.Requirements.AddRange(
                CacheGateRequirements(_state.Gates.Explain(src.CanonicalSpawn?.Condition))
            );
        else if (src.SourceKey != null)
            display.Requirements.AddRange(
                CacheGateRequirements(_state.Gates.ExplainCharacter(src.SourceKey))
            );
        foreach (var family in _state.Gates.SourceRequirements(src))
        {
            List<GateAtom>? best = null;
            int missing = int.MaxValue;
            foreach (var group in family)
            {
                int count = 0;
                foreach (var atom in group)
                    if (!_state.Gates.Holds(atom))
                        count++;
                if (count < missing)
                {
                    best = group;
                    missing = count;
                }
            }
            if (best == null || missing == 0)
                continue;
            foreach (var atom in best)
            {
                if (_state.Gates.Holds(atom))
                    continue;
                string text = _state.Gates.Describe(atom);
                if (display.Requirements.Exists(requirement => requirement.Text == text))
                    continue;
                display.Requirements.Add(
                    new GateRequirement
                    {
                        Text = text,
                        Quest = atom.Kind is GateAtomKind.QuestDone or GateAtomKind.QuestNotDone
                            ? _data.GetByDBName(atom.Ref)
                            : null,
                    }
                );
            }
        }
        if (src.Type == "quest_reward" && src.QuestKey != null)
        {
            display.QuestTreeLabel = $"Quest steps##sqt_{step.Order}_{src.QuestKey}";
            var target = _data.GetByStableKey(src.QuestKey);
            if (target != null)
                display.OpenQuestLabel =
                    $"Open quest: {target.DisplayName}##goto_{step.Order}_{src.QuestKey}";
        }
        stepDisplay.Sources.Add((src, depth), display);
        if (src.Children != null)
        {
            foreach (var child in display.Children)
                CacheSourceChoice(child, step, stepDisplay, depth + 1, src.Children);
        }
    }

    // ── Helpers ──────────────────────────────────────────────────────

    private bool IsSourceAvailable(ItemSource source) => _state.Gates.IsSourceAvailable(source);

    private bool CanChooseSource(ItemSource source, List<ItemSource>? inputSiblings = null)
    {
        if (source.Type == "treasure_chest")
            return _state.TreasureHunt.State.Active;
        if (ItemSourcePolicy.IsRandomSource(source))
            return false;
        if (
            ItemSourcePolicy.IsStaticCandidate(source)
            && (
                source.Scene != null
                || (source.SourceKey != null && _data.CharacterSpawns.ContainsKey(source.SourceKey))
            )
        )
            return true;
        if (source.Type == "quest_reward" && source.QuestKey != null)
            return _data.GetByStableKey(source.QuestKey)?.HasSteps == true;
        if (
            source.Children != null
            && ItemSourcePolicy.NeedsUsedItem(source, _state.CountItemDelegate, inputSiblings)
        )
        {
            foreach (var child in source.Children)
            {
                if (CanChooseSource(child, source.Children))
                    return true;
            }
        }
        return false;
    }

    private bool HasNavigableSource(ItemSource s, List<ItemSource>? inputSiblings = null)
    {
        if (!IsSourceAvailable(s))
            return false;
        if (s.Type == "treasure_chest")
            return _state.TreasureHunt.State.Active;
        if (
            ItemSourcePolicy.IsRandomSource(s)
            || !ItemSourcePolicy.NeedsUsedItem(s, _state.CountItemDelegate, inputSiblings)
        )
            return false;
        if (ItemSourcePolicy.IsStaticCandidate(s) && s.Scene != null)
            return true;
        if (
            ItemSourcePolicy.IsStaticCandidate(s)
            && s.SourceKey != null
            && _data.CharacterSpawns.TryGetValue(s.SourceKey, out var spawns)
            && spawns.Count > 0
        )
            return true;
        if (s.Children != null)
        {
            foreach (var child in s.Children)
            {
                if (HasNavigableSource(child, s.Children))
                    return true;
            }
        }
        return false;
    }
}
