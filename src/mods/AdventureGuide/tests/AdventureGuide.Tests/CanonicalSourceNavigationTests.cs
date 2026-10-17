using AdventureGuide.Data;
using AdventureGuide.Navigation;
using AdventureGuide.State;

namespace AdventureGuide.Tests;

public sealed class CanonicalSourceNavigationTests
{
    private static QuestEntry Quest(params ItemSource[] sources) =>
        new()
        {
            StableKey = "quest:goal",
            DBName = "Goal",
            DisplayName = "Goal",
            Steps =
            [
                new()
                {
                    Order = 1,
                    Action = "obtain",
                    Description = "Obtain the key.",
                    TargetType = "item",
                    TargetKey = "item:crafted key",
                    TargetName = "Crafted Key",
                    Sources = [.. sources],
                },
            ],
        };

    private static GuideWrapper Wrapper(QuestEntry quest) =>
        new()
        {
            Version = 8,
            Quests = [quest],
            ZoneLineDestinationContexts = new(),
            Encounters = new()
            {
                Placements = [],
                Conditions = [],
                Completions = [],
                EventConditions = [],
            },
            ZoneLookup = new()
            {
                ["Home"] = new() { StableKey = "zone:home", DisplayName = "Home" },
                ["A"] = new() { StableKey = "zone:a", DisplayName = "A" },
                ["B"] = new() { StableKey = "zone:b", DisplayName = "B" },
            },
            ZoneLines =
            [
                new()
                {
                    StableKey = "zoneline:home:a",
                    Scene = "Home",
                    DestinationZoneKey = "zone:a",
                },
                new()
                {
                    StableKey = "zoneline:home:b",
                    Scene = "Home",
                    DestinationZoneKey = "zone:b",
                },
            ],
            CharacterSpawns = new()
            {
                ["character:group"] =
                [
                    new()
                    {
                        Scene = "B",
                        X = 1,
                        Y = 2,
                        Z = 3,
                    },
                ],
                ["character:key vendor"] =
                [
                    new()
                    {
                        Scene = "Home",
                        X = 4,
                        Y = 5,
                        Z = 6,
                    },
                ],
            },
        };

    private static ItemSource Located(string key, string scene, float x = 100) =>
        new()
        {
            Type = "drop",
            SourceKey = "character:group",
            Name = key,
            AcquisitionKey = "acquisition:" + key,
            LocationKey = "location:" + key,
            ItemStableKey = "item:" + key,
            Scene = scene,
            X = x,
            Y = 20,
            Z = 30,
        };

    private static SourceFact AddFact(
        GuideWrapper wrapper,
        ItemSource source,
        string kind = "character_drop"
    )
    {
        var fact = new SourceFact
        {
            AcquisitionKey = source.AcquisitionKey!,
            ItemStableKey = source.ItemStableKey!,
            Kind = kind,
            PlayerAccessState = "verified_player",
            ProbabilityKind = "exact",
            ProbabilityStage = "final_acquisition",
            ProbabilityMin = 100,
            ProbabilityMax = 100,
            QuantityMin = 1,
            QuantityMax = 1,
            Locations =
                source.LocationKey == null
                    ? []
                    :
                    [
                        new()
                        {
                            LocationKey = source.LocationKey,
                            Relation = "fixed",
                            Scene = source.Scene,
                            X = source.X,
                            Y = source.Y,
                            Z = source.Z,
                            EntryZoneLineKeys = source.EntryZoneLineKeys ?? [],
                        },
                    ],
        };
        wrapper.SourceFacts.Add(fact.AcquisitionKey, fact);
        return fact;
    }

    private static (GuideData data, RequirementResolver resolver, ZoneGraph graph) Build(
        GuideWrapper wrapper,
        GateTestFacts? facts = null
    )
    {
        var data = GuideData.FromWrapper(wrapper);
        var gates = new GateConditions(data, facts ?? new());
        var graph = new ZoneGraph(data, gates);
        return (
            data,
            new RequirementResolver(data, gates, graph, quest => quest.Steps?.FirstOrDefault()),
            graph
        );
    }

    private static SourceFact AddPlacementPair(
        GuideWrapper wrapper,
        ItemSource first,
        ItemSource second
    )
    {
        second.AcquisitionKey = first.AcquisitionKey;
        second.ItemStableKey = first.ItemStableKey;
        var fact = AddFact(wrapper, first);
        fact.Locations.Add(
            new()
            {
                LocationKey = second.LocationKey!,
                Relation = "fixed",
                Scene = second.Scene,
                X = second.X,
                Y = second.Y,
                Z = second.Z,
                EntryZoneLineKeys = second.EntryZoneLineKeys ?? [],
            }
        );
        return fact;
    }

    [Fact]
    public void Chosen_acquisition_uses_allowed_member_and_repicks_after_live_state_changes()
    {
        var first = Located("first", "A", 110);
        var second = Located("second", "B", 220);
        first.EntryZoneLineKeys = ["zoneline:home:a"];
        second.EntryZoneLineKeys = ["zoneline:home:b"];
        var other = Located("unselected", "Home", 330);
        var quest = Quest(first, second, other);
        var wrapper = Wrapper(quest);
        var fact = AddPlacementPair(wrapper, first, second);
        fact.ProbabilityMin = 0.00001;
        fact.ProbabilityMax = 0.00001;
        fact.ProbabilityBasis = "per_native_roll";
        fact.Locations[0]
            .Conditions.Add(
                new()
                {
                    GateKey = "gate:first:level",
                    Predicate = "actor_level",
                    Actor = "player",
                    Minimum = 20,
                    Scope = first.LocationKey!,
                    Phase = "availability",
                }
            );
        fact.Locations[1]
            .Conditions.Add(
                new()
                {
                    GateKey = "gate:second:level",
                    Predicate = "actor_level",
                    Actor = "player",
                    Maximum = 19,
                    Scope = second.LocationKey!,
                    Phase = "availability",
                }
            );
        AddFact(wrapper, other);
        var facts = new GateTestFacts { PlayerLevel = 5 };
        var (_, resolver, graph) = Build(wrapper, facts);
        var selection = new SourceNavigationSelection();
        var step = quest.Steps![0];
        Assert.True(
            selection.Select(SourceChoice.FindContaining(step.Sources, first)!, step, quest)
        );

        var lowLevel = selection.Resolve(resolver, quest, step, "Home");
        Assert.True(lowLevel.CanNavigate, lowLevel.Message);
        Assert.Equal("B", lowLevel.SelectedScene);
        Assert.Equal(220, lowLevel.SelectedSpawn!.X);
        Assert.Equal("zoneline:home:b", lowLevel.EntryLine!.StableKey);
        Assert.Equal(
            "acquisition:first|location:second",
            Assert.Single(lowLevel.Step.Sources!).MakeSourceId()
        );

        facts.PlayerLevel = 30;
        graph.Rebuild();
        var highLevel = selection.Resolve(resolver, quest, step, "Home");
        Assert.True(highLevel.CanNavigate, highLevel.Message);
        Assert.Equal("A", highLevel.SelectedScene);
        Assert.Equal(110, highLevel.SelectedSpawn!.X);
        Assert.Equal("zoneline:home:a", highLevel.EntryLine!.StableKey);
        Assert.Equal(
            "acquisition:first|location:first",
            Assert.Single(highLevel.Step.Sources!).MakeSourceId()
        );
        Assert.Equal("item:crafted key", highLevel.Step.TargetKey);
        Assert.Equal(0.00001, fact.ProbabilityMin);
        Assert.Equal(0.00001, fact.ProbabilityMax);
        Assert.Equal("per_native_roll", fact.ProbabilityBasis);
        Assert.Equal("final_acquisition", fact.ProbabilityStage);
    }

    [Fact]
    public void Scene_change_repicks_an_actual_member_without_switching_acquisitions()
    {
        var first = Located("first", "A", 110);
        var second = Located("second", "B", 220);
        var other = Located("unselected", "B", 330);
        var quest = Quest(first, second, other);
        var wrapper = Wrapper(quest);
        AddPlacementPair(wrapper, first, second);
        AddFact(wrapper, other);
        var (_, resolver, graph) = Build(wrapper);
        var step = quest.Steps![0];
        var selection = new SourceNavigationSelection();
        Assert.True(
            selection.Select(SourceChoice.FindContaining(step.Sources, first)!, step, quest)
        );

        var inA = selection.Resolve(resolver, quest, step, "A");
        Assert.True(inA.CanNavigate, inA.Message);
        Assert.Equal(
            "acquisition:first|location:first",
            Assert.Single(inA.Step.Sources!).MakeSourceId()
        );
        Assert.Equal(110, inA.SelectedSpawn!.X);

        graph.Rebuild();
        var inB = selection.Resolve(resolver, quest, step, "B");
        Assert.True(inB.CanNavigate, inB.Message);
        Assert.Equal(
            "acquisition:first|location:second",
            Assert.Single(inB.Step.Sources!).MakeSourceId()
        );
        Assert.Equal(220, inB.SelectedSpawn!.X);
    }

    [Fact]
    public void Canonical_location_does_not_expand_a_grouped_character_to_other_copies()
    {
        var source = Located("actual", "A");
        var quest = Quest(source);
        var wrapper = Wrapper(quest);
        AddFact(wrapper, source);
        var (data, resolver, _) = Build(wrapper);
        var result = resolver.Resolve(quest, quest.Steps![0], "Home");
        Assert.True(result.CanNavigate, result.Message);
        Assert.Equal("A", result.SelectedScene);
        Assert.Equal(100, result.SelectedSpawn!.X);
        Assert.Same(source.CanonicalSpawn, result.SelectedSpawn);
        Assert.Same(source, Assert.Single(result.Step.Sources!));
        Assert.Equal("A", StepSceneResolver.ResolveScene(quest, quest.Steps[0], data));
        Assert.True(StepSceneResolver.HasSourceInScene(quest, quest.Steps[0], data, "A"));
        Assert.False(StepSceneResolver.HasSourceInScene(quest, quest.Steps[0], data, "B"));
        Assert.True(PositionedSource.TryCreate(source, out var position));
        Assert.Equal("A", position.Scene);
        Assert.Equal(100, position.X);
        Assert.Equal("acquisition:actual|location:actual", source.MakeSourceId());
    }

    [Fact]
    public void Exact_canonical_entry_restriction_cannot_use_an_unrelated_open_copy()
    {
        var source = Located("actual", "A");
        source.EntryZoneLineKeys = ["zoneline:home:a"];
        var quest = Quest(source);
        var wrapper = Wrapper(quest);
        wrapper.Conditions =
        [
            [],
        ];
        wrapper.ZoneLines![0].Condition = 0;
        wrapper.ZoneLines.Add(
            new()
            {
                StableKey = "zoneline:home:a-open",
                Scene = "Home",
                DestinationZoneKey = "zone:a",
            }
        );
        AddFact(wrapper, source);
        var (_, resolver, graph) = Build(wrapper);
        Assert.NotNull(graph.FindRoute("Home", "A"));
        var result = resolver.Resolve(quest, quest.Steps![0], "Home");
        Assert.False(result.CanNavigate);
        Assert.Equal("No route reaches this requirement.", result.Message);
    }

    [Theory]
    [InlineData("starting_class")]
    [InlineData("ui_grant")]
    public void Unlocated_native_actions_are_explanatory_not_arbitrary_character_routes(string kind)
    {
        var source = new ItemSource
        {
            Type = kind,
            AcquisitionKey = "acquisition:unlocated",
            ItemStableKey = "item:gift",
            SourceKey = "character:group",
            Scene = "B",
            Name = "Native action",
        };
        var quest = Quest(source);
        var wrapper = Wrapper(quest);
        AddFact(wrapper, source, kind);
        var (data, resolver, _) = Build(wrapper);
        Assert.False(resolver.Resolve(quest, quest.Steps![0], "Home").CanNavigate);
        Assert.Null(StepSceneResolver.ResolveScene(quest, quest.Steps[0], data));
        Assert.False(StepSceneResolver.HasSourceInScene(quest, quest.Steps[0], data, "B"));
        Assert.False(PositionedSource.TryCreate(source, out _));
    }

    [Fact]
    public void Canonical_observable_availability_routes_to_its_requirement_without_legacy_condition()
    {
        var source = Located("actual", "A");
        var quest = Quest(source);
        var wrapper = Wrapper(quest);
        var fact = AddFact(wrapper, source);
        fact.Conditions.Add(
            new()
            {
                GateKey = "gate:key",
                Predicate = "item_held",
                ReferenceStableKey = "item:entry key",
                Actor = "player",
                Scope = "acquisition",
                Phase = "availability",
            }
        );
        wrapper.GateItems = new()
        {
            ["item:entry key"] = new()
            {
                Name = "Entry Key",
                Sources =
                [
                    new()
                    {
                        Type = "vendor",
                        Name = "Key vendor",
                        SourceKey = "character:key vendor",
                        Instruction = "Buy Entry Key.",
                    },
                ],
            },
        };
        var facts = new GateTestFacts();
        var (_, resolver, _) = Build(wrapper, facts);
        var selection = new SourceNavigationSelection();
        Assert.True(
            selection.Select(
                SourceChoice.ForSources(quest.Steps![0].Sources)[0],
                quest.Steps[0],
                quest
            )
        );
        var required = selection.Resolve(resolver, quest, quest.Steps[0], "Home");
        Assert.True(required.CanNavigate, required.Message);
        Assert.Equal("item:entry key", required.Step.TargetKey);
        Assert.Contains(required.Chain, link => link.Atom?.Ref == "item:entry key");
        Assert.Equal("Crafted Key", required.Chain[0].Label);
        facts.Inventory["item:entry key"] = 1;
        var ready = selection.Resolve(resolver, quest, quest.Steps[0], "Home");
        Assert.True(ready.CanNavigate, ready.Message);
        Assert.Equal("A", ready.SelectedScene);
        Assert.Equal(source.MakeSourceId(), Assert.Single(ready.Step.Sources!).MakeSourceId());
    }

    [Fact]
    public void Canonical_player_level_failure_is_non_navigable_even_without_a_gate_atom()
    {
        var source = Located("level gated", "A");
        var quest = Quest(source);
        var wrapper = Wrapper(quest);
        var fact = AddFact(wrapper, source);
        fact.Conditions.Add(
            new()
            {
                GateKey = "gate:level",
                Predicate = "actor_level",
                Actor = "player",
                Minimum = 20,
                Scope = "acquisition",
                Phase = "availability",
            }
        );
        var (_, resolver, _) = Build(wrapper, new() { PlayerLevel = 5 });
        var result = resolver.Resolve(quest, quest.Steps![0], "Home");
        Assert.False(result.CanNavigate);
        Assert.Contains("level", result.Message!, StringComparison.OrdinalIgnoreCase);
    }

    private static ItemSource Ingredient(
        GuideWrapper wrapper,
        string key,
        double quantity,
        ItemSource source,
        string slot
    )
    {
        string useKey = "use:" + slot;
        wrapper.ItemUses.Add(
            useKey,
            new()
            {
                UseKey = useKey,
                ItemStableKey = key,
                Kind = "crafting_material",
                QuantityMin = quantity,
            }
        );
        return new()
        {
            Type = "ingredient",
            Name = key.Substring("item:".Length),
            ItemStableKey = key,
            Quantity = quantity,
            UseKey = useKey,
            Children = [source],
        };
    }

    [Fact]
    public void Crafted_key_follows_remaining_materials_and_keeps_the_selected_recipe_and_original_goal()
    {
        var recipe = new ItemSource
        {
            Type = "crafting",
            Name = "Key recipe",
            AcquisitionKey = "acquisition:recipe",
            ItemStableKey = "item:crafted key",
        };
        var quest = Quest(recipe);
        var wrapper = Wrapper(quest);
        AddFact(wrapper, recipe, "crafting");
        var first = Located("ore", "A");
        var second = Located("wood", "B");
        AddFact(wrapper, first);
        AddFact(wrapper, second);
        recipe.Children =
        [
            Ingredient(wrapper, "item:ore", 2, first, "ore"),
            Ingredient(wrapper, "item:wood", 1, second, "wood"),
        ];
        var facts = new GateTestFacts();
        facts.Inventory["item:ore"] = 1;
        var (data, resolver, _) = Build(wrapper, facts);
        var selection = new SourceNavigationSelection();
        Assert.True(
            selection.Select(
                SourceChoice.ForSources(quest.Steps![0].Sources)[0],
                quest.Steps[0],
                quest
            )
        );
        var ore = selection.Resolve(resolver, quest, quest.Steps[0], "Home");
        Assert.True(ore.CanNavigate, ore.Message);
        Assert.Equal("A", ore.SelectedScene);
        Assert.Same(first, Assert.Single(ore.Step.Sources!));
        Assert.Equal("item:ore", ore.Step.TargetKey);
        Assert.Equal(2, ore.Step.Quantity);
        Assert.Equal("Crafted Key", ore.Chain[0].Label);
        Assert.Equal("item:crafted key", quest.Steps[0].TargetKey);
        facts.Inventory["item:ore"] = 2;
        var wood = selection.Resolve(resolver, quest, quest.Steps[0], "Home");
        Assert.True(wood.CanNavigate, wood.Message);
        Assert.Equal("B", wood.SelectedScene);
        Assert.Same(second, Assert.Single(wood.Step.Sources!));
        Assert.Equal("item:wood", wood.Step.TargetKey);
        Assert.Equal("Crafted Key", wood.Chain[0].Label);
        Assert.Equal(
            "B",
            StepSceneResolver.ResolveScene(quest, quest.Steps[0], data, countItem: facts.ItemCount)
        );
        Assert.False(
            StepSceneResolver.HasSourceInScene(
                quest,
                quest.Steps[0],
                data,
                "A",
                countItem: facts.ItemCount
            )
        );
    }

    [Fact]
    public void Repeated_native_material_slots_consume_inventory_cumulatively()
    {
        var first = new ItemSource
        {
            Type = "ingredient",
            ItemStableKey = "item:ore",
            Quantity = 2,
        };
        var second = new ItemSource
        {
            Type = "ingredient",
            ItemStableKey = "item:ore",
            Quantity = 2,
        };
        List<ItemSource> inputs = [first, second];
        Assert.False(ItemSourcePolicy.NeedsUsedItem(first, _ => 2, inputs));
        Assert.True(ItemSourcePolicy.NeedsUsedItem(second, _ => 2, inputs));
        Assert.False(ItemSourcePolicy.NeedsUsedItem(second, _ => 4, inputs));
    }

    [Theory]
    [InlineData("ui_grant")]
    [InlineData("auction_house")]
    public void Located_native_actions_navigate_to_the_real_endpoint_without_a_character_family(
        string kind
    )
    {
        var source = Located("native", "A", 150);
        source.Type = kind;
        source.SourceKey = null;
        var quest = Quest(source);
        var wrapper = Wrapper(quest);
        AddFact(wrapper, source, kind);
        var (_, resolver, _) = Build(wrapper);
        var result = resolver.Resolve(quest, quest.Steps![0], "Home");
        Assert.True(result.CanNavigate, result.Message);
        Assert.Equal("A", result.SelectedScene);
        Assert.Equal(150, result.SelectedSpawn!.X);
        Assert.True(PositionedSource.TryCreate(source, out var endpoint));
        Assert.Equal(150, endpoint.X);
    }

    [Fact]
    public void Ancestor_canonical_availability_blocks_an_otherwise_reachable_ingredient()
    {
        var recipe = new ItemSource
        {
            Type = "crafting",
            Name = "Recipe",
            AcquisitionKey = "acquisition:recipe",
            ItemStableKey = "item:crafted key",
        };
        var quest = Quest(recipe);
        var wrapper = Wrapper(quest);
        var recipeFact = AddFact(wrapper, recipe, "crafting");
        recipeFact.Conditions.Add(
            new()
            {
                GateKey = "gate:recipe-level",
                Predicate = "actor_level",
                Actor = "player",
                Minimum = 20,
                Scope = "acquisition",
                Phase = "availability",
            }
        );
        var material = Located("ore", "A");
        AddFact(wrapper, material);
        recipe.Children = [Ingredient(wrapper, "item:ore", 2, material, "ore")];
        var (_, resolver, _) = Build(wrapper, new() { PlayerLevel = 1 });
        var result = resolver.Resolve(quest, quest.Steps![0], "Home");
        Assert.False(result.CanNavigate);
        Assert.Contains("level", result.Message!, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public void Repeated_material_slot_route_requires_the_cumulative_inventory_amount()
    {
        var recipe = new ItemSource
        {
            Type = "crafting",
            Name = "Recipe",
            AcquisitionKey = "acquisition:recipe",
            ItemStableKey = "item:crafted key",
        };
        var quest = Quest(recipe);
        var wrapper = Wrapper(quest);
        AddFact(wrapper, recipe, "crafting");
        var material = Located("ore", "A");
        AddFact(wrapper, material);
        recipe.Children =
        [
            Ingredient(wrapper, "item:ore", 2, material, "first"),
            Ingredient(wrapper, "item:ore", 2, material, "second"),
        ];
        var facts = new GateTestFacts();
        facts.Inventory["item:ore"] = 2;
        var (_, resolver, _) = Build(wrapper, facts);
        var result = resolver.Resolve(quest, quest.Steps![0], "Home");
        Assert.True(result.CanNavigate, result.Message);
        Assert.Equal("item:ore", result.Step.TargetKey);
        Assert.Equal(4, result.Step.Quantity);
    }

    [Theory]
    [InlineData(0)]
    [InlineData(1)]
    [InlineData(3)]
    [InlineData(4)]
    [InlineData(7)]
    public void Collapsed_material_NAV_keeps_the_total_native_requirement(int have)
    {
        var recipe = new ItemSource
        {
            Type = "crafting",
            AcquisitionKey = "acquisition:recipe",
            ItemStableKey = "item:crafted key",
        };
        var quest = Quest(recipe);
        var wrapper = Wrapper(quest);
        AddFact(wrapper, recipe, "crafting");
        var material = Located("ore", "A");
        AddFact(wrapper, material);
        recipe.Children = [];
        for (int slot = 1; slot <= 8; slot++)
        {
            var input = Ingredient(wrapper, "item:ore", 1, material, slot.ToString());
            wrapper.ItemUses[input.UseKey!].TargetStableKey = "recipe:key";
            recipe.Children.Add(input);
        }
        var facts = new GateTestFacts();
        facts.Inventory["item:ore"] = have;
        var (_, resolver, _) = Build(wrapper, facts);
        var row = Assert.Single(ItemSourcePolicy.PresentationSources(recipe.Children));
        var selection = new SourceNavigationSelection();
        Assert.True(selection.Select(row, quest.Steps![0], quest));
        var result = selection.Resolve(resolver, quest, quest.Steps[0], "Home");
        Assert.True(result.CanNavigate, result.Message);
        Assert.Equal("item:ore", result.Step.TargetKey);
        Assert.Equal(8, result.Step.Quantity);
        Assert.Equal("item:crafted key", quest.Steps[0].TargetKey);
    }

    [Fact]
    public void Completing_an_explicit_material_resumes_its_recipe_and_other_inputs()
    {
        var recipe = new ItemSource
        {
            Type = "crafting",
            AcquisitionKey = "acquisition:recipe",
            ItemStableKey = "item:crafted key",
        };
        var quest = Quest(recipe);
        var wrapper = Wrapper(quest);
        AddFact(wrapper, recipe, "crafting");
        var ore = Located("ore", "A");
        var wood = Located("wood", "B");
        AddFact(wrapper, ore);
        AddFact(wrapper, wood);
        recipe.Children = [];
        for (int slot = 1; slot <= 8; slot++)
        {
            var input = Ingredient(wrapper, "item:ore", 1, ore, slot.ToString());
            wrapper.ItemUses[input.UseKey!].TargetStableKey = "recipe:key";
            recipe.Children.Add(input);
        }
        recipe.Children.Add(Ingredient(wrapper, "item:wood", 1, wood, "wood"));
        var facts = new GateTestFacts();
        facts.Inventory["item:ore"] = 7;
        var (_, resolver, _) = Build(wrapper, facts);
        var selection = new SourceNavigationSelection();
        var row = ItemSourcePolicy.PresentationSources(recipe.Children)[0];
        Assert.True(selection.Select(row, quest.Steps![0], quest));
        var missingOre = selection.Resolve(resolver, quest, quest.Steps[0], "Home");
        Assert.True(missingOre.CanNavigate, missingOre.Message);
        Assert.Equal("item:ore", missingOre.Step.TargetKey);
        Assert.Equal(8, missingOre.Step.Quantity);

        facts.Inventory["item:ore"] = 8;
        var missingWood = selection.Resolve(resolver, quest, quest.Steps[0], "Home");
        Assert.True(missingWood.CanNavigate, missingWood.Message);
        Assert.Equal("item:wood", missingWood.Step.TargetKey);
        Assert.Equal(1, missingWood.Step.Quantity);
        Assert.Same(recipe, selection.Choice!.Primary);
        Assert.Equal("item:crafted key", quest.Steps[0].TargetKey);

        facts.Inventory["item:ore"] = 7;
        var usedOre = selection.Resolve(resolver, quest, quest.Steps[0], "Home");
        Assert.True(usedOre.CanNavigate, usedOre.Message);
        Assert.Equal("item:ore", usedOre.Step.TargetKey);
        Assert.Equal(8, usedOre.Step.Quantity);
        Assert.Same(recipe, selection.Choice.Primary);
    }
}
