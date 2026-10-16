extern alias vectors;

using AdventureGuide.Data;
using AdventureGuide.UI;
using ImGuiNET;
using Vector2 = vectors::System.Numerics.Vector2;

namespace AdventureGuide.Navigation;

/// <summary>Shared navigation overlay metrics and requirement rendering.</summary>
internal static class NavigationDisplay
{
    internal const float GroundOffset = 0.50f;

    internal static bool IsOrigin(NavigationController nav, QuestEntry quest, QuestStep step) =>
        nav.IsNavigating(quest.RuntimeKey, step.Order)
        && nav.OriginQuest?.RuntimeKey == quest.RuntimeKey
        && nav.OriginStep?.Order == step.Order;

    internal static bool HasGuidance(NavigationController nav) =>
        nav.Requirements is RequirementResolution requirements
        && (
            requirements.Chain.Count > 1
            || requirements.Advisories.Count > 0
            || !string.IsNullOrEmpty(requirements.Message)
        );

    internal static void DrawRequirements(NavigationController nav, string currentScene)
    {
        var requirements = nav.Requirements;
        if (requirements == null)
            return;

        ImGui.PushID("navigation-requirements");
        ImGui.Indent();
        ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
        for (int i = 0; i < requirements.Chain.Count; i++)
        {
            var link = requirements.Chain[i];
            if (link.Atom is { Kind: GateAtomKind.EncounterWon } atom)
            {
                ImGui.PushID(i);
                if (ImGui.SmallButton("[NAV]"))
                    nav.NavigateToRequirementCharacter(atom.Ref, link.Label, currentScene);
                ImGui.PopID();
                ImGui.SameLine();
            }
            ImGui.TextWrapped(link.Label);
            for (int j = 0; j < link.Alternatives.Count; j++)
            {
                ImGui.TextUnformatted("Alternative:");
                ImGui.SameLine();
                ImGui.TextWrapped(link.Alternatives[j]);
            }
        }
        if (!string.IsNullOrEmpty(requirements.Message))
            ImGui.TextWrapped(requirements.Message);
        ImGui.PopStyleColor();
        ImGui.Unindent();
        ImGui.PopID();
    }

    internal static void DrawOverlay(NavigationController nav)
    {
        if (!HasGuidance(nav))
            return;

        var display = Theme.DisplaySize();
        ImGui.SetNextWindowPos(
            new Vector2(display.X * 0.5f, 40f),
            ImGuiCond.Always,
            new Vector2(0.5f, 0f)
        );
        ImGui.SetNextWindowSize(new Vector2(Math.Min(520f, display.X * 0.8f), 0f));
        using var style = Theme.WindowStyleScope(1f);
        try
        {
            if (
                ImGui.Begin(
                    "Navigation requirements###navigation-requirements-overlay",
                    ImGuiWindowFlags.NoTitleBar
                        | ImGuiWindowFlags.NoMove
                        | ImGuiWindowFlags.NoResize
                        | ImGuiWindowFlags.NoSavedSettings
                        | ImGuiWindowFlags.AlwaysAutoResize
                        | ImGuiWindowFlags.NoFocusOnAppearing
                        | ImGuiWindowFlags.NoNav
                )
            )
                DrawRequirements(nav, nav.CurrentScene);
        }
        finally
        {
            ImGui.End();
        }
    }
}
