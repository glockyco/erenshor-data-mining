using AdventureGuide.Data;
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

    public QuestDetailPanel(GuideData data, QuestStateTracker state)
    {
        _data = data;
        _state = state;
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

        // All acquisition sources (not just dialog)
        if (quest.Acquisition != null)
        {
            foreach (var acq in quest.Acquisition)
            {
                ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
                string? line = acq.Method switch
                {
                    "dialog" => $"Given by: {acq.SourceName}",
                    "item_read" => $"Read: {acq.SourceName}",
                    "zone_entry" => $"Enter: {acq.ZoneName}",
                    "quest_chain" => $"Chain from: {acq.SourceName}",
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
                if (comp.SourceName == null) continue;
                ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
                string turnIn = comp.Method switch
                {
                    "item_turnin" or "dialog" => $"Turn in to: {comp.SourceName}",
                    "zone" => $"Complete at: {comp.ZoneName}",
                    _ => $"Complete: {comp.SourceName}",
                };
                if (comp.ZoneName != null && comp.Method is "item_turnin" or "dialog")
                    turnIn += $" ({comp.ZoneName})";
                ImGui.Text(turnIn);
                ImGui.PopStyleColor();
            }
        }

        if (quest.ZoneContext != null)
        {
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
            ImGui.Text($"Zone: {quest.ZoneContext}");
            ImGui.PopStyleColor();
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

    // ── Objectives ──────────────────────────────────────────────────

    private void DrawObjectives(QuestEntry quest)
    {
        if (quest.Steps == null || quest.Steps.Count == 0)
            return;

        if (!ImGui.CollapsingHeader("Objectives", ImGuiTreeNodeFlags.DefaultOpen))
            return;

        int currentStepIndex = DetermineCurrentStep(quest);

        ImGui.Indent(Theme.IndentWidth);
        for (int i = 0; i < quest.Steps.Count; i++)
        {
            var step = quest.Steps[i];

            if (i < currentStepIndex)
                DrawStep(step, StepState.Completed);
            else if (i == currentStepIndex)
                DrawStep(step, StepState.Current);
            else
                DrawStep(step, StepState.Future);
        }
        ImGui.Unindent(Theme.IndentWidth);
    }

    private enum StepState { Completed, Current, Future }

    private void DrawStep(QuestStep step, StepState state)
    {
        uint color = state switch
        {
            StepState.Completed => Theme.QuestCompleted,
            StepState.Current => Theme.QuestActive,
            _ => Theme.TextSecondary,
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

        ImGui.PushStyleColor(ImGuiCol.Text, color);
        ImGui.Text(text);
        ImGui.PopStyleColor();

        // Drop/vendor sources and tips for collect steps
        DrawStepSources(step);
    }

    /// <summary>
    /// Show obtainability sources (drop, vendor, fishing, mining, etc.) and
    /// tips indented below a step. Only for collect steps.
    /// </summary>
    private void DrawStepSources(QuestStep step)
    {
        if (step.Action != "collect" || step.TargetName == null)
        {
            DrawTips(step);
            return;
        }

        // Find matching required item for full source info
        var quest = _data.GetByDBName(_state.SelectedQuestDBName!);
        var item = quest?.RequiredItems?.Find(ri =>
            string.Equals(ri.ItemName, step.TargetName, StringComparison.OrdinalIgnoreCase));

        if (item == null)
        {
            DrawTips(step);
            return;
        }

        ImGui.Indent(Theme.IndentWidth);
        ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);

        if (item.DropSources != null)
        {
            foreach (var ds in item.DropSources)
            {
                var zone = ds.ZoneName != null ? $" ({ds.ZoneName})" : "";
                ImGui.Text($"Drops from: {ds.CharacterName}{zone}");
            }
        }

        if (item.VendorSources != null)
        {
            foreach (var vs in item.VendorSources)
            {
                var zone = vs.ZoneName != null ? $" ({vs.ZoneName})" : "";
                ImGui.Text($"Sold by: {vs.CharacterName}{zone}");
            }
        }

        if (item.FishingSources is { Count: > 0 })
            foreach (var fs in item.FishingSources)
            {
                var zone = fs.ZoneName != null ? $" ({fs.ZoneName})" : "";
                ImGui.Text($"Fishing{zone}");
            }

        if (item.MiningSources is { Count: > 0 })
            foreach (var ms in item.MiningSources)
            {
                var zone = ms.ZoneName != null ? $" ({ms.ZoneName})" : "";
                ImGui.Text($"Mining{zone}");
            }

        if (item.BagSources is { Count: > 0 })
            foreach (var bs in item.BagSources)
            {
                var zone = bs.ZoneName != null ? $" ({bs.ZoneName})" : "";
                ImGui.Text($"Found in world{zone}");
            }

        if (item.CraftingSources is { Count: > 0 })
            foreach (var cs in item.CraftingSources)
                ImGui.Text($"Crafted from: {cs.RecipeItemName}");

        if (item.QuestRewardSources is { Count: > 0 })
            foreach (var qr in item.QuestRewardSources)
                ImGui.Text($"Quest reward: {qr.QuestName}");

        ImGui.PopStyleColor();
        ImGui.Unindent(Theme.IndentWidth);

        DrawTips(step);
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

    /// <summary>
    /// Walk steps to find the first incomplete one. Conservative approach:
    /// only advance past steps we can verify (collect with item count).
    /// Non-verifiable steps (talk, kill, shout, turn_in) stop the pointer.
    /// </summary>
    private int DetermineCurrentStep(QuestEntry quest)
    {
        if (_state.IsCompleted(quest.DBName))
            return quest.Steps!.Count;

        if (!_state.IsActive(quest.DBName))
            return 0;

        for (int i = 0; i < quest.Steps!.Count; i++)
        {
            var step = quest.Steps[i];
            if (step.Action == "collect" && step.TargetName != null && step.Quantity.HasValue)
            {
                int have = _state.CountItemInInventory(step.TargetName);
                if (have < step.Quantity.Value)
                    return i;
                // have >= need: this collect step is done, continue to next
            }
            else
            {
                // Can't verify: treat as current (conservative)
                return i;
            }
        }

        // All verifiable steps done — point to last step
        return quest.Steps.Count - 1;
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
        foreach (var prereqName in quest.Prerequisites)
        {
            bool completed = IsPrerequisiteCompleted(prereqName);
            var color = completed ? Theme.QuestCompleted : Theme.TextPrimary;
            var prefix = completed ? "\u2713 " : "\u25cb ";

            ImGui.PushStyleColor(ImGuiCol.Text, color);
            if (ImGui.Selectable($"{prefix}{prereqName}##prereq"))
            {
                // Navigate to prerequisite quest
                foreach (var entry in _data.All)
                {
                    if (string.Equals(entry.DisplayName, prereqName, StringComparison.OrdinalIgnoreCase))
                    {
                        _state.SelectedQuestDBName = entry.DBName;
                        break;
                    }
                }
            }
            ImGui.PopStyleColor();
        }
        ImGui.Unindent(Theme.IndentWidth);
    }

    private bool IsPrerequisiteCompleted(string prereqName)
    {
        foreach (var entry in _data.All)
        {
            if (string.Equals(entry.DisplayName, prereqName, StringComparison.OrdinalIgnoreCase))
                return _state.IsCompleted(entry.DBName);
        }
        return false;
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
