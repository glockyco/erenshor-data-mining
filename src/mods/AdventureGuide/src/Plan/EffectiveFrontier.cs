namespace AdventureGuide.Plan;

public sealed class EffectiveFrontier
{
    private readonly CompiledGuide.CompiledGuide _guide;
    private readonly QuestPhaseTracker _phases;

    internal QuestPhaseTracker Phases => _phases;

    public EffectiveFrontier(CompiledGuide.CompiledGuide guide, QuestPhaseTracker phases)
    {
        _guide = guide;
        _phases = phases;
    }

    public void Resolve(
        int questIndex,
        List<FrontierEntry> results,
        int requiredFor,
        AdventureGuide.Resolution.IResolutionTracer? tracer = null
    )
    {
        QuestPhase phase = _phases.GetPhase(questIndex);
        if (phase is QuestPhase.Completed or QuestPhase.Infeasible)
        {
            return;
        }

        if (phase == QuestPhase.ReadyToAccept)
        {
            int before = results.Count;
            foreach (int giverId in _guide.GiverIds(questIndex))
            {
                int giverQuestIndex = _guide.FindQuestIndex(giverId);
                if (giverQuestIndex < 0 || _phases.IsCompleted(giverQuestIndex))
                    continue;

                Resolve(giverQuestIndex, results, questIndex, tracer);
            }

            if (results.Count > before)
                return;
        }

        if (phase != QuestPhase.NotReady)
        {
            var entry = new FrontierEntry(questIndex, phase, requiredFor);
            results.Add(entry);
            tracer?.OnFrontierEntry(
                questIndex,
                _guide.GetNode(_guide.QuestNodeId(questIndex)).DbName,
                phase.ToString(),
                requiredFor
            );
            return;
        }

        foreach (int prereqQuestId in _guide.PrereqQuestIds(questIndex))
        {
            int prereqQuestIndex = _guide.FindQuestIndex(prereqQuestId);
            if (prereqQuestIndex < 0 || _phases.IsCompleted(prereqQuestIndex))
            {
                continue;
            }

            Resolve(prereqQuestIndex, results, questIndex, tracer);
        }
    }
}
