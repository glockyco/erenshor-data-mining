
namespace AdventureGuide.Plan;

public sealed class EffectiveFrontier
{
    private readonly CompiledGuide.CompiledGuide _guide;
    private readonly QuestPhaseTracker _phases;

    public EffectiveFrontier(CompiledGuide.CompiledGuide guide, QuestPhaseTracker phases)
    {
        _guide = guide;
        _phases = phases;
    }

    public void Resolve(int questIndex, List<FrontierEntry> results, int requiredFor)
    {
        QuestPhase phase = _phases.GetPhase(questIndex);
        if (phase is QuestPhase.Completed or QuestPhase.Infeasible)
        {
            return;
        }

        if (phase != QuestPhase.NotReady)
        {
            results.Add(new FrontierEntry(questIndex, phase, requiredFor));
            return;
        }

        foreach (int prereqQuestId in _guide.PrereqQuestIds(questIndex))
        {
            int prereqQuestIndex = _guide.FindQuestIndex(prereqQuestId);
            if (prereqQuestIndex < 0 || _phases.IsCompleted(prereqQuestIndex))
            {
                continue;
            }

            Resolve(prereqQuestIndex, results, questIndex);
        }
    }
}
