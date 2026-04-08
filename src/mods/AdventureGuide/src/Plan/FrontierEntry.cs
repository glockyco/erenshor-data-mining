namespace AdventureGuide.Plan;

public enum QuestPhase : byte
{
    Infeasible,
    NotReady,
    ReadyToAccept,
    Accepted,
    Completed,
}

public readonly struct FrontierEntry
{
    public FrontierEntry(int questIndex, QuestPhase phase, int requiredForQuestIndex)
    {
        QuestIndex = questIndex;
        Phase = phase;
        RequiredForQuestIndex = requiredForQuestIndex;
    }

    public int QuestIndex { get; }
    public QuestPhase Phase { get; }
    public int RequiredForQuestIndex { get; }
}
