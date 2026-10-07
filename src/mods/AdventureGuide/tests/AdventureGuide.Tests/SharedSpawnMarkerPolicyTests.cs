using AdventureGuide.Navigation;

namespace AdventureGuide.Tests;

public sealed class SharedSpawnMarkerPolicyTests
{
    [Theory]
    [InlineData(MarkerType.DeadSpawn)]
    [InlineData(MarkerType.NightSpawn)]
    public void Absence_intents_share_the_live_point_but_not_other_points(MarkerType type)
    {
        Assert.Equal(42, SharedSpawnMarkerPolicy.AbsencePointId(type, 42));
        Assert.NotEqual(
            SharedSpawnMarkerPolicy.AbsencePointId(type, 42),
            SharedSpawnMarkerPolicy.AbsencePointId(type, 43)
        );
        Assert.Null(SharedSpawnMarkerPolicy.AbsencePointId(type, null));
    }

    [Theory]
    [InlineData(MarkerType.Objective)]
    [InlineData(MarkerType.QuestGiver)]
    [InlineData(MarkerType.TurnInReady)]
    [InlineData(MarkerType.ZoneReentry)]
    public void Living_and_direct_placement_intents_keep_character_identity(MarkerType type)
    {
        Assert.Null(SharedSpawnMarkerPolicy.AbsencePointId(type, 42));
    }

    [Fact]
    public void Multiple_quests_for_one_character_do_not_repeat_its_name_in_a_shared_marker()
    {
        var names = new SharedSpawnMarkerNames("character:brittle skeleton", "Brittle Skeleton");
        names.Add("character:sturdy skeleton", "Sturdy Skeleton");
        names.Add("CHARACTER:BRITTLE SKELETON", "Brittle Skeleton");
        names.Add("character:gort", "Gort");
        names.Add("character:sturdy skeleton", "Sturdy Skeleton");
        Assert.Equal("Brittle Skeleton / Sturdy Skeleton / Gort", names.DisplayName);
        Assert.Contains(
            "~1:00",
            RespawnTimerText.WithName(
                names.DisplayName,
                RespawnTimerText.Timer(60, "Respawning...")
            )
        );
    }

    [Fact]
    public void Shared_marker_keeps_the_higher_priority_quest_intent()
    {
        Assert.True(MarkerDecision.ShouldReplace(MarkerType.Objective, MarkerType.TurnInReady));
        Assert.False(MarkerDecision.ShouldReplace(MarkerType.TurnInReady, MarkerType.Objective));
        Assert.False(MarkerDecision.ShouldReplace(MarkerType.Objective, MarkerType.Objective));
    }
}
