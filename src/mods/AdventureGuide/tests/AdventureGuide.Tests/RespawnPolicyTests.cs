using AdventureGuide.Data;
using AdventureGuide.Navigation;

namespace AdventureGuide.Tests;

public sealed class RespawnPolicyTests
{
    private static SpawnPointFacts Facts(
        bool anyAlive = false,
        bool targetAlive = false,
        bool canSpawn = true,
        bool stopQuestCompleted = false,
        bool nightSpawn = false,
        int hour = 12,
        bool hasRespawnHistory = true
    ) =>
        new(
            anyAlive,
            targetAlive,
            canSpawn,
            stopQuestCompleted,
            nightSpawn,
            hour,
            hasRespawnHistory
        );

    [Fact]
    public void Living_npc_outranks_every_spawn_rule()
    {
        // Encounter scripts clear canSpawn while their boss is fighting.
        var fighting = Facts(anyAlive: true, targetAlive: true, canSpawn: false);
        Assert.Equal(SpawnPointPhase.TargetAlive, SpawnPointPolicy.Classify(fighting));

        // A night spawn stays until 07:00 after its window closes at 04:00.
        var lingering = Facts(anyAlive: true, targetAlive: true, nightSpawn: true, hour: 5);
        Assert.Equal(SpawnPointPhase.TargetAlive, SpawnPointPolicy.Classify(lingering));

        var other = Facts(anyAlive: true, targetAlive: false, stopQuestCompleted: true);
        Assert.Equal(SpawnPointPhase.OtherAlive, SpawnPointPolicy.Classify(other));
    }

    [Fact]
    public void Held_or_stopped_points_never_report_a_respawn()
    {
        var held = Facts(canSpawn: false, nightSpawn: true, hour: 12);
        Assert.Equal(SpawnPointPhase.Withheld, SpawnPointPolicy.Classify(held));

        var stopped = Facts(stopQuestCompleted: true, nightSpawn: true, hour: 12);
        Assert.Equal(SpawnPointPhase.Withheld, SpawnPointPolicy.Classify(stopped));
    }

    [Theory]
    [InlineData(22, true)]
    [InlineData(23, false)]
    [InlineData(0, false)]
    [InlineData(3, false)]
    [InlineData(4, true)]
    [InlineData(7, true)]
    public void Night_points_lock_outside_the_game_spawn_window(int hour, bool locked)
    {
        var phase = SpawnPointPolicy.Classify(Facts(nightSpawn: true, hour: hour));
        Assert.Equal(locked ? SpawnPointPhase.NightLocked : SpawnPointPhase.Respawning, phase);
    }

    [Fact]
    public void Empty_point_without_history_is_still_populating()
    {
        var populating = Facts(hasRespawnHistory: false);
        Assert.Equal(SpawnPointPhase.Populating, SpawnPointPolicy.Classify(populating));

        // A night-only quest target still reports its night lock before it
        // ever spawned, so the marker can say when it appears.
        var daytime = Facts(hasRespawnHistory: false, nightSpawn: true, hour: 12);
        Assert.Equal(SpawnPointPhase.NightLocked, SpawnPointPolicy.Classify(daytime));
    }

    [Theory]
    [InlineData(0f, 0)]
    [InlineData(-3f, 0)]
    [InlineData(0.01f, 1)]
    [InlineData(59.01f, 60)]
    [InlineData(60f, 60)]
    public void Respawn_timer_rounds_up_so_it_reaches_zero_only_when_due(float seconds, int shown)
    {
        Assert.Equal(shown, RespawnTimerText.DisplaySeconds(seconds));
    }

    [Theory]
    [InlineData(59, "~0:59")]
    [InlineData(60, "~1:00")]
    [InlineData(3599, "~59:59")]
    [InlineData(3600, "~1:00:00")]
    [InlineData(99999, "~27:46:39")]
    public void Respawn_timer_switches_to_hours_from_one_hour(int seconds, string expected)
    {
        Assert.Equal(expected, RespawnTimerText.Format(seconds));
    }

    [Fact]
    public void Due_respawn_timer_shows_the_due_text()
    {
        Assert.Equal("Respawning...", RespawnTimerText.Timer(0, "Respawning..."));
        Assert.Equal("~0:01", RespawnTimerText.Timer(1, "Respawning..."));
    }

    [Fact]
    public void Unnamed_respawn_marker_shows_only_its_status()
    {
        Assert.Equal("~1:00", RespawnTimerText.WithName(null, "~1:00"));
        Assert.Equal("~1:00", RespawnTimerText.WithName("", "~1:00"));
        Assert.Equal("Goblin Scout\n~1:00", RespawnTimerText.WithName("Goblin Scout", "~1:00"));
    }

    [Theory]
    [InlineData("Chosen Fawn ", "Chosen Fawn")]
    [InlineData("Kio The Darkbringer", "Kio the Darkbringer")]
    public void Target_name_ignores_case_and_surrounding_spaces(string npcName, string expected)
    {
        Assert.True(SpawnPointPolicy.IsTargetName(npcName, expected));
    }

    [Fact]
    public void Target_name_does_not_match_other_npcs()
    {
        // The guide's display name can carry a suffix the game's NPCName lacks;
        // the bridge resolves the NPCName from the spawn table's prefab instead.
        Assert.False(SpawnPointPolicy.IsTargetName("Gloopa", "Gloopa (Quarter)"));
        Assert.False(SpawnPointPolicy.IsTargetName(null, "Gloopa"));
    }

    [Fact]
    public void Object_names_map_to_export_stable_keys()
    {
        // StableKeyGenerator.ForCharacter trims and lowercases object names.
        Assert.Equal(
            "character:braxonian planar guardian fire",
            CharacterStableKey.FromObjectName(" Braxonian Planar Guardian Fire ")
        );
        Assert.Equal(
            "character:arenachest 1",
            CharacterStableKey.Normalize(CharacterStableKey.FromObjectName("ArenaChest 1"))
        );
    }
}
