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

    public QuestDetailPanel(GuideData data, QuestStateTracker state, NavigationController nav)
    {
        _data = data;
        _state = state;
        _nav = nav;
    }

    public void Draw()
    {
        if (_state.SelectedQuestDBName == null)
        {
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
            ImGui.TextWrapped("Select a quest from the list.");
            ImGui.PopStyleColor();
            return;
        }

        var quest = _data.GetByDBName(_state.SelectedQuestDBName);
        if (quest == null)
        {
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
            ImGui.TextWrapped("Quest not found in guide data.");
            ImGui.PopStyleColor();
            return;
        }

        DrawHeader(quest);
        DrawObjectives(quest);
        DrawRewards(quest);
        DrawPrerequisites(quest);
        DrawChain(quest);
    }

    // ── Header ──────────────────────────────────────────────────────

    private void DrawHeader(QuestEntry quest)
    {
        // Quest name in header color
        ImGui.PushStyleColor(ImGuiCol.Text, Theme.Header);
        ImGui.TextWrapped(quest.DisplayName);
        ImGui.PopStyleColor();

        // Level + zone on one line (replaces separate "Zone:" line)
        DrawLevelZoneLine(quest);

        // All acquisition sources (not just dialog)
        if (quest.Acquisition != null)
        {
            foreach (var acq in quest.Acquisition)
            {
                ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
                string? line = acq.Method switch
                {
                    "dialog" when acq.SourceName != null => $"Given by: {acq.SourceName}",
                    "item_read" when acq.SourceName != null => $"Read: {acq.SourceName}",
                    "zone_entry" when acq.SourceName != null => $"Enter: {acq.SourceName}",
                    "quest_chain" when acq.SourceName != null => $"Chain from: {acq.SourceName}",
                    _ => acq.SourceName != null ? $"From: {acq.SourceName}" : null,
                };
                if (line != null)
                {
                    if (acq.ZoneName != null && acq.Method == "dialog")
                        line += $" ({acq.ZoneName})";
                    ImGui.Text(line);
                }
                ImGui.PopStyleColor();
            }
        }

        // Turn-in location
        if (quest.Completion != null)
        {
            foreach (var comp in quest.Completion)
            {
                if (comp.SourceName == null && comp.ZoneName == null) continue;
                ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
                string? turnIn = comp.Method switch
                {
                    "item_turnin" or "dialog" when comp.SourceName != null => $"Turn in to: {comp.SourceName}",
                    "zone" when comp.SourceName != null => $"Complete at: {comp.SourceName}",
                    _ when comp.SourceName != null => $"Complete: {comp.SourceName}",
                    _ => null,
                };
                if (turnIn == null) { ImGui.PopStyleColor(); continue; }
                if (comp.ZoneName != null && comp.Method is "item_turnin" or "dialog")
                    turnIn += $" ({comp.ZoneName})";
                ImGui.Text(turnIn);
                ImGui.PopStyleColor();
            }
        }

        // Description
        if (quest.Description != null)
        {
            ImGui.Spacing();
            ImGui.TextWrapped(quest.Description);
        }

        ImGui.Spacing();
        ImGui.Separator();
        ImGui.Spacing();
    }

    private static void DrawLevelZoneLine(QuestEntry quest)
    {
        int? level = quest.LevelEstimate?.Recommended;
        string? zone = quest.ZoneContext;

        if (level == null && zone == null)
            return;

        ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);

        string meta = "";
        if (level != null)
            meta = $"Lv {level}";
        if (level != null && zone != null)
            meta += "  \u00b7  ";
        if (zone != null)
            meta += zone;

        ImGui.Text(meta);

        // Tooltip: show all steps with their levels, mark the driving step
        if (ImGui.IsItemHovered() && quest.Steps is { Count: > 0 })
        {
            ImGui.BeginTooltip();
            ImGui.Text("Quest level: hardest step");
            ImGui.Separator();
            int? questLvl = quest.LevelEstimate?.Recommended;
            foreach (var step in quest.Steps)
            {
                int? stepLvl = step.LevelEstimate?.Recommended;
                string lvlStr = stepLvl.HasValue ? $"Lv {stepLvl,2}" : "    ";
                bool isDriving = questLvl.HasValue && stepLvl == questLvl;
                string marker = isDriving ? " <" : "";
                uint tipColor = isDriving ? Theme.TextPrimary : Theme.TextSecondary;
                ImGui.PushStyleColor(ImGuiCol.Text, tipColor);
                ImGui.Text($"  {step.Order}. {step.Description}  {lvlStr}{marker}");
                ImGui.PopStyleColor();
            }
            ImGui.EndTooltip();
        }

        ImGui.PopStyleColor();
    }

    // ── Objectives ──────────────────────────────────────────────────

    private void DrawObjectives(QuestEntry quest)
    {
        if (quest.Steps == null || quest.Steps.Count == 0)
            return;

        if (!ImGui.CollapsingHeader("Objectives", ImGuiTreeNodeFlags.DefaultOpen))
            return;

        int currentStepIndex = StepProgress.GetCurrentStepIndex(quest, _state);

        ImGui.Indent(Theme.IndentWidth);
        bool prevWasOptional = false;
        for (int i = 0; i < quest.Steps.Count; i++)
        {
            var step = quest.Steps[i];
            bool isOptional = step.Optional;

            // Show "OR" separator between consecutive optional steps
            if (isOptional && prevWasOptional)
            {
                ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
                ImGui.Text("  -- OR --");
                ImGui.PopStyleColor();
            }

            if (i < currentStepIndex)
                DrawStep(step, StepState.Completed, quest);
            else if (i == currentStepIndex)
                DrawStep(step, StepState.Current, quest);
            else
                DrawStep(step, StepState.Future, quest);

            prevWasOptional = isOptional;
        }
        ImGui.Unindent(Theme.IndentWidth);
    }


    private enum StepState { Completed, Current, Future }

    private void DrawStep(QuestStep step, StepState state, QuestEntry quest)
    {
        uint color = state switch
        {
            StepState.Completed => Theme.QuestCompleted,
            StepState.Current => Theme.QuestActive,
            _ => Theme.TextPrimary,
        };
        string prefix = state switch
        {
            StepState.Completed => "\u2713",
            StepState.Current => ">>",
            _ => "\u25cb",
        };

        string text = $"{prefix} {step.Order}. {step.Description}";

        // Collect steps: show have/need count
        if (step.Action == "collect" && step.TargetName != null && step.Quantity.HasValue)
        {
            int have = _state.CountItemInInventory(step.TargetName);
            text += $" ({have}/{step.Quantity})";
        }

        // Step suffix: zone (for non-collect) and level, dot-separated
        if (step.LevelEstimate?.Recommended is int stepLvl)
        {
            // Non-collect steps show zone since there's no source list below
            if (step.Action is not "collect" and not "read"
                && step.LevelEstimate.Factors is { Count: > 0 })
                text += $"  \u00b7  {step.LevelEstimate.Factors[0].Name}";
            text += $"  \u00b7  Lv {stepLvl}";
        }
        else if (step.Action is not "collect" and not "read"
                 && step.LevelEstimate?.Factors is { Count: > 0 })
        {
            // Zone without level
            text += $"  \u00b7  {step.LevelEstimate.Factors[0].Name}";
        }

        // [NAV] button first (fixed width), then step text
        DrawNavButton(step, quest);

        ImGui.PushStyleColor(ImGuiCol.Text, color);
        ImGui.Text(text);
        ImGui.PopStyleColor();

        // Drop/vendor sources and tips for collect steps
        DrawStepSources(step);
    }

    private void DrawNavButton(QuestStep step, QuestEntry quest)
    {
        if (step.TargetKey == null) return;

        bool isActive = _nav.IsNavigating(quest.DBName, step.Order);

        if (isActive)
            ImGui.PushStyleColor(ImGuiCol.Button, Theme.QuestActive);

        if (ImGui.SmallButton($"[NAV]##{step.Order}"))
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
                ImGui.Text("Click to stop navigating");
            else
                ImGui.Text($"Navigate to {step.TargetName ?? step.Description}");
            ImGui.EndTooltip();
        }

        // Keep cursor on same line so the step text follows the button
        ImGui.SameLine();
    }

    /// <summary>
    /// Show obtainability sources sorted by level (easiest first), with levels
    /// and counts inline. Sources arrive pre-sorted and pre-aggregated from
    /// the pipeline. Collapses beyond 4 sources behind a TreeNode.
    /// </summary>
    private void DrawStepSources(QuestStep step)
    {
        if (step.Action is not "collect" and not "read" || step.TargetName == null)
        {
            DrawTips(step);
            return;
        }

        var quest = _data.GetByDBName(_state.SelectedQuestDBName!);
        var item = quest?.RequiredItems?.Find(ri =>
            string.Equals(ri.ItemName, step.TargetName, StringComparison.OrdinalIgnoreCase));

        if (item?.Sources == null || item.Sources.Count == 0)
        {
            DrawTips(step);
            return;
        }

        ImGui.Indent(Theme.IndentWidth);
        ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);

        const int maxVisible = 4;
        int visible = Math.Min(item.Sources.Count, maxVisible);

        for (int i = 0; i < visible; i++)
            DrawSource(item.Sources[i]);

        if (item.Sources.Count > maxVisible)
        {
            int remaining = item.Sources.Count - maxVisible;
            int minLv = item.Sources[maxVisible].Level ?? 0;
            int maxLv = item.Sources[^1].Level ?? minLv;
            string range = minLv == maxLv ? $"Lv {minLv}" : $"Lv {minLv}-{maxLv}";
            if (ImGui.TreeNode($"{remaining} more sources ({range})##{step.Order}"))
            {
                for (int i = maxVisible; i < item.Sources.Count; i++)
                    DrawSource(item.Sources[i]);
                ImGui.TreePop();
            }
        }

        ImGui.PopStyleColor();
        ImGui.Unindent(Theme.IndentWidth);

        DrawTips(step);
    }

    private static void DrawSource(ItemSource src)
    {
        // Consistent format: {what}  \u00b7  {where}  \u00b7  Lv {N}
        string what = src.Type switch
        {
            "drop" => $"Drops from: {src.Name}",
            "vendor" => $"Sold by: {src.Name}",
            "fishing" => "Fishing",
            "mining" => "Mining",
            "pickup" => "Found in world",
            "crafting" => $"Crafted from: {src.Name}",
            "quest_reward" => $"Quest reward: {src.Name}",
            _ => src.Name ?? src.Type,
        };
        string label = what;
        if (src.Zone != null)
            label += $"  \u00b7  {src.Zone}";
        if (src.Level is int lv)
            label += $"  \u00b7  Lv {lv}";
        ImGui.Text(label);
    }

    private void DrawTips(QuestStep step)
    {
        if (step.Tips == null || step.Tips.Count == 0) return;

        ImGui.Indent(Theme.IndentWidth);
        if (ImGui.TreeNode($"Tips##{step.Order}"))
        {
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
            foreach (var tip in step.Tips)
                ImGui.TextWrapped(tip);
            ImGui.PopStyleColor();
            ImGui.TreePop();
        }
        ImGui.Unindent(Theme.IndentWidth);
    }

    // ── Rewards ─────────────────────────────────────────────────────

    private void DrawRewards(QuestEntry quest)
    {
        var r = quest.Rewards;
        if (r == null) return;
        if (r.XP == 0 && r.Gold == 0 && r.ItemName == null && r.FactionEffects == null)
            return;

        // Expanded by default — rewards are primary motivation
        if (!ImGui.CollapsingHeader("Rewards", ImGuiTreeNodeFlags.DefaultOpen))
            return;

        ImGui.Indent(Theme.IndentWidth);

        if (r.XP > 0)
            ImGui.Text($"{r.XP} XP");
        if (r.Gold > 0)
            ImGui.Text($"{r.Gold} Gold");
        if (r.ItemName != null)
            ImGui.Text(r.ItemName);
        if (r.FactionEffects != null)
        {
            foreach (var fe in r.FactionEffects)
            {
                var sign = fe.Amount >= 0 ? "+" : "";
                ImGui.Text($"{fe.FactionName}: {sign}{fe.Amount}");
            }
        }
        if (r.AlsoCompletes != null && r.AlsoCompletes.Count > 0)
        {
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
            ImGui.Text($"Also completes: {string.Join(", ", r.AlsoCompletes)}");
            ImGui.PopStyleColor();
        }

        ImGui.Unindent(Theme.IndentWidth);
    }

    // ── Prerequisites ───────────────────────────────────────────────

    private void DrawPrerequisites(QuestEntry quest)
    {
        if (quest.Prerequisites == null || quest.Prerequisites.Count == 0)
            return;

        // Auto-expand when any prerequisite is incomplete
        bool anyIncomplete = false;
        foreach (var p in quest.Prerequisites)
        {
            if (!IsPrerequisiteCompleted(p))
            {
                anyIncomplete = true;
                break;
            }
        }

        var flags = anyIncomplete ? ImGuiTreeNodeFlags.DefaultOpen : ImGuiTreeNodeFlags.None;
        if (!ImGui.CollapsingHeader("Prerequisites", flags))
            return;

        ImGui.Indent(Theme.IndentWidth);
        foreach (var prereq in quest.Prerequisites)
        {
            bool completed = IsPrerequisiteCompleted(prereq);
            var color = completed ? Theme.QuestCompleted : Theme.TextPrimary;
            var prefix = completed ? "\u2713 " : "\u25cb ";
            string label = prereq.Item != null
                ? $"{prereq.QuestName} ({prereq.Item})"
                : prereq.QuestName;

            ImGui.PushStyleColor(ImGuiCol.Text, color);
            if (ImGui.Selectable($"{prefix}{label}##prereq_{prereq.QuestKey}"))
            {
                // Navigate to prerequisite quest via stable key (O(1) lookup)
                var target = _data.GetByStableKey(prereq.QuestKey);
                if (target != null)
                    _state.SelectedQuestDBName = target.DBName;
            }
            ImGui.PopStyleColor();
        }
        ImGui.Unindent(Theme.IndentWidth);
    }

    private bool IsPrerequisiteCompleted(Prerequisite prereq)
    {
        var quest = _data.GetByStableKey(prereq.QuestKey);
        return quest != null && _state.IsCompleted(quest.DBName);
    }

    // ── Chain ────────────────────────────────────────────────────────

    private void DrawChain(QuestEntry quest)
    {
        if (quest.Chain == null || quest.Chain.Count == 0)
            return;

        if (!ImGui.CollapsingHeader("Quest Chain", ImGuiTreeNodeFlags.None))
            return;

        ImGui.Indent(Theme.IndentWidth);
        foreach (var link in quest.Chain)
        {
            string arrow = link.Relationship switch
            {
                "previous" => "<< ",
                "next" => ">> ",
                "completed_by" => "<= ",
                _ => "   "
            };

            bool isCompleted = false;
            var linkedQuest = _data.GetByStableKey(link.QuestStableKey);
            if (linkedQuest != null)
                isCompleted = _state.IsCompleted(linkedQuest.DBName);

            var color = isCompleted ? Theme.QuestCompleted : Theme.TextPrimary;

            ImGui.PushStyleColor(ImGuiCol.Text, color);
            if (ImGui.Selectable($"{arrow}{link.QuestName}##{link.QuestStableKey}"))
            {
                if (linkedQuest != null)
                    _state.SelectedQuestDBName = linkedQuest.DBName;
            }
            ImGui.PopStyleColor();
        }
        ImGui.Unindent(Theme.IndentWidth);
    }
}
