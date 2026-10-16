using AdventureGuide.Data;
using AdventureGuide.Navigation;
using AdventureGuide.State;

namespace AdventureGuide.Tests;

public sealed class NavigationResolutionPolicyTests
{
    [Fact]
    public void Completed_first_step_stays_advanced_across_source_repicks_and_state_changes()
    {
        QuestStep[] steps =
        [
            new() { Order = 1, TargetKey = "item:first" },
            new() { Order = 2, TargetKey = "item:second" },
        ];
        int selectedOrder = NavigationResolutionPolicy.SelectOriginStepOrder(steps, 1, 1);
        Assert.Equal(2, selectedOrder);

        int resolutionVersion = 10;
        foreach (int stateVersion in new[] { 10, 10, 11, 11, 12 })
        {
            if (
                NavigationResolutionPolicy.ShouldResolveRequirements(
                    stateVersion,
                    resolutionVersion
                )
            )
                resolutionVersion = stateVersion;
            selectedOrder = NavigationResolutionPolicy.SelectOriginStepOrder(
                steps,
                selectedOrder,
                1
            );
            Assert.Equal(2, selectedOrder);
        }
    }

    [Fact]
    public void Explicit_future_selection_does_not_move_back_to_current_step()
    {
        QuestStep[] steps =
        [
            new() { Order = 10, TargetKey = "item:first" },
            new() { Order = 20, TargetKey = "item:second" },
            new() { Order = 30, TargetKey = "item:third" },
        ];
        Assert.Equal(30, NavigationResolutionPolicy.SelectOriginStepOrder(steps, 30, 1));
    }

    [Fact]
    public void Advancement_skips_non_navigable_steps_and_accepts_locations()
    {
        QuestStep[] steps =
        [
            new() { Order = 1, TargetKey = "item:first" },
            new() { Order = 2 },
            new() { Order = 3, Location = new WorkflowLocation() },
        ];
        Assert.Equal(3, NavigationResolutionPolicy.SelectOriginStepOrder(steps, 1, 1));
        Assert.Equal(0, NavigationResolutionPolicy.SelectOriginStepOrder(steps, 1, 3));
        Assert.Equal(0, NavigationResolutionPolicy.SelectOriginStepOrder(steps, 99, 0));
        Assert.Equal(0, NavigationResolutionPolicy.SelectOriginStepOrder([], 1, 0));
    }

    [Theory]
    [InlineData(10, 10, false)]
    [InlineData(11, 10, true)]
    [InlineData(9, 10, true)]
    public void Requirements_resolve_only_for_changed_versions(
        int state,
        int resolution,
        bool expected
    )
    {
        Assert.Equal(
            expected,
            NavigationResolutionPolicy.ShouldResolveRequirements(state, resolution)
        );
    }

    [Fact]
    public void Copied_quest_and_narrowed_step_retain_pin_identity()
    {
        var quest = new QuestEntry { DBName = "Quest", StableKey = "quest:original" };
        var copy = new QuestEntry { DBName = "Quest", StableKey = "quest:copy" };
        var step = new QuestStep
        {
            Order = 2,
            TargetKey = "item:target",
            Sources = [new ItemSource(), new ItemSource()],
        };
        var narrowed = new QuestStep
        {
            Order = 2,
            TargetKey = "item:target",
            Sources = [step.Sources[1]],
        };
        Assert.True(NavigationResolutionPolicy.SameStep(quest, step, copy, narrowed));
        copy.DBName = "Other";
        Assert.False(NavigationResolutionPolicy.SameStep(quest, step, copy, narrowed));
        copy.DBName = quest.DBName;
        narrowed.Order = 3;
        Assert.False(NavigationResolutionPolicy.SameStep(quest, step, copy, narrowed));
        narrowed.Order = step.Order;
        narrowed.TargetKey = "item:other";
        Assert.False(NavigationResolutionPolicy.SameStep(quest, step, copy, narrowed));
    }

    [Fact]
    public void Guide_only_quest_identity_uses_stable_key_not_empty_database_name()
    {
        var first = new QuestEntry
        {
            StableKey = "guide:first",
            Flags = new() { GuideOnly = true },
        };
        var second = new QuestEntry
        {
            StableKey = "guide:second",
            Flags = new() { GuideOnly = true },
        };
        var step = new QuestStep { Order = 1, TargetKey = "item:target" };
        Assert.False(NavigationResolutionPolicy.SameStep(first, step, second, step));
        second.StableKey = first.StableKey;
        Assert.True(NavigationResolutionPolicy.SameStep(first, step, second, step));
    }

    [Fact]
    public void Permanent_lines_are_filtered_but_missing_key_lines_remain_available_for_guidance()
    {
        var data = GuideData.FromWrapper(
            new GuideWrapper
            {
                Version = 7,
                Quests = [],
                GateItems = new()
                {
                    ["item:key"] = new GateItem { Name = "Key", GameId = "key-id" },
                },
                Conditions =
                [
                    [],
                    [
                        [new GateAtom { Kind = GateAtomKind.KeyHeld, Ref = "item:key" }],
                    ],
                    [
                        [new GateAtom { Kind = GateAtomKind.QuestNotDone, Ref = "finished" }],
                    ],
                ],
            }
        );
        var facts = new GateTestFacts();
        facts.Quests.Add("finished");
        var gates = new GateConditions(data, facts);
        Assert.False(NavigationResolutionPolicy.CanUseZoneLine(new() { Condition = 0 }, gates));
        Assert.False(NavigationResolutionPolicy.CanUseZoneLine(new() { Condition = 2 }, gates));
        Assert.False(gates.IsAvailable(1));
        Assert.True(NavigationResolutionPolicy.CanUseZoneLine(new() { Condition = 1 }, gates));
        Assert.True(NavigationResolutionPolicy.CanUseZoneLine(new(), gates));
    }

    [Theory]
    [InlineData(true, false)]
    [InlineData(false, true)]
    public void Completed_quests_cannot_be_resolved_again(bool completed, bool expected)
    {
        Assert.Equal(expected, NavigationResolutionPolicy.CanResolveQuest(completed));
    }

    [Theory]
    [InlineData(false)]
    [InlineData(true)]
    public void Same_effective_plan_reuses_endpoint_with_shared_or_new_wrapper_lists(bool newLists)
    {
        var sources = new List<ItemSource> { new(), new() };
        var spawns = new List<SpawnPoint> { new(), new() };
        var location = new WorkflowLocation();
        var line = new ZoneLineEntry();
        var previous = EndpointResolution(
            new() { DBName = "Quest" },
            new()
            {
                Order = 1,
                TargetKey = "item:target",
                Sources = sources,
                Location = location,
            },
            selectedSpawn: spawns[0],
            entryLine: line,
            availableSpawns: spawns
        );
        var current = EndpointResolution(
            new() { DBName = "QUEST" },
            new()
            {
                Order = 1,
                TargetKey = "ITEM:TARGET",
                Sources = newLists ? new List<ItemSource>(sources) : sources,
                Location = location,
            },
            selectedScene: "SCENE",
            selectedSpawn: spawns[0],
            entryLine: line,
            availableSpawns: newLists ? new List<SpawnPoint>(spawns) : spawns
        );

        Assert.True(NavigationResolutionPolicy.CanReuseEndpoint(previous, current, true, false));
    }

    [Theory]
    [InlineData(false)]
    [InlineData(true)]
    public void Effective_sources_compare_required_item_fallback_against_step_sources(bool changed)
    {
        var source = new ItemSource();
        var previous = EndpointResolution(
            new()
            {
                DBName = "Quest",
                RequiredItems = [new() { ItemStableKey = "item:target", Sources = [source] }],
            },
            new() { Order = 1, TargetKey = "item:target" }
        );
        var current = EndpointResolution(
            new() { DBName = "Quest" },
            new()
            {
                Order = 1,
                TargetKey = "item:target",
                Sources = [changed ? new ItemSource() : source],
            }
        );

        Assert.Equal(
            !changed,
            NavigationResolutionPolicy.CanReuseEndpoint(previous, current, true, false)
        );
    }

    [Theory]
    [InlineData("quest")]
    [InlineData("order")]
    [InlineData("target")]
    [InlineData("location")]
    [InlineData("missing-location")]
    [InlineData("scene")]
    [InlineData("selected-spawn")]
    [InlineData("entry-line")]
    [InlineData("source")]
    [InlineData("source-order")]
    [InlineData("source-count")]
    [InlineData("placement")]
    [InlineData("placement-order")]
    [InlineData("placement-count")]
    [InlineData("blocked-previous")]
    [InlineData("blocked-current")]
    public void Changed_effective_plan_requires_endpoint_resolution(string change)
    {
        var sourceA = new ItemSource();
        var sourceB = new ItemSource();
        var spawnA = new SpawnPoint();
        var spawnB = new SpawnPoint();
        var location = new WorkflowLocation { X = 1 };
        var line = new ZoneLineEntry();
        var previous = EndpointResolution(
            new() { DBName = "Quest" },
            new()
            {
                Order = 1,
                TargetKey = "item:target",
                Sources = [sourceA, sourceB],
                Location = location,
            },
            canNavigate: change != "blocked-previous",
            selectedSpawn: spawnA,
            entryLine: line,
            availableSpawns: [spawnA, spawnB]
        );
        var quest = new QuestEntry { DBName = change == "quest" ? "Other" : "Quest" };
        var step = new QuestStep
        {
            Order = change == "order" ? 2 : 1,
            TargetKey = change == "target" ? "item:other" : "item:target",
            Location = change switch
            {
                "location" => new WorkflowLocation { X = 2 },
                "missing-location" => null,
                _ => location,
            },
            Sources = change switch
            {
                "source" => [sourceA, new ItemSource()],
                "source-order" => [sourceB, sourceA],
                "source-count" => [sourceA],
                _ => [sourceA, sourceB],
            },
        };
        var current = EndpointResolution(
            quest,
            step,
            canNavigate: change != "blocked-current",
            selectedScene: change == "scene" ? "Other" : "Scene",
            selectedSpawn: change == "selected-spawn" ? new SpawnPoint() : spawnA,
            entryLine: change == "entry-line" ? new ZoneLineEntry() : line,
            availableSpawns: change switch
            {
                "placement" => [spawnA, new SpawnPoint()],
                "placement-order" => [spawnB, spawnA],
                "placement-count" => [spawnA],
                _ => [spawnA, spawnB],
            }
        );

        Assert.False(NavigationResolutionPolicy.CanReuseEndpoint(previous, current, true, false));
    }

    [Theory]
    [InlineData(false)]
    [InlineData(true)]
    public void Null_and_empty_source_or_placement_constraints_are_distinct(bool sources)
    {
        var quest = new QuestEntry { DBName = "Quest" };
        var previous = EndpointResolution(quest, new() { Order = 1, TargetKey = "item:target" });
        var current = EndpointResolution(
            quest,
            new()
            {
                Order = 1,
                TargetKey = "item:target",
                Sources = sources ? [] : null,
            },
            availableSpawns: sources ? null : []
        );

        Assert.False(NavigationResolutionPolicy.CanReuseEndpoint(previous, current, true, false));
        Assert.False(NavigationResolutionPolicy.CanReuseEndpoint(current, previous, true, false));
    }

    [Fact]
    public void Missing_previous_endpoint_or_target_and_item_use_require_resolution()
    {
        var resolution = EndpointResolution(
            new() { DBName = "Quest" },
            new()
            {
                Order = 1,
                TargetKey = "item:target",
                Sources = [new() { Children = [new() { Type = "item_use" }] }],
            }
        );

        Assert.False(NavigationResolutionPolicy.CanReuseEndpoint(null, resolution, true, false));
        Assert.False(
            NavigationResolutionPolicy.CanReuseEndpoint(resolution, resolution, false, false)
        );
        Assert.False(
            NavigationResolutionPolicy.CanReuseEndpoint(resolution, resolution, true, true)
        );
    }

    private static RequirementResolution EndpointResolution(
        QuestEntry quest,
        QuestStep step,
        bool canNavigate = true,
        string? selectedScene = "Scene",
        SpawnPoint? selectedSpawn = null,
        ZoneLineEntry? entryLine = null,
        IReadOnlyList<SpawnPoint>? availableSpawns = null
    ) =>
        new(
            quest,
            step,
            canNavigate,
            null,
            [],
            [],
            selectedScene,
            selectedSpawn,
            entryLine,
            availableSpawns
        );
}
