using AdventureGuide.Data;
using AdventureGuide.State;

namespace AdventureGuide.Tests;

public sealed class CanonicalSourceConditionsTests
{
    private static SourceCondition Condition(
        string predicate,
        string? reference = null,
        int gate = 0,
        int alternative = 0,
        int atom = 0,
        string phase = "availability"
    ) =>
        new()
        {
            GateKey = "same-provenance-label",
            GateIndex = gate,
            AlternativeIndex = alternative,
            AtomIndex = atom,
            Predicate = predicate,
            ReferenceStableKey = reference,
            Phase = phase,
        };

    private static GuideWrapper Wrapper(params SourceCondition[] conditions) =>
        new()
        {
            Version = GuideData.SchemaVersion,
            Encounters = TestData.EmptyEncounters(),
            Quests =
            [
                new()
                {
                    StableKey = "quest:test",
                    DBName = "Test",
                    DisplayName = "Test",
                    RequiredItems =
                    [
                        new()
                        {
                            ItemStableKey = "item:result",
                            ItemName = "Result",
                            Sources = [new() { AcquisitionKey = "source:test" }],
                        },
                    ],
                },
            ],
            Sources = new()
            {
                ["source:test"] = new()
                {
                    Type = "pickup",
                    Kind = "item_bag",
                    Name = "Bag",
                    ItemStableKey = "item:result",
                    Conditions = [.. conditions],
                },
            },
        };

    private static ItemSource Source(GuideData data) => data.All[0].RequiredItems![0].Sources![0];

    [Theory]
    [InlineData("availability")]
    [InlineData("source_initialization")]
    [InlineData("operation_input")]
    [InlineData("operation_outcome")]
    public void Public_conditions_are_evaluated_in_every_stored_phase(string phase)
    {
        var data = GuideData.FromWrapper(Wrapper(Condition("item_held", "item:key", phase: phase)));
        var facts = new GateTestFacts();
        var gates = new GateConditions(data, facts);
        Assert.False(gates.IsSourceAvailable(Source(data)));
        facts.Inventory["item:key"] = 1;
        Assert.True(gates.IsSourceAvailable(Source(data)));
        Assert.Single(Assert.Single(Assert.Single(gates.SourceRequirements(Source(data)))));
    }

    [Fact]
    public void Gate_and_alternative_indices_preserve_AND_OR_AND_without_provenance_grouping()
    {
        var data = GuideData.FromWrapper(
            Wrapper(
                Condition("item_held", "item:a"),
                Condition("item_held", "item:b", atom: 1),
                Condition("item_held", "item:c", alternative: 1),
                Condition("item_held", "item:d", gate: 1)
            )
        );
        var facts = new GateTestFacts();
        var gates = new GateConditions(data, facts);
        var source = Source(data);
        facts.Inventory["item:a"] = 1;
        facts.Inventory["item:d"] = 1;
        Assert.False(gates.IsSourceAvailable(source));
        facts.Inventory["item:b"] = 1;
        Assert.True(gates.IsSourceAvailable(source));
        facts.Inventory.Remove("item:a");
        facts.Inventory["item:c"] = 1;
        Assert.True(gates.IsSourceAvailable(source));
        facts.Inventory.Remove("item:d");
        Assert.False(gates.IsSourceAvailable(source));
    }

    [Fact]
    public void Shared_place_sets_expand_once_without_leaking_place_gates_or_path_children()
    {
        var wrapper = Wrapper();
        wrapper.Sources["source:test"].PlaceSetKey = "places:shared";
        wrapper.Sources["source:other"] = new()
        {
            Type = "auction_house",
            Kind = "auction_house",
            Name = "Auction House",
            ItemStableKey = "item:result",
            PlaceSetKey = "places:shared",
        };
        wrapper.PlaceSets["places:shared"] =
        [
            new()
            {
                PlaceKey = "place:locked",
                Relation = "fixed",
                Scene = "A",
                Zone = "First zone",
                X = 1,
                Y = 2,
                Z = 3,
                Conditions = [Condition("item_held", "item:key")],
            },
            new() { PlaceKey = "place:open", Relation = "unlocated" },
        ];
        var references = wrapper.Quests![0].RequiredItems![0].Sources!;
        references[0].Children = [new() { Type = "ingredient", Quantity = 2 }];
        references.Add(new() { AcquisitionKey = "source:other" });
        var data = GuideData.FromWrapper(wrapper);
        Assert.Equal(4, references.Count);
        Assert.Equal("First zone", references[0].Zone);
        Assert.Equal(1, references[0].CanonicalSpawn!.X);
        Assert.Same(references[0].CanonicalLocation, references[2].CanonicalLocation);
        Assert.Same(references[0].Children, references[1].Children);
        Assert.Null(references[2].Children);
        Assert.Equal("auction_house", references[2].Type);
        var facts = new GateTestFacts();
        var gates = new GateConditions(data, facts);
        Assert.False(gates.IsSourceAvailable(references[0]));
        Assert.True(gates.IsSourceAvailable(references[1]));
        Assert.False(gates.IsSourceAvailable(references[2]));
        facts.Inventory["item:key"] = 1;
        Assert.True(gates.IsSourceAvailable(references[0]));
        Assert.True(gates.IsSourceAvailable(references[2]));
    }

    [Fact]
    public void Public_JSON_resolves_references_in_quests_gate_items_and_nested_children()
    {
        const string json = """
            {"_version":10,"_encounters":{"encounter_placements":[],"encounter_conditions":[],"encounter_completions":[],"encounter_event_conditions":[]},
             "_sources":{"source:test":{"type":"auction_house","kind":"auction_house","name":"Auction House","item_stable_key":"item:result","place_set_key":"places:test","conditions":[]}},
             "_place_sets":{"places:test":[{"place_key":"place:test","relation":"fixed","scene":"A","zone":"A zone","marker_stable_key":"spawn:test","x":1,"y":2,"z":3,"conditions":[],"entry_zone_line_keys":[]}]},
             "_source_ranks":{"source:test":{"tier":2,"depth":3}},"_item_uses":{},"_quest_state_keys":{},"_zone_line_destination_contexts":{},
             "_gate_items":{"item:result":{"name":"Result","sources":[{"acquisition_key":"source:test"}]}},
             "quests":[{"stable_key":"quest:test","db_name":"Test","display_name":"Test","required_items":[{"item_stable_key":"item:result","item_name":"Result","sources":[{"type":"ingredient","children":[{"acquisition_key":"source:test"}]}]}],
              "steps":[{"order":1,"action":"obtain","description":"Obtain Result.","sources":[{"acquisition_key":"source:test"}]}]}]}
            """;
        var data = GuideData.Parse(json);
        var step = data.All[0].Steps![0].Sources![0];
        var nested = Source(data).Children![0];
        var gate = data.GateItems["item:result"].Sources![0];
        foreach (var source in new[] { step, nested, gate })
        {
            Assert.Equal("Auction House", source.Name);
            Assert.Equal("source:test|place:test", source.MakeSourceId());
            Assert.Equal("A zone", source.Zone);
            Assert.Equal(2, source.Rank!.Tier);
            Assert.Same(step.CanonicalLocation, source.CanonicalLocation);
        }
    }

    [Theory]
    [InlineData(9, false)]
    [InlineData(10, true)]
    [InlineData(20, false)]
    public void Player_level_bounds_keep_exclusive_endpoints(int level, bool available)
    {
        var condition = Condition("actor_level");
        condition.Actor = "player";
        condition.Minimum = 10;
        condition.Maximum = 20;
        condition.MaximumInclusive = false;
        var data = GuideData.FromWrapper(Wrapper(condition));
        Assert.Equal(
            available,
            new GateConditions(data, new GateTestFacts { PlayerLevel = level }).IsSourceAvailable(
                Source(data)
            )
        );
    }

    [Theory]
    [InlineData(5, false)]
    [InlineData(6, true)]
    [InlineData(21, true)]
    [InlineData(22, false)]
    public void Public_fishing_time_conditions_use_the_live_operation_window(
        int hour,
        bool available
    )
    {
        var condition = Condition("time_of_day", phase: "operation_input");
        condition.Value = "day";
        var wrapper = Wrapper(condition);
        var presentation = wrapper.Sources["source:test"];
        presentation.Type = presentation.Kind = "fishing";
        presentation.Chance = 5;
        presentation.ChanceMax = 7;
        presentation.DayChance = 5;
        presentation.NightChance = 0;
        presentation.TimeRestriction = "day";
        var data = GuideData.FromWrapper(wrapper);
        var source = Source(data);
        Assert.Equal(5, source.Chance);
        Assert.Equal(7, source.ChanceMax);
        Assert.Equal(available ? 5d : 0d, ItemSourcePolicy.FishingChance(source, hour));
        Assert.Equal(
            available,
            new GateConditions(data, new GateTestFacts { Hour = hour }).IsSourceAvailable(source)
        );
        Assert.Null(source.CanonicalSpawn);
        Assert.Null(source.Scene);
    }

    [Fact]
    public void Missing_public_source_or_shared_place_set_is_rejected_at_load()
    {
        var wrapper = Wrapper();
        wrapper.Quests![0].RequiredItems![0].Sources![0].AcquisitionKey = "missing";
        Assert.Throws<InvalidDataException>(() => GuideData.FromWrapper(wrapper));
        wrapper = Wrapper();
        wrapper.Sources["source:test"].PlaceSetKey = "missing";
        Assert.Throws<InvalidDataException>(() => GuideData.FromWrapper(wrapper));
    }

    [Fact]
    public void Global_fishing_remains_unlocated_and_preserves_public_odds_quantity_and_quality()
    {
        var quality = Condition("quality", phase: "operation_outcome");
        quality.Value = "rare";
        var wrapper = Wrapper(quality);
        var presentation = wrapper.Sources["source:test"];
        presentation.Type = presentation.Kind = "fishing";
        presentation.Name = "Any water";
        presentation.SourceKey = "water:Other:1:2:3";
        presentation.Chance = presentation.DayChance = presentation.NightChance = 7;
        presentation.Quantity = 2;
        presentation.OutputQuality = "rare";
        var data = GuideData.FromWrapper(wrapper);
        var source = Source(data);
        Assert.Equal("Any water", source.Name);
        Assert.Equal(7, source.Chance);
        Assert.Equal(2, source.Quantity);
        Assert.Equal("rare", source.OutputQuality);
        Assert.Null(source.LocationKey);
        Assert.Null(source.CanonicalSpawn);
        Assert.Null(source.Scene);
        Assert.False(AdventureGuide.Navigation.PositionedSource.TryCreate(source, out _));
        Assert.True(new GateConditions(data, new GateTestFacts()).IsSourceAvailable(source));
    }

    [Fact]
    public void Duplicate_public_atom_indices_are_rejected_without_using_phase_as_identity()
    {
        var wrapper = Wrapper(
            Condition("item_held", "item:a"),
            Condition("item_held", "item:b", phase: "operation_input")
        );
        Assert.Throws<InvalidDataException>(() => GuideData.FromWrapper(wrapper));
    }

    [Fact]
    public void Possible_treasure_places_keep_existing_chest_presentation_and_navigation_identity()
    {
        var wrapper = Wrapper();
        var source = wrapper.Sources["source:test"];
        source.Type = "drop";
        source.Kind = "character_drop";
        source.Chance = 5;
        source.PlaceSetKey = "places:treasure";
        wrapper.PlaceSets["places:treasure"] =
        [
            new()
            {
                PlaceKey = "place:treasure",
                Relation = "possible_treasure",
                Scene = "A",
                PlayerLevelMin = 10,
                PlayerLevelMax = 20,
            },
        ];
        var resolved = Source(GuideData.FromWrapper(wrapper));
        Assert.Equal("treasure_chest", resolved.Type);
        Assert.Equal("Treasure map chest", resolved.Name);
        Assert.Equal("Read a Treasure Map and dig at the marked spot.", resolved.Instruction);
        Assert.Equal(10, resolved.Level);
        Assert.Equal(20, resolved.LevelMax);
        Assert.Equal(5, resolved.Chance);
        Assert.Equal("treasure:dig-site", resolved.MakeSourceId());
        Assert.Null(resolved.CanonicalSpawn);
    }

    [Theory]
    [InlineData(null)]
    [InlineData("other")]
    public void Operation_inputs_cannot_bind_to_another_outcome(string? outcome)
    {
        var wrapper = Wrapper();
        wrapper.Quests![0].RequiredItems![0].Sources![0].OperationUseKeys = ["input"];
        wrapper.ItemUses["input"] = new()
        {
            UseKey = "input",
            ItemStableKey = "item:material",
            OutcomeKey = outcome,
        };
        Assert.Throws<InvalidDataException>(() => GuideData.FromWrapper(wrapper));
    }

    [Theory]
    [InlineData(null, 1)]
    [InlineData(9.0, 9)]
    public void Public_encounter_guidance_keeps_defeat_quantities(double? count, int expected)
    {
        var condition = Condition("encounter_won", "character:stardust");
        condition.Minimum = count;
        var data = GuideData.FromWrapper(Wrapper(condition));
        var gates = new GateConditions(data, new GateTestFacts());
        var atom = Assert.Single(
            Assert.Single(Assert.Single(gates.SourceRequirements(Source(data))))
        );
        Assert.Equal(expected, atom.Quantity);
        Assert.True(gates.IsSourceAvailable(Source(data)));
    }

    [Theory]
    [InlineData(0)]
    [InlineData(-1)]
    [InlineData(1.5)]
    public void Defeat_quantities_must_be_positive_integers(double count)
    {
        var condition = Condition("encounter_won", "character:stardust");
        condition.Minimum = count;
        Assert.Throws<InvalidDataException>(() => GuideData.FromWrapper(Wrapper(condition)));
    }

    [Fact]
    public void Repeated_public_availability_checks_do_not_allocate()
    {
        var data = GuideData.FromWrapper(Wrapper(Condition("item_held", "item:key")));
        var facts = new GateTestFacts();
        facts.Inventory["item:key"] = 1;
        var gates = new GateConditions(data, facts);
        var source = Source(data);
        Assert.True(gates.IsSourceAvailable(source));
        long before = GC.GetAllocatedBytesForCurrentThread();
        bool available = true;
        for (int i = 0; i < 1000; i++)
            available &= gates.IsSourceAvailable(source);
        long allocated = GC.GetAllocatedBytesForCurrentThread() - before;
        Assert.True(available);
        Assert.Equal(0, allocated);
    }
}
