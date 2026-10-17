using AdventureGuide.Data;
using AdventureGuide.Navigation;
using AdventureGuide.State;

namespace AdventureGuide.Tests;

public sealed class PlacementRouteTests
{
    private static ZoneLineEntry Line(string scene, string destination, int? condition = null) =>
        new()
        {
            Scene = scene,
            DestinationZoneKey = "zone:" + destination.ToLowerInvariant(),
            Condition = condition,
        };

    private static GuideWrapper Wrapper(
        List<ZoneLineEntry> lines,
        SpawnPoint spawn,
        List<List<List<GateAtom>>>? conditions = null
    ) =>
        new()
        {
            Version = 8,
            Encounters = TestData.EmptyEncounters(),
            Quests = [],
            Conditions = conditions ?? [],
            CharacterSpawns = new() { ["target"] = [spawn] },
            ZoneLines = lines,
            ZoneLookup = new()
            {
                ["A"] = new() { StableKey = "zone:a", DisplayName = "A" },
                ["B"] = new() { StableKey = "zone:b", DisplayName = "B" },
                ["C"] = new() { StableKey = "zone:c", DisplayName = "C" },
                ["T"] = new() { StableKey = "zone:t", DisplayName = "T" },
            },
        };

    private static (GuideData data, GateConditions gates, ZoneGraph graph) Build(
        GuideWrapper wrapper,
        GateTestFacts? facts = null
    )
    {
        var data = GuideData.FromWrapper(wrapper);
        var gates = new GateConditions(data, facts ?? new());
        return (data, gates, new(data, gates));
    }

    private static QuestStep Step(string type = "character") =>
        new()
        {
            Order = 1,
            Action = "obtain",
            Description = "Reach target",
            TargetName = "Target",
            TargetType = type,
            TargetKey = "target",
        };

    private static QuestEntry Quest(QuestStep step) =>
        new()
        {
            StableKey = "quest:test",
            DBName = "Test",
            DisplayName = "Test",
            Steps = [step],
        };

    [Fact]
    public void Entry_cost_uses_approach_scene_and_not_the_general_target_route()
    {
        var spawn = new SpawnPoint { Scene = "T", Entries = [0, 1] };
        var (data, gates, graph) = Build(
            Wrapper(
                [Line("C", "T"), Line("B", "T"), Line("A", "B"), Line("B", "C"), Line("A", "T")],
                spawn
            )
        );
        var placement = graph.GetPlacementRoute(spawn, "A");
        Assert.NotNull(placement);
        Assert.Same(data.ZoneLines[1], placement.Value.EntryLine);
        Assert.Equal(new[] { "A", "B" }, placement.Value.Route!.Path);

        var step = Step();
        var result = new RequirementResolver(data, gates, graph, quest => quest.Steps![0]).Resolve(
            Quest(step),
            step,
            "A"
        );
        Assert.True(result.CanNavigate, result.Message);
        Assert.Same(spawn, result.SelectedSpawn);
        Assert.Same(data.ZoneLines[1], result.EntryLine);
    }

    [Fact]
    public void Equal_cost_entries_preserve_placement_order_and_same_entry_scene_costs_zero()
    {
        var spawn = new SpawnPoint { Scene = "T", Entries = [1, 0] };
        var (data, _, graph) = Build(
            Wrapper([Line("B", "T"), Line("C", "T"), Line("A", "B"), Line("A", "C")], spawn)
        );
        Assert.Same(data.ZoneLines[1], graph.GetPlacementRoute(spawn, "A")!.Value.EntryLine);
        var local = graph.GetPlacementRoute(spawn, "B");
        Assert.NotNull(local);
        Assert.Null(local.Value.Route);
        Assert.Same(data.ZoneLines[0], local.Value.EntryLine);
        var arrived = graph.GetPlacementRoute(spawn, "T");
        Assert.NotNull(arrived);
        Assert.Null(arrived.Value.Route);
        Assert.Null(arrived.Value.EntryLine);
    }

    [Fact]
    public void Missing_entries_use_normal_route_and_unreachable_placements_return_null()
    {
        var spawn = new SpawnPoint { Scene = "T" };
        var (_, _, graph) = Build(Wrapper([Line("A", "T")], spawn));
        var placement = graph.GetPlacementRoute(spawn, "A");
        Assert.NotNull(placement);
        Assert.Equal(new[] { "A", "T" }, placement.Value.Route!.Path);
        Assert.Null(placement.Value.EntryLine);
        Assert.Null(graph.GetPlacementRoute(spawn, "B"));
    }

    [Fact]
    public void Permanently_closed_entry_is_skipped_but_a_missing_key_remains_a_possible_entry()
    {
        var spawn = new SpawnPoint { Scene = "T", Entries = [0, 1] };
        var facts = new GateTestFacts();
        facts.Quests.Add("Closed");
        var wrapper = Wrapper(
            [Line("A", "T", 0), Line("B", "T", 1), Line("A", "B")],
            spawn,
            [
                [
                    [new() { Kind = GateAtomKind.QuestNotDone, Ref = "Closed" }],
                ],
                [
                    [new() { Kind = GateAtomKind.KeyHeld, Ref = "item:key" }],
                ],
            ]
        );
        wrapper.GateItems = new()
        {
            ["item:key"] = new() { Name = "Key", GameId = "key" },
        };
        var (data, _, graph) = Build(wrapper, facts);
        Assert.Same(data.ZoneLines[1], graph.GetPlacementRoute(spawn, "A")!.Value.EntryLine);
        Assert.Equal(new[] { "A", "B", "T" }, graph.FindRoute("A", "T")!.Path);
    }

    [Fact]
    public void All_permanently_closed_entries_are_unreachable_and_not_in_fallback_graph()
    {
        var spawn = new SpawnPoint { Scene = "T", Entries = [0] };
        var (_, _, graph) = Build(
            Wrapper(
                [Line("A", "T", 0)],
                spawn,
                [
                    [],
                ]
            )
        );
        Assert.Null(graph.GetPlacementRoute(spawn, "A"));
        Assert.Null(graph.FindRoute("A", "T"));
    }

    [Fact]
    public void Entry_condition_is_checked_instead_of_incompatible_pinned_target_line()
    {
        var spawn = new SpawnPoint { Scene = "T", Entries = [0] };
        var wrapper = Wrapper(
            [Line("B", "T"), Line("A", "B"), Line("A", "T", 0)],
            spawn,
            [
                [
                    [new() { Kind = GateAtomKind.KeyHeld, Ref = "item:unobtainable" }],
                ],
            ]
        );
        wrapper.GateItems = new()
        {
            ["item:unobtainable"] = new() { Name = "Unobtainable", GameId = "key" },
        };
        var (data, gates, graph) = Build(wrapper);
        var step = Step();
        var result = new RequirementResolver(data, gates, graph, quest => quest.Steps![0]).Resolve(
            Quest(step),
            step,
            "A",
            data.ZoneLines[2]
        );
        Assert.True(result.CanNavigate, result.Message);
        Assert.Same(data.ZoneLines[0], result.EntryLine);
        Assert.Empty(result.Chain);
    }

    [Fact]
    public void Unusable_item_placement_is_skipped_and_the_usable_source_is_constrained()
    {
        var blocked = new SpawnPoint { Scene = "T", Entries = [0] };
        var wrapper = Wrapper(
            [Line("B", "T", 0)],
            blocked,
            [
                [],
            ]
        );
        var available = new SpawnPoint { Scene = "A" };
        wrapper.CharacterSpawns!["available"] = [available];
        var (data, gates, graph) = Build(wrapper);
        var step = Step("item");
        var source = new ItemSource
        {
            Type = "drop",
            SourceKey = "available",
            Name = "Available",
        };
        step.Sources = [new() { Type = "drop", SourceKey = "target" }, source];
        var result = new RequirementResolver(data, gates, graph, quest => quest.Steps![0]).Resolve(
            Quest(step),
            step,
            "A"
        );
        Assert.True(result.CanNavigate, result.Message);
        Assert.Same(source, Assert.Single(result.Step.Sources!));
        Assert.Same(available, result.SelectedSpawn);
    }

    [Fact]
    public void Available_entry_restricted_item_keeps_its_exact_placement()
    {
        var spawn = new SpawnPoint { Scene = "T", Entries = [0] };
        var (data, gates, graph) = Build(Wrapper([Line("A", "T")], spawn));
        var step = Step("item");
        step.Sources = [new() { Type = "drop", SourceKey = "target" }];
        var result = new RequirementResolver(data, gates, graph, quest => quest.Steps![0]).Resolve(
            Quest(step),
            step,
            "A"
        );
        Assert.True(result.CanNavigate, result.Message);
        Assert.Same(spawn, result.SelectedSpawn);
        Assert.Same(data.ZoneLines[0], result.EntryLine);
    }

    [Fact]
    public void Requirement_cost_ranks_the_entry_approach_not_a_shortcut_to_target_scene()
    {
        var far = new SpawnPoint { Scene = "T", Entries = [0] };
        var wrapper = Wrapper(
            [Line("C", "T"), Line("A", "B"), Line("B", "C"), Line("A", "T")],
            far,
            [
                [
                    [new() { Kind = GateAtomKind.QuestDone, Ref = "Far" }],
                    [new() { Kind = GateAtomKind.QuestDone, Ref = "Near" }],
                ],
            ]
        );
        var target = new SpawnPoint { Scene = "A", Condition = 0 };
        wrapper.CharacterSpawns!["original"] = [target];
        wrapper.CharacterSpawns["near"] = [new() { Scene = "B" }];
        var farQuest = Quest(Step());
        farQuest.StableKey = "quest:far";
        farQuest.DBName = "Far";
        var nearStep = Step();
        nearStep.TargetKey = "near";
        var nearQuest = Quest(nearStep);
        nearQuest.StableKey = "quest:near";
        nearQuest.DBName = "Near";
        wrapper.Quests = [farQuest, nearQuest];
        var (data, gates, graph) = Build(wrapper);
        var step = Step();
        step.TargetKey = "original";
        var result = new RequirementResolver(data, gates, graph, quest => quest.Steps![0]).Resolve(
            Quest(step),
            step,
            "A"
        );
        Assert.True(result.CanNavigate, result.Message);
        Assert.Same(nearStep, result.Step);
    }

    [Fact]
    public void Multiple_available_sources_keep_entry_restricted_placements_without_a_global_winner()
    {
        var restricted = new SpawnPoint { Scene = "T", Entries = [0] };
        var local = new SpawnPoint { Scene = "A", X = 10 };
        var blocked = new SpawnPoint { Scene = "A", Condition = 0 };
        var wrapper = Wrapper(
            [Line("A", "T")],
            restricted,
            [
                [],
            ]
        );
        wrapper.CharacterSpawns!["local"] = [local];
        wrapper.CharacterSpawns["blocked"] = [blocked];
        var (data, gates, graph) = Build(wrapper);
        var restrictedSource = new ItemSource { Type = "drop", SourceKey = "target" };
        var localSource = new ItemSource { Type = "drop", SourceKey = "local" };
        var step = Step("item");
        step.Sources =
        [
            restrictedSource,
            new ItemSource { Type = "drop", SourceKey = "blocked" },
            localSource,
        ];

        var result = new RequirementResolver(data, gates, graph, quest => quest.Steps![0]).Resolve(
            Quest(step),
            step,
            "A"
        );

        Assert.True(result.CanNavigate, result.Message);
        Assert.Equal(new[] { restrictedSource, localSource }, result.Step.Sources);
        Assert.Equal(new[] { restricted, local }, result.AvailableSpawns);
        Assert.Null(result.SelectedScene);
        Assert.Null(result.SelectedSpawn);
        Assert.Null(result.EntryLine);
        Assert.Same(data.ZoneLines[0], graph.GetPlacementRoute(restricted, "A")!.Value.EntryLine);
        Assert.Empty(result.Chain);
    }

    [Theory]
    [InlineData(0)]
    [InlineData(1)]
    [InlineData(2)]
    [InlineData(3)]
    [InlineData(4)]
    [InlineData(5)]
    public void Route_lookup_matches_existing_BFS_for_accessible_locked_same_zone_and_unreachable_routes(
        int scenario
    )
    {
        List<ZoneLineEntry> lines = scenario switch
        {
            0 =>
            [
                Line("A", "T", 0),
                Line("A", "B"),
                Line("B", "C"),
                Line("C", "T"),
                Line("T", "A"),
            ],
            1 => [Line("A", "B", 0), Line("B", "T")],
            2 => [Line("A", "B"), Line("B", "T", 0)],
            3 => [Line("A", "B"), Line("C", "T")],
            4 => [Line("A", "T", 1)],
            _ => [Line("A", "B", 0), Line("A", "B"), Line("B", "T")],
        };
        var wrapper = Wrapper(
            lines,
            new SpawnPoint { Scene = "T" },
            [
                [
                    [new GateAtom { Kind = GateAtomKind.KeyHeld, Ref = "item:key" }],
                ],
                [],
            ]
        );
        wrapper.GateItems = new()
        {
            ["item:key"] = new GateItem { Name = "Key", GameId = "key" },
        };
        var (_, _, graph) = Build(wrapper);
        string[] scenes = ["A", "B", "C", "T", "Unknown"];
        foreach (string origin in scenes)
        {
            var lookup = graph.BuildRouteLookup(origin);
            foreach (string destination in scenes)
            {
                var expected = graph.FindRoute(origin, destination);
                var actual = lookup.FindRoute(destination);
                if (expected == null)
                    Assert.Null(actual);
                else
                {
                    Assert.NotNull(actual);
                    Assert.Equal(expected.Path, actual.Path);
                    Assert.Equal(expected.NextHopZoneKey, actual.NextHopZoneKey);
                    Assert.Equal(expected.IsLocked, actual.IsLocked);
                    Assert.Same(actual, lookup.FindRoute(destination));
                }
                int expectedHops =
                    origin == destination ? 0 : expected?.Path.Count - 1 ?? int.MaxValue;
                Assert.Equal(expectedHops, lookup.HopCount(destination));
            }
        }

        var target = graph.BuildRouteLookup("A").FindRoute("t");
        if (scenario is 3 or 4)
            Assert.Null(target);
        else
        {
            Assert.NotNull(target);
            Assert.Equal(
                scenario == 0 ? new[] { "A", "B", "C", "T" } : new[] { "A", "B", "T" },
                target.Path
            );
            Assert.Equal(scenario == 1, target.IsLocked);
        }
    }

    [Fact]
    public void Route_lookup_entry_selection_matches_existing_placement_routing()
    {
        var spawn = new SpawnPoint { Scene = "T", Entries = [0, 1, 2] };
        var wrapper = Wrapper(
            [Line("C", "T"), Line("B", "T", 0), Line("A", "T", 1), Line("A", "B"), Line("B", "C")],
            spawn,
            [
                [
                    [new GateAtom { Kind = GateAtomKind.KeyHeld, Ref = "item:key" }],
                ],
                [],
            ]
        );
        wrapper.GateItems = new()
        {
            ["item:key"] = new GateItem { Name = "Key", GameId = "key" },
        };
        var (_, _, graph) = Build(wrapper);
        foreach (string scene in new[] { "A", "B", "C", "T", "Unknown" })
        {
            var lookup = graph.BuildRouteLookup(scene);
            foreach (
                var placement in new[]
                {
                    spawn,
                    new SpawnPoint { Scene = "T" },
                    new SpawnPoint { Scene = "T", Entries = [] },
                }
            )
            {
                var expected = graph.GetPlacementRoute(placement, scene);
                var actual = lookup.GetPlacementRoute(placement);
                Assert.Equal(expected.HasValue, actual.HasValue);
                if (!expected.HasValue)
                    continue;
                Assert.Same(expected.Value.EntryLine, actual!.Value.EntryLine);
                Assert.Equal(expected.Value.Route?.Path, actual.Value.Route?.Path);
                Assert.Equal(
                    expected.Value.Route?.NextHopZoneKey,
                    actual.Value.Route?.NextHopZoneKey
                );
                Assert.Equal(expected.Value.Route?.IsLocked, actual.Value.Route?.IsLocked);
            }
        }
    }

    [Fact]
    public void Empty_entry_list_is_valid_but_unreachable_until_inside_the_target_scene()
    {
        var spawn = new SpawnPoint { Scene = "T", Entries = [] };
        var (_, _, graph) = Build(Wrapper([Line("A", "T")], spawn));
        Assert.Null(graph.GetPlacementRoute(spawn, "A"));
        Assert.NotNull(graph.GetPlacementRoute(spawn, "T"));
    }

    [Theory]
    [InlineData(-1)]
    [InlineData(1)]
    public void Validation_rejects_entry_indices_outside_zone_lines(int index)
    {
        var wrapper = Wrapper([Line("A", "T")], new SpawnPoint { Scene = "T", Entries = [index] });
        Assert.Throws<InvalidDataException>(() => GuideData.ValidateWrapper(wrapper));
    }

    [Fact]
    public void Validation_rejects_entries_without_a_zone_line_list()
    {
        var wrapper = Wrapper([], new SpawnPoint { Scene = "T", Entries = [0] });
        wrapper.ZoneLines = null;
        Assert.Throws<InvalidDataException>(() => GuideData.ValidateWrapper(wrapper));
    }

    [Fact]
    public void Validation_rejects_entries_into_a_different_scene()
    {
        var wrapper = Wrapper([Line("A", "B")], new SpawnPoint { Scene = "T", Entries = [0] });
        Assert.Throws<InvalidDataException>(() => GuideData.ValidateWrapper(wrapper));
    }

    [Fact]
    public void Validation_rejects_entries_without_the_placement_destination_lookup()
    {
        var wrapper = Wrapper([Line("A", "T")], new SpawnPoint { Scene = "T", Entries = [0] });
        wrapper.ZoneLookup!.Remove("T");
        Assert.Throws<InvalidDataException>(() => GuideData.ValidateWrapper(wrapper));
    }

    [Fact]
    public void Validation_accepts_repeated_entries_and_preserves_their_order()
    {
        var spawn = new SpawnPoint { Scene = "T", Entries = [1, 0, 1] };
        var (data, _, graph) = Build(Wrapper([Line("A", "T"), Line("A", "T")], spawn));
        Assert.Same(data.ZoneLines[1], graph.GetPlacementRoute(spawn, "A")!.Value.EntryLine);
    }

    [Theory]
    [InlineData(false)]
    [InlineData(true)]
    public void Requirements_include_both_the_entry_condition_and_approach_route_conditions(
        bool onEntry
    )
    {
        var spawn = new SpawnPoint { Scene = "T", Entries = [0] };
        var wrapper = Wrapper(
            [
                Line("B", "T", onEntry ? 0 : null),
                Line("A", "B", onEntry ? null : 0),
                Line("A", "T"),
            ],
            spawn,
            [
                [
                    [new() { Kind = GateAtomKind.KeyHeld, Ref = "item:key" }],
                ],
            ]
        );
        var source = new ItemSource
        {
            Type = "pickup",
            SourceKey = "itembag:a:1:2:3",
            Scene = "A",
        };
        wrapper.GateItems = new()
        {
            ["item:key"] = new()
            {
                Name = "Entry Key",
                GameId = "key",
                Sources = [source],
            },
        };
        var (data, gates, graph) = Build(wrapper);
        var step = Step();
        var result = new RequirementResolver(data, gates, graph, quest => quest.Steps![0]).Resolve(
            Quest(step),
            step,
            "A"
        );
        Assert.True(result.CanNavigate, result.Message);
        Assert.Equal("item:key", result.Step.TargetKey);
        Assert.Same(source, Assert.Single(result.Step.Sources!));
        Assert.Contains(result.Chain, link => link.Label == "Requires Entry Key");
    }
}
