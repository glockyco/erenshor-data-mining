using AdventureGuide.Data;
using AdventureGuide.Navigation;

namespace AdventureGuide.Tests;

public sealed class SourceSelectionTests
{
    [Fact]
    public void Initial_character_resolution_keeps_static_fallback_but_live_rescan_skips_absent_npcs()
    {
        Assert.True(SourceSelectionPolicy.ShouldConsiderCharacter(false, false));
        Assert.True(SourceSelectionPolicy.ShouldConsiderCharacter(false, true));
        Assert.True(SourceSelectionPolicy.ShouldConsiderCharacter(true, true));
        Assert.False(SourceSelectionPolicy.ShouldConsiderCharacter(true, false));
    }

    [Fact]
    public void Alive_source_beats_nearer_mined_node() =>
        Assert.True(SourceSelectionPolicy.IsBetter(false, 1000f, 0f, true, 1f, 1f));

    [Fact]
    public void Mined_node_does_not_replace_alive_source() =>
        Assert.False(SourceSelectionPolicy.IsBetter(true, 1f, 1f, false, 1000f, 0f));

    [Fact]
    public void Exhausted_nodes_choose_soonest_respawn_then_distance()
    {
        Assert.True(SourceSelectionPolicy.IsBetter(true, 1000f, 2f, true, 1f, 3f));
        Assert.False(SourceSelectionPolicy.IsBetter(true, 1f, 3f, true, 1000f, 2f));
        Assert.True(SourceSelectionPolicy.IsBetter(true, 1f, 2f, true, 1000f, 2f));
        Assert.True(SourceSelectionPolicy.IsBetter(false, 1f, 0f, false, 1000f, 0f));
    }

    [Fact]
    public void Position_match_tolerates_export_rounding_but_not_another_node()
    {
        Assert.True(SourceSelectionPolicy.MatchesNode(3f * 0.005f * 0.005f));
        Assert.False(SourceSelectionPolicy.MatchesNode(0.25f));
    }

    [Fact]
    public void Cross_zone_sources_prefer_the_fewest_zone_crossings()
    {
        // A vendor two zones away beats a fishing spot four zones away.
        Assert.True(SourceSelectionPolicy.IsBetterCrossZone(true, false, 2, true, false, 4));
        Assert.False(SourceSelectionPolicy.IsBetterCrossZone(true, false, 4, true, false, 2));
        // Equal distance keeps the guide's earlier source.
        Assert.False(SourceSelectionPolicy.IsBetterCrossZone(true, false, 2, true, false, 2));
    }

    [Fact]
    public void Cross_zone_sources_rank_open_routes_before_locked_and_unroutable_ones()
    {
        Assert.True(SourceSelectionPolicy.IsBetterCrossZone(true, false, 6, true, true, 1));
        Assert.True(SourceSelectionPolicy.IsBetterCrossZone(true, true, 6, false, false, 0));
        Assert.False(
            SourceSelectionPolicy.IsBetterCrossZone(false, false, int.MaxValue, true, true, 9)
        );
    }

    [Theory]
    [InlineData("mining:hidden:1:2:3")]
    [InlineData("water:hidden:1:2:3")]
    [InlineData("itembag:hidden:1:2:3")]
    public void Scene_resolution_recognizes_positioned_sources_through_reward_children(string key)
    {
        var step = new QuestStep { TargetType = "item", TargetName = "Coal" };
        var quest = new QuestEntry
        {
            Steps = [step],
            RequiredItems =
            [
                new RequiredItemInfo
                {
                    ItemName = "Coal",
                    Sources =
                    [
                        new ItemSource
                        {
                            Type = "quest_reward",
                            SourceKey = "character:foreign giver",
                            Children = [new ItemSource { SourceKey = key }],
                        },
                    ],
                },
            ],
        };
        var data = TestData.Build();
        Assert.Equal("hidden", StepSceneResolver.ResolveScene(quest, step, data));
        Assert.True(StepSceneResolver.HasSourceInScene(quest, step, data, "Hidden"));
        Assert.False(StepSceneResolver.HasSourceInScene(quest, step, data, "Stowaway"));
    }
}
