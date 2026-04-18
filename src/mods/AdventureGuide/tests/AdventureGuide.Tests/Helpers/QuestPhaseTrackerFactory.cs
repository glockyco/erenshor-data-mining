using AdventureGuide.Plan;
using AdventureGuide.State;
using CompiledGuideModel = AdventureGuide.CompiledGuide.CompiledGuide;

namespace AdventureGuide.Tests.Helpers;

internal static class QuestPhaseTrackerFactory
{
    public static QuestPhaseTracker Build(
        CompiledGuideModel guide,
        IReadOnlyCollection<string> completedQuestDbNames,
        IReadOnlyCollection<string> activeQuestDbNames,
        IReadOnlyDictionary<string, int> inventory,
        IReadOnlyCollection<string> keyringItems,
        GuideDependencyEngine? dependencies = null,
        string currentZone = ""
    )
    {
        return BuildWithState(
            guide,
            completedQuestDbNames,
            activeQuestDbNames,
            inventory,
            keyringItems,
            dependencies,
            currentZone
        ).Phases;
    }

    public static (QuestStateTracker State, QuestPhaseTracker Phases, GuideDependencyEngine Dependencies) BuildWithState(
        CompiledGuideModel guide,
        IReadOnlyCollection<string> completedQuestDbNames,
        IReadOnlyCollection<string> activeQuestDbNames,
        IReadOnlyDictionary<string, int> inventory,
        IReadOnlyCollection<string> keyringItems,
        GuideDependencyEngine? dependencies = null,
        string currentZone = ""
    )
    {
        var engine = dependencies ?? new GuideDependencyEngine();
        var state = new QuestStateTracker(guide, engine);
        state.LoadState(
            currentZone,
            activeQuestDbNames,
            completedQuestDbNames,
            inventory,
            keyringItems
        );
        var phases = new QuestPhaseTracker(guide, state);
        return (state, phases, engine);
    }
}
