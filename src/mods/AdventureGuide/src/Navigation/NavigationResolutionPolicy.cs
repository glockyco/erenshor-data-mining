using AdventureGuide.Data;
using AdventureGuide.State;

namespace AdventureGuide.Navigation;

public static class NavigationResolutionPolicy
{
    /// <summary>Returns zero when the selection has no remaining navigable step.</summary>
    public static int SelectOriginStepOrder(
        IReadOnlyList<QuestStep> steps,
        int selectedOrder,
        int currentStepIndex
    )
    {
        int selectedIndex = -1;
        for (int i = 0; i < steps.Count; i++)
        {
            if (steps[i].Order == selectedOrder)
            {
                selectedIndex = i;
                break;
            }
        }

        if (selectedIndex < 0)
            return 0;

        for (int i = Math.Max(selectedIndex, currentStepIndex); i < steps.Count; i++)
        {
            if (steps[i].TargetKey != null || steps[i].Location != null)
                return steps[i].Order;
        }

        return 0;
    }

    public static IReadOnlyList<RequirementLink> CaptureAdvisories(RequirementResolution? result)
    {
        if (result == null || result.Advisories.Count == 0)
            return Array.Empty<RequirementLink>();
        var context = new List<RequirementLink>(result.Advisories.Count);
        foreach (var link in result.Chain)
            if (link.Atom is { Kind: GateAtomKind.EncounterWon })
                context.Add(link);
        return context;
    }

    public static RequirementResolution PreserveAdvisories(
        RequirementResolution result,
        IReadOnlyList<RequirementLink> context
    )
    {
        List<RequirementLink>? chain = null;
        List<GateAtom>? advisories = null;
        foreach (var link in context)
        {
            if (link.Atom is not { Kind: GateAtomKind.EncounterWon } atom)
                continue;
            bool present = false;
            var existing = advisories ?? result.Advisories;
            for (int i = 0; i < existing.Count; i++)
                if (ReferenceEquals(existing[i], atom))
                {
                    present = true;
                    break;
                }
            if (present)
                continue;
            chain ??= new List<RequirementLink>(result.Chain);
            advisories ??= new List<GateAtom>(result.Advisories);
            chain.Add(link);
            advisories.Add(atom);
        }
        return chain == null
            ? result
            : new RequirementResolution(
                result.Quest,
                result.Step,
                result.CanNavigate,
                result.Message,
                chain,
                advisories!,
                result.SelectedScene,
                result.SelectedSpawn,
                result.EntryLine,
                result.AvailableSpawns
            )
            {
                Activation = result.Activation,
            };
    }

    public static bool ShouldResolveRequirements(int stateVersion, int resolutionVersion) =>
        stateVersion != resolutionVersion;

    /// <summary>Keeps an existing endpoint only when re-resolution preserves its effective plan.</summary>
    public static bool CanReuseEndpoint(
        RequirementResolution? previous,
        RequirementResolution current,
        bool hasTarget,
        bool containsItemUse
    ) =>
        hasTarget
        // Item-use children depend on inventory even when their source references are unchanged.
        && !containsItemUse
        && previous != null
        && previous.Activation == null
        && current.Activation == null
        && previous.CanNavigate
        && current.CanNavigate
        && SameStep(previous.Quest, previous.Step, current.Quest, current.Step)
        && ReferenceEquals(previous.Step.Location, current.Step.Location)
        && string.Equals(
            previous.SelectedScene,
            current.SelectedScene,
            StringComparison.OrdinalIgnoreCase
        )
        && ReferenceEquals(previous.SelectedSpawn, current.SelectedSpawn)
        && ReferenceEquals(previous.EntryLine, current.EntryLine)
        && SameReferences(previous.AvailableSpawns, current.AvailableSpawns)
        && SameReferences(
            ItemSourcePolicy.SourcesFor(previous.Quest, previous.Step),
            ItemSourcePolicy.SourcesFor(current.Quest, current.Step)
        );

    private static bool SameReferences<T>(IReadOnlyList<T>? previous, IReadOnlyList<T>? current)
        where T : class
    {
        if (ReferenceEquals(previous, current))
            return true;
        if (previous == null || current == null || previous.Count != current.Count)
            return false;
        for (int i = 0; i < previous.Count; i++)
        {
            if (!ReferenceEquals(previous[i], current[i]))
                return false;
        }
        return true;
    }

    public static bool SameStep(
        QuestEntry questA,
        QuestStep stepA,
        QuestEntry questB,
        QuestStep stepB
    ) =>
        string.Equals(questA.DBName, questB.DBName, StringComparison.OrdinalIgnoreCase)
        && stepA.Order == stepB.Order
        && string.Equals(stepA.TargetKey, stepB.TargetKey, StringComparison.OrdinalIgnoreCase);

    public static bool CanUseZoneLine(ZoneLineEntry line, GateConditions gates) =>
        gates.CanBecomeAvailable(line.Condition);

    public static bool CanResolveQuest(bool isCompleted) => !isCompleted;
}
