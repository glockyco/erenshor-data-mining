using AdventureGuide.Data;
using AdventureGuide.UI;
using ImGuiNET;

namespace AdventureGuide.Navigation;

/// <summary>Navigation guidance shared by the quest panel and tracker.</summary>
internal static class NavigationDisplay
{
    internal const float GroundOffset = 0.50f;

    internal static bool IsOrigin(NavigationController nav, QuestEntry quest, QuestStep step) =>
        nav.IsNavigating(quest.RuntimeKey, step.Order)
        && nav.OriginQuest?.RuntimeKey == quest.RuntimeKey
        && nav.OriginStep?.Order == step.Order;

    internal static bool HasGuidance(NavigationController nav) =>
        nav.SelectedItemSource != null
        || (
            nav.Requirements is RequirementResolution requirements
            && (
                requirements.Chain.Count > 1
                || requirements.Advisories.Count > 0
                || !string.IsNullOrEmpty(requirements.Message)
            )
        );

    internal static void DrawRequirements(NavigationController nav, string currentScene)
    {
        var requirements = nav.Requirements;
        if (requirements == null && nav.SelectedItemSource == null)
            return;

        ImGui.PushID("navigation-requirements");
        ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
        if (nav.ImmediateRequirement is string blocker)
            Theme.TextWrapped(blocker);
        ImGui.PopStyleColor();
        if (nav.NextActionLabel is string nextAction)
            Theme.TextWrapped(nextAction);
        ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
        if (nav.SelectedSourceLocation is string location)
            Theme.TextWrapped(location);
        if (nav.SelectedSourceOdds is string odds)
            Theme.TextWrapped(odds);
        if (nav.SelectedItemSource is { Type: "drop", Instruction: not null } preparedSource)
            Theme.TextWrapped(preparedSource.Instruction);
        if (nav.SelectedSourceTiming is string timing)
            Theme.TextWrapped(timing);
        if (!string.IsNullOrEmpty(requirements?.Message))
            Theme.TextWrapped(requirements!.Message!);
        ImGui.PopStyleColor();

        for (int i = 0; requirements != null && i < requirements.Chain.Count; i++)
        {
            var link = requirements.Chain[i];
            if (link.Atom is not { Kind: GateAtomKind.EncounterWon } atom)
                continue;
            ImGui.PushID(i);
            if (ImGui.SmallButton("[NAV]"))
                nav.NavigateToRequirementCharacter(atom.Ref, link.Label, currentScene);
            ImGui.PopID();
            ImGui.SameLine();
            Theme.TextWrapped(link.Label);
        }
        ImGui.PopID();
    }
}
