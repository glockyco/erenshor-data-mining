namespace AdventureGuide.Navigation;

/// <summary>
/// Types of world markers. Priority order (highest first) determines
/// which icon shows when multiple quests target the same NPC.
/// </summary>
public enum MarkerType
{
    TurnInReady, // circle-question gold — can turn in now
    TurnInRepeatReady, // circle-question blue — repeatable, can turn in
    Objective, // circle-dot orange — step objective or drop source
    QuestGiver, // star gold — new quest available
    QuestGiverRepeat, // star blue — repeatable quest available
    TurnInPending, // circle-question grey — quest active, missing items
    DeadSpawn, // clock red — respawn timer
    NightSpawn, // moon pale-blue — night-only, currently daytime
    ZoneReentry, // clock grey — directly placed, re-enter zone to respawn
}
