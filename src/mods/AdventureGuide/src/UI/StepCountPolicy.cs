using AdventureGuide.Data;

namespace AdventureGuide.UI;

internal static class StepCountPolicy
{
    public static bool ShowsInventoryCount(QuestStep step) =>
        (step.Action is "collect" or "obtain") && step.TargetKey != null && step.Quantity.HasValue;
}
