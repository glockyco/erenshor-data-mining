using AdventureGuide.Data;
using AdventureGuide.Navigation;
using AdventureGuide.State;

namespace AdventureGuide.Tests;

public sealed class CrossZoneWaypointTests
{
    [Fact]
    public void Whole_hop_access_set_changes_even_when_the_selected_line_stays_open()
    {
        var data = GuideData.FromWrapper(
            new GuideWrapper
            {
                Version = GuideData.SchemaVersion,
                Encounters = TestData.EmptyEncounters(),
                Quests = [],
                Conditions =
                [
                    [
                        [new GateAtom { Kind = GateAtomKind.KeyHeld, Ref = "item:key" }],
                    ],
                ],
                GateItems = new()
                {
                    ["item:key"] = new GateItem { Name = "Key", GameId = "key-id" },
                },
            }
        );
        var facts = new GateTestFacts();
        var gates = new GateConditions(data, facts);
        var selected = new ZoneLineEntry();
        var alternative = new ZoneLineEntry { Condition = 0 };
        ZoneLineAccess[] snapshot = [new(selected, gates), new(alternative, gates)];

        facts.Inventory["item:unrelated"] = 1;
        Assert.True(CrossZoneWaypointPolicy.IsAccessibleSetUnchanged(snapshot, gates));
        facts.Keyring.Add("key-id");
        Assert.True(gates.IsAvailable(selected.Condition));
        Assert.False(CrossZoneWaypointPolicy.IsAccessibleSetUnchanged(snapshot, gates));

        ZoneLineAccess[] unlocked = [new(selected, gates), new(alternative, gates)];
        facts.Keyring.Clear();
        Assert.False(CrossZoneWaypointPolicy.IsAccessibleSetUnchanged(unlocked, gates));
    }

    [Fact]
    public void Permanently_removed_locked_line_invalidates_an_unchanged_accessible_set()
    {
        var data = GuideData.FromWrapper(
            new GuideWrapper
            {
                Version = GuideData.SchemaVersion,
                Encounters = TestData.EmptyEncounters(),
                Quests = [],
                Conditions =
                [
                    [
                        [
                            new GateAtom { Kind = GateAtomKind.QuestNotDone, Ref = "REMOVED" },
                            new GateAtom { Kind = GateAtomKind.ItemHeld, Ref = "item:key" },
                        ],
                    ],
                ],
                GateItems = new() { ["item:key"] = new GateItem { Name = "Key" } },
            }
        );
        var facts = new GateTestFacts();
        var gates = new GateConditions(data, facts);
        var line = new ZoneLineEntry { Condition = 0 };
        ZoneLineAccess[] snapshot = [new(line, gates)];
        Assert.False(snapshot[0].Accessible);

        facts.Quests.Add("REMOVED");
        Assert.False(gates.IsAvailable(line.Condition));
        Assert.False(CrossZoneWaypointPolicy.IsAccessibleSetUnchanged(snapshot, gates));
    }

    [Fact]
    public void Unchanged_state_keeps_cached_waypoint()
    {
        Assert.True(
            CrossZoneWaypointPolicy.ShouldKeepOnStateChange(
                true,
                true,
                true,
                true,
                true,
                true,
                true
            )
        );
    }

    [Theory]
    [InlineData(false, true, true, true, true, true, true)]
    [InlineData(true, false, true, true, true, true, true)]
    [InlineData(false, false, true, true, true, true, true)]
    [InlineData(true, true, false, true, true, true, true)]
    [InlineData(true, true, true, false, true, true, true)]
    [InlineData(true, true, true, true, false, true, true)]
    [InlineData(true, true, true, true, true, false, true)]
    [InlineData(true, true, true, true, true, true, false)]
    public void Missing_cache_or_changed_state_invalidates_waypoint(
        bool hasLine,
        bool hasWaypoint,
        bool targetUnchanged,
        bool nextHopUnchanged,
        bool entryUnchanged,
        bool accessibleSetUnchanged,
        bool routeLockedUnchanged
    )
    {
        Assert.False(
            CrossZoneWaypointPolicy.ShouldKeepOnStateChange(
                hasLine,
                hasWaypoint,
                targetUnchanged,
                nextHopUnchanged,
                entryUnchanged,
                accessibleSetUnchanged,
                routeLockedUnchanged
            )
        );
    }

    [Theory]
    [InlineData(0f, false)]
    [InlineData(99f, false)]
    [InlineData(100f, false)]
    [InlineData(101f, true)]
    public void Cached_waypoint_recalculates_only_beyond_movement_threshold(
        float movedSquared,
        bool expected
    )
    {
        Assert.Equal(
            expected,
            CrossZoneWaypointPolicy.ShouldRecalculate(true, true, movedSquared, 100f)
        );
    }

    [Theory]
    [InlineData(null, "Hidden", true)]
    [InlineData("Hidden", "Hidden", false)]
    [InlineData("Hidden", "hidden", false)]
    [InlineData("Hidden", "Stowaway", true)]
    [InlineData("Stowaway", "Hidden", true)]
    public void Scene_changes_preserve_case_insensitive_comparison(
        string? previous,
        string current,
        bool expected
    )
    {
        Assert.Equal(expected, CrossZoneWaypointPolicy.SceneChanged(previous, current));
    }

    [Fact]
    public void Missing_waypoint_recalculates_with_a_cached_line_and_stationary_player()
    {
        Assert.True(CrossZoneWaypointPolicy.ShouldRecalculate(true, false, 0f, 100f));
        Assert.True(CrossZoneWaypointPolicy.ShouldRecalculate(false, true, 0f, 100f));
        Assert.False(CrossZoneWaypointPolicy.ShouldRecalculate(true, true, 100f, 100f));
        Assert.True(CrossZoneWaypointPolicy.ShouldRecalculate(true, true, 100.1f, 100f));
    }

    [Fact]
    public void Leaving_and_returning_resets_waypoint_even_at_same_position()
    {
        Assert.True(CrossZoneWaypointPolicy.SceneChanged("Hidden", "Stowaway"));
        Assert.True(CrossZoneWaypointPolicy.SceneChanged("Stowaway", "Hidden"));
        Assert.True(CrossZoneWaypointPolicy.ShouldRebuild(false, false, false, false));
        Assert.False(CrossZoneWaypointPolicy.SceneChanged("Hidden", "hidden"));
    }

    [Fact]
    public void Same_line_is_rebuilt_when_lock_changes_but_not_every_frame()
    {
        Assert.True(CrossZoneWaypointPolicy.ShouldRebuild(true, false, true, false));
        Assert.True(CrossZoneWaypointPolicy.ShouldRebuild(true, false, false, true));
        Assert.True(CrossZoneWaypointPolicy.ShouldRebuild(true, true, false, false));
        Assert.False(CrossZoneWaypointPolicy.ShouldRebuild(true, false, true, true));
        Assert.False(CrossZoneWaypointPolicy.ShouldRebuild(true, false, false, false));
    }
}
