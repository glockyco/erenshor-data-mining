using AdventureGuide.Data;

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
        if (step.Action == "loot")
        {
            if (quest?.RequiredItems != null)
                foreach (var item in quest.RequiredItems)
                    if (countItem(item.ItemStableKey) < item.Quantity)
                        output.Add(item.ItemName);
        }
        else if (step.TargetType == "item" && step.TargetName != null)
            output.Add(step.TargetName);
    }
}
