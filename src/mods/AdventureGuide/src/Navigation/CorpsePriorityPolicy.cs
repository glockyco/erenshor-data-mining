using AdventureGuide.Data;
using AdventureGuide.State;

namespace AdventureGuide.Navigation;

public static class CorpsePriorityPolicy
{
    /// <summary>Reuse the output set; unrelated quest items must not redirect a step.</summary>
    public static void FillItems(
        QuestStep? step,
        QuestEntry? quest,
        Func<string, int> countItem,
        HashSet<string> output
    )
    {
        output.Clear();
        if (
            step == null
            || step.Action == "talk"
            || step.Action == "kill"
            || step.Action == "turn_in"
        )
            return;
        if (step.TargetType == "item" && step.TargetName != null)
        {
            output.Add(step.TargetName);
            if (quest != null)
                ItemSourcePolicy.AddUsedItems(
                    ItemSourcePolicy.SourcesFor(quest, step),
                    countItem,
                    output
                );
        }
    }
}
