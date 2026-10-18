using AdventureGuide.Data;
using AdventureGuide.State;

namespace AdventureGuide.Tests;

internal sealed class GateTestFacts : IGateFacts
{
    public HashSet<string> Quests { get; } = new(StringComparer.OrdinalIgnoreCase);
    public Dictionary<string, int> Inventory { get; } = new(StringComparer.OrdinalIgnoreCase);
    public HashSet<string> Keyring { get; } = new(StringComparer.OrdinalIgnoreCase);
    public Dictionary<string, string> Rooms { get; } = new(StringComparer.OrdinalIgnoreCase);
    public bool AccountClaimed { get; set; }
    public string? ReturnZone { get; set; }
    public UnityEngine.Vector3? ReturnLanding { get; set; }
    public int PlayerLevel { get; set; }

    public bool IsQuestCompleted(string questDbName) => Quests.Contains(questDbName);

    public bool ReadAccountState(string key) =>
        key == EncounterStateKeys.ReliquaryClaimed
            ? AccountClaimed
            : throw new ArgumentException($"Unknown account state {key}", nameof(key));

    public string? ReadCharacterZoneState(string key) =>
        key == EncounterStateKeys.ReturnZone
            ? ReturnZone
            : throw new ArgumentException($"Unknown character zone state {key}", nameof(key));

    public UnityEngine.Vector3? ReadCharacterPositionState(string key) =>
        key == EncounterStateKeys.ReturnLanding
            ? ReturnLanding
            : throw new ArgumentException($"Unknown character position state {key}", nameof(key));

    public int ItemCount(string itemStableKey) => Inventory.GetValueOrDefault(itemStableKey);

    public bool IsOnKeyring(string gameId) => Keyring.Contains(gameId);

    public string? StoredItemIn(string slot) => Rooms.GetValueOrDefault(slot);
}

public sealed class GateConditionsTests
{
    private const string Item = "item:key";

    [Theory]
    [InlineData("PlanarFern")]
    [InlineData("PlanarBrax")]
    [InlineData("PlanarVith")]
    [InlineData("PlanarSol")]
    [InlineData("Rune1")]
    [InlineData("Rune2")]
    [InlineData("Rune3")]
    [InlineData("Rune4")]
    [InlineData("Rune5")]
    [InlineData("Rune6")]
    public void Stored_portal_item_requires_exact_slot_and_tracks_replacement(string slot)
    {
        string instruction = slot.StartsWith("Rune", StringComparison.Ordinal)
            ? "Place Portal stone in a rune slot on your planning table."
            : "Place Portal stone in the planning-table slot for Test destination.";
        string json = """
            {"_version":9,"_encounters":{"encounter_placements":[],"encounter_conditions":[],"encounter_completions":[],"encounter_event_conditions":[]},"_source_facts":{},"_source_ranks":{},"_item_uses":{},"_quest_state_keys":{},"quests":[],"_conditions":[[[{"kind":"planning_slot_item","ref":"item:key","slot":"SLOT","instruction":INSTRUCTION}]]],
             "_zone_line_destination_contexts":{},
             "_gate_items":{"item:key":{"name":"Portal stone","game_id":"134379"}}}
            """.Replace("SLOT", slot).Replace(
            "INSTRUCTION",
            Newtonsoft.Json.JsonConvert.SerializeObject(instruction)
        );
        var facts = new GateTestFacts();
        facts.Inventory[Item] = 1;
        facts.Keyring.Add("134379");
        facts.Quests.Add("RELIQ-PLANE");
        var gates = new GateConditions(GuideData.Parse(json), facts);
        Assert.False(gates.IsAvailable(0));
        facts.Rooms["L1"] = Item;
        Assert.False(gates.IsAvailable(0));
        facts.Rooms[slot == "PlanarFern" ? "PlanarBrax" : "PlanarFern"] = Item;
        Assert.False(gates.IsAvailable(0));
        facts.Rooms[slot] = "item:wrong stone";
        Assert.False(gates.IsAvailable(0));
        facts.Rooms[slot] = Item;
        Assert.True(gates.IsAvailable(0));
        facts.Rooms[slot] = "item:replacement";
        Assert.False(gates.IsAvailable(0));
        facts.Rooms[slot] = Item;
        Assert.True(gates.IsAvailable(0));
        facts.Rooms.Remove(slot);
        Assert.False(gates.IsAvailable(0));
    }

    [Theory]
    [InlineData(null)]
    [InlineData("L1")]
    [InlineData("PlanarUnknown")]
    [InlineData("Rune7")]
    public void Stored_portal_item_rejects_unknown_or_room_slot(string? slot)
    {
        var atom = Atom(GateAtomKind.PlanningSlotItem);
        atom.Slot = slot;
        atom.Instruction = "Place Portal stone in a rune slot on your planning table.";
        Assert.Throws<InvalidDataException>(() =>
            Data([
                [
                    [atom],
                ],
            ])
        );
    }

    [Theory]
    [InlineData(null)]
    [InlineData("")]
    [InlineData(" ")]
    public void Stored_portal_item_rejects_missing_instruction(string? instruction)
    {
        string json = """
            {"_version":9,"_encounters":{"encounter_placements":[],"encounter_conditions":[],"encounter_completions":[],"encounter_event_conditions":[]},"_source_facts":{},"_source_ranks":{},"_item_uses":{},"_quest_state_keys":{},"quests":[],"_conditions":[[[{"kind":"planning_slot_item","ref":"item:key","slot":"Rune1","instruction":INSTRUCTION}]]],
             "_zone_line_destination_contexts":{},
             "_gate_items":{"item:key":{"name":"Portal stone","game_id":"2096280"}}}
            """.Replace("INSTRUCTION", Newtonsoft.Json.JsonConvert.SerializeObject(instruction));
        Assert.Throws<InvalidDataException>(() => GuideData.Parse(json));
    }

    [Fact]
    public void Stored_portal_item_rejects_absent_instruction_property()
    {
        const string json = """
            {"_version":9,"_encounters":{"encounter_placements":[],"encounter_conditions":[],"encounter_completions":[],"encounter_event_conditions":[]},"_source_facts":{},"_source_ranks":{},"_item_uses":{},"_quest_state_keys":{},"quests":[],"_conditions":[[[{"kind":"planning_slot_item","ref":"item:key","slot":"Rune1"}]]],
             "_zone_line_destination_contexts":{},
             "_gate_items":{"item:key":{"name":"Portal stone","game_id":"2096280"}}}
            """;
        Assert.Throws<InvalidDataException>(() => GuideData.Parse(json));
    }

    [Theory]
    [InlineData("Rune1")]
    [InlineData("Rune2")]
    [InlineData("Rune3")]
    [InlineData("Rune4")]
    [InlineData("Rune5")]
    [InlineData("Rune6")]
    public void Rune_alternatives_keep_slot_identity_but_explain_one_generated_action(string slot)
    {
        const string instruction = "Place Portal stone in a rune slot on your planning table.";
        var groups = FurnishingPolicy
            .RuneSlots.Select(rune => new List<GateAtom>
            {
                new()
                {
                    Kind = GateAtomKind.PlanningSlotItem,
                    Ref = Item,
                    Slot = rune,
                    Instruction = instruction,
                },
            })
            .ToList();
        var data = Data([groups]);
        var facts = new GateTestFacts();
        facts.Inventory[Item] = 1;
        facts.Keyring.Add("key-id");
        facts.Quests.Add("RELIQ-RUNE");
        facts.Rooms["PlanarFern"] = Item;
        facts.Rooms["L1"] = Item;
        var gates = new GateConditions(data, facts);
        Assert.Equal(6, data.Conditions[0].Count);
        Assert.Equal(FurnishingPolicy.RuneSlots, groups.Select(group => Assert.Single(group).Slot));
        Assert.False(gates.IsAvailable(0));
        Assert.Equal(instruction, gates.Describe(Assert.Single(gates.Explain(0))));
        facts.Rooms[slot] = "item:wrong";
        Assert.False(gates.IsAvailable(0));
        facts.Rooms[slot] = Item;
        Assert.True(gates.IsAvailable(0));
        Assert.Empty(gates.Explain(0));
        facts.Rooms[slot] = "item:replacement";
        Assert.False(gates.IsAvailable(0));
        facts.Rooms.Remove(slot);
        Assert.False(gates.IsAvailable(0));
        Assert.Equal(6, data.Conditions[0].Count);
    }

    [Fact]
    public void Dedicated_instruction_uses_generated_destination_text()
    {
        const string instruction = "Place Portal stone in the planning-table slot for Fernalla.";
        var atom = new GateAtom
        {
            Kind = GateAtomKind.PlanningSlotItem,
            Ref = Item,
            Slot = "PlanarFern",
            Instruction = instruction,
        };
        var gates = new GateConditions(
            Data([
                [
                    [atom],
                ],
            ]),
            new GateTestFacts()
        );
        Assert.Equal(instruction, gates.Describe(atom));
    }

    private static GateAtom Atom(GateAtomKind kind, string reference = Item) =>
        new() { Kind = kind, Ref = reference };

    private static GuideData Data(
        List<List<List<GateAtom>>> conditions,
        Dictionary<string, List<SpawnPoint>>? spawns = null
    ) =>
        GuideData.FromWrapper(
            new GuideWrapper
            {
                Version = GuideData.SchemaVersion,
                Encounters = TestData.EmptyEncounters(),
                Quests = [],
                Conditions = conditions,
                GateItems = new()
                {
                    [Item] = new GateItem { Name = "Test Key", GameId = "key-id" },
                },
                CharacterSpawns = spawns,
            }
        );

    [Theory]
    [InlineData(false, false, false)]
    [InlineData(true, false, true)]
    [InlineData(false, true, true)]
    [InlineData(true, true, true)]
    public void Key_gate_accepts_inventory_or_keyring(bool inventory, bool keyring, bool expected)
    {
        var data = Data([
            [
                [Atom(GateAtomKind.KeyHeld)],
            ],
        ]);
        var facts = new GateTestFacts();
        if (inventory)
            facts.Inventory[Item] = 1;
        if (keyring)
            facts.Keyring.Add("key-id");
        Assert.Equal(expected, new GateConditions(data, facts).IsAvailable(0));
    }

    [Fact]
    public void Item_gate_requires_positive_inventory_not_only_a_keyring_entry()
    {
        var data = Data([
            [
                [Atom(GateAtomKind.ItemHeld)],
            ],
        ]);
        var facts = new GateTestFacts();
        facts.Keyring.Add("key-id");
        var gates = new GateConditions(data, facts);
        Assert.False(gates.IsAvailable(0));
        facts.Inventory[Item] = 1;
        Assert.True(gates.IsAvailable(0));
        facts.Inventory[Item] = 0;
        Assert.False(gates.IsAvailable(0));
    }

    [Fact]
    public void Quest_not_done_inverts_completed_quest_state()
    {
        var data = Data([
            [
                [Atom(GateAtomKind.QuestNotDone, "QUEST")],
            ],
        ]);
        var facts = new GateTestFacts();
        var gates = new GateConditions(data, facts);
        Assert.True(gates.IsAvailable(0));
        facts.Quests.Add("QUEST");
        Assert.False(gates.IsAvailable(0));
    }

    [Fact]
    public void Advisory_encounter_is_explained_without_blocking_availability()
    {
        var advisory = Atom(GateAtomKind.EncounterWon, "encounter:boss");
        var gates = new GateConditions(
            Data([
                [
                    [advisory],
                ],
            ]),
            new GateTestFacts()
        );
        Assert.True(gates.Holds(advisory));
        Assert.True(gates.IsAvailable(0));
        Assert.Same(advisory, Assert.Single(gates.Explain(0)));
    }

    [Theory]
    [InlineData(null, 1, "character:raval", "Defeat Raval")]
    [InlineData(1, 1, "character:raval", "Defeat Raval")]
    [InlineData(9, 9, "character:stardust", "Defeat all 9 Stardust")]
    public void Defeat_quantity_is_read_from_wire_and_shown_without_blocking(
        int? quantity,
        int expected,
        string reference,
        string description
    )
    {
        string property = quantity.HasValue ? ",\"quantity\":" + quantity.Value : "";
        string json = """
            {"_version":9,"_zone_line_destination_contexts":{},"_encounters":{"encounter_placements":[],"encounter_conditions":[],"encounter_completions":[],"encounter_event_conditions":[]},"_source_facts":{},"_source_ranks":{},"_item_uses":{},"_quest_state_keys":{},"quests":[],
             "_conditions":[[[{"kind":"encounter_won","ref":"REFERENCE"QUANTITY}]]]}
            """.Replace("QUANTITY", property).Replace("REFERENCE", reference);
        var data = GuideData.Parse(json);
        var atom = Assert.Single(Assert.Single(Assert.Single(data.Conditions)));
        Assert.Equal(expected, atom.Quantity);
        var gates = new GateConditions(data, new GateTestFacts());
        Assert.True(gates.IsAvailable(0));
        Assert.Equal(description, gates.Describe(Assert.Single(gates.Explain(0))));
    }

    [Fact]
    public void Advisory_deduplication_preserves_distinct_defeat_counts()
    {
        var once = Atom(GateAtomKind.EncounterWon, "character:stardust");
        var repeated = Atom(GateAtomKind.EncounterWon, "character:stardust");
        repeated.Quantity = 9;
        var gates = new GateConditions(
            Data([
                [
                    [once],
                    [repeated],
                    [repeated],
                ],
            ]),
            new GateTestFacts()
        );
        var explained = gates.Explain(0);
        Assert.Equal(2, explained.Count);
        Assert.Contains(once, explained);
        Assert.Contains(repeated, explained);
    }

    [Theory]
    [InlineData(0)]
    [InlineData(-1)]
    public void Invalid_defeat_quantity_is_rejected(int quantity)
    {
        var atom = Atom(GateAtomKind.EncounterWon, "character:stardust");
        atom.Quantity = quantity;
        Assert.Throws<InvalidDataException>(() =>
            Data([
                [
                    [atom],
                ],
            ])
        );
    }

    [Fact]
    public void Missing_condition_is_ungated_empty_disjunction_is_false_and_empty_conjunction_is_true()
    {
        var gates = new GateConditions(
            Data([
                [],
                [
                    [],
                ],
            ]),
            new GateTestFacts()
        );
        Assert.True(gates.IsAvailable(null));
        Assert.Empty(gates.Explain(null));
        Assert.False(gates.IsAvailable(0));
        Assert.True(gates.IsAvailable(1));
    }

    [Fact]
    public void Future_availability_only_rejects_empty_conditions_and_completed_negative_quests()
    {
        var facts = new GateTestFacts();
        facts.Quests.Add("Done");
        var gates = new GateConditions(
            Data([
                [],
                [
                    [],
                ],
                [
                    [Atom(GateAtomKind.QuestNotDone, "Done")],
                ],
                [
                    [Atom(GateAtomKind.QuestNotDone, "Done")],
                    [Atom(GateAtomKind.KeyHeld)],
                ],
                [
                    [Atom(GateAtomKind.QuestDone, "NotDone"), Atom(GateAtomKind.ItemHeld)],
                ],
                [
                    [Atom(GateAtomKind.QuestNotDone, "NotDone")],
                ],
            ]),
            facts
        );

        Assert.True(gates.CanBecomeAvailable(null));
        Assert.False(gates.CanBecomeAvailable(0));
        Assert.True(gates.CanBecomeAvailable(1));
        Assert.False(gates.CanBecomeAvailable(2));
        Assert.True(gates.CanBecomeAvailable(3));
        Assert.True(gates.CanBecomeAvailable(4));
        Assert.True(gates.CanBecomeAvailable(5));
    }

    [Fact]
    public void Character_without_placements_is_ungated_and_any_available_placement_suffices()
    {
        var facts = new GateTestFacts();
        var gates = new GateConditions(
            Data(
                [
                    [
                        [Atom(GateAtomKind.QuestDone, "QUEST")],
                    ],
                ],
                new()
                {
                    ["character:empty"] = [],
                    ["character:gated"] = [new SpawnPoint { Condition = 0 }],
                    ["character:mixed"] = [new SpawnPoint { Condition = 0 }, new SpawnPoint()],
                }
            ),
            facts
        );
        Assert.True(gates.IsCharacterAvailable("character:unknown"));
        Assert.True(gates.IsCharacterAvailable("character:empty"));
        Assert.Empty(gates.ExplainCharacter("character:unknown"));
        Assert.False(gates.IsCharacterAvailable("character:gated"));
        Assert.True(gates.IsCharacterAvailable("character:mixed"));
        facts.Quests.Add("QUEST");
        Assert.True(gates.IsCharacterAvailable("character:gated"));
    }

    [Theory]
    [InlineData(false, false, false)]
    [InlineData(true, false, false)]
    [InlineData(false, true, false)]
    [InlineData(true, true, true)]
    public void Source_and_character_conditions_must_both_hold(
        bool sourceReady,
        bool characterReady,
        bool expected
    )
    {
        var facts = new GateTestFacts();
        if (sourceReady)
            facts.Quests.Add("SOURCE");
        if (characterReady)
            facts.Quests.Add("CHARACTER");
        var data = Data(
            [
                [
                    [Atom(GateAtomKind.QuestDone, "SOURCE")],
                ],
                [
                    [Atom(GateAtomKind.QuestDone, "CHARACTER")],
                ],
            ],
            new() { ["character:vendor"] = [new SpawnPoint { Condition = 1 }] }
        );
        var gates = new GateConditions(data, facts);
        Assert.Equal(
            expected,
            gates.IsSourceAvailable(
                new ItemSource { SourceKey = "character:vendor", Condition = 0 }
            )
        );
    }

    [Fact]
    public void Explanation_chooses_fewest_unmet_atoms_and_first_tie_retaining_advisories()
    {
        var first = Atom(GateAtomKind.QuestDone, "FIRST");
        var second = Atom(GateAtomKind.QuestDone, "SECOND");
        var advisory = Atom(GateAtomKind.EncounterWon, "encounter:boss");
        var facts = new GateTestFacts();
        var gates = new GateConditions(
            Data([
                [
                    [first, second],
                    [first, advisory],
                    [second],
                ],
            ]),
            facts
        );
        Assert.Equal(new[] { first, advisory }, gates.Explain(0));
        facts.Quests.Add("FIRST");
        Assert.Equal(new[] { advisory }, gates.Explain(0));
    }

    [Fact]
    public void Explanation_keeps_advisories_from_every_alternative_but_only_the_best_unmet_observables()
    {
        var first = Atom(GateAtomKind.QuestDone, "FIRST");
        var second = Atom(GateAtomKind.QuestDone, "SECOND");
        var third = Atom(GateAtomKind.QuestDone, "THIRD");
        var firstAdvisory = Atom(GateAtomKind.EncounterWon, "encounter:first");
        var secondAdvisory = Atom(GateAtomKind.EncounterWon, "encounter:second");
        var gates = new GateConditions(
            Data([
                [
                    [first, second, firstAdvisory],
                    [third, secondAdvisory],
                ],
            ]),
            new GateTestFacts()
        );

        var explanation = gates.Explain(0);
        Assert.Equal(3, explanation.Count);
        Assert.Contains(firstAdvisory, explanation);
        Assert.Contains(secondAdvisory, explanation);
        Assert.Contains(third, explanation);
        Assert.DoesNotContain(first, explanation);
        Assert.DoesNotContain(second, explanation);
    }

    [Theory]
    [InlineData("zone", -1)]
    [InlineData("zone", 1)]
    [InlineData("spawn", -1)]
    [InlineData("spawn", 1)]
    [InlineData("source", -1)]
    [InlineData("source", 1)]
    [InlineData("nested_source", -1)]
    [InlineData("nested_source", 1)]
    public void Loading_rejects_out_of_range_condition_references(string placement, int condition)
    {
        var wrapper = new GuideWrapper
        {
            Version = GuideData.SchemaVersion,
            Encounters = TestData.EmptyEncounters(),
            Quests = [],
            Conditions =
            [
                [
                    [],
                ],
            ],
        };
        switch (placement)
        {
            case "zone":
                wrapper.ZoneLines = [new ZoneLineEntry { Condition = condition }];
                break;
            case "spawn":
                wrapper.CharacterSpawns = new()
                {
                    ["character:test"] = [new SpawnPoint { Condition = condition }],
                };
                break;
            default:
                var source = new ItemSource { Condition = condition };
                wrapper.GateItems = new()
                {
                    [Item] = new GateItem
                    {
                        GameId = "key-id",
                        Sources =
                            placement == "nested_source"
                                ? [new ItemSource { Children = [source] }]
                                : [source],
                    },
                };
                break;
        }

        Assert.Throws<InvalidDataException>(() => GuideData.FromWrapper(wrapper));
    }

    [Theory]
    [InlineData(GateAtomKind.ItemHeld)]
    [InlineData(GateAtomKind.KeyHeld)]
    [InlineData(GateAtomKind.RoomFurnished)]
    public void Loading_rejects_item_atoms_missing_from_gate_items(GateAtomKind kind)
    {
        var wrapper = new GuideWrapper
        {
            Version = GuideData.SchemaVersion,
            Encounters = TestData.EmptyEncounters(),
            Quests = [],
            Conditions =
            [
                [
                    [
                        new GateAtom
                        {
                            Kind = kind,
                            Ref = "item:missing",
                            Slot = "L1",
                        },
                    ],
                ],
            ],
        };

        Assert.Throws<InvalidDataException>(() => GuideData.FromWrapper(wrapper));
    }

    private static GuideData ShippingData()
    {
        using var stream = typeof(GuideData).Assembly.GetManifestResourceStream(
            "AdventureGuide.quest-guide.json"
        );
        Assert.NotNull(stream);
        using var reader = new StreamReader(stream);
        return GuideData.Parse(reader.ReadToEnd());
    }

    [Fact]
    public void Duskenlight_to_Jaws_requires_the_candle_or_She_Sees_You()
    {
        var data = ShippingData();
        var line = Assert.Single(
            data.ZoneLines,
            line => line.Scene == "Duskenlight" && line.DestinationZoneKey == "zone:jaws"
        );
        Assert.NotNull(line.Condition);
        var groups = data.Conditions[line.Condition.Value];
        var candle = Assert.Single(
            groups.SelectMany(group => group),
            atom => atom.Kind == GateAtomKind.ItemHeld
        );
        Assert.Equal("item:hand - 100 - the nighthollow candle", candle.Ref);
        Assert.Contains(
            groups,
            group =>
                group.Count == 1
                && group[0].Kind == GateAtomKind.QuestDone
                && group[0].Ref == "JAWSSEEN"
        );
        var facts = new GateTestFacts();
        var gates = new GateConditions(data, facts);
        Assert.False(gates.IsAvailable(line.Condition));
        facts.Inventory[candle.Ref] = 1;
        Assert.True(gates.IsAvailable(line.Condition));
        facts.Inventory.Clear();
        facts.Quests.Add("JAWSSEEN");
        Assert.True(gates.IsAvailable(line.Condition));
    }

    [Fact]
    public void Bassle_requires_ANGLERRING()
    {
        var data = ShippingData();
        var facts = new GateTestFacts();
        var gates = new GateConditions(data, facts);
        const string bassle = "character:bassle wavebreak";
        Assert.False(gates.IsCharacterAvailable(bassle));
        Assert.Contains(
            gates.ExplainCharacter(bassle),
            atom => atom.Kind == GateAtomKind.QuestDone && atom.Ref == "ANGLERRING"
        );
        facts.Quests.Add("ANGLERRING");
        Assert.True(gates.IsCharacterAvailable(bassle));
    }

    [Fact]
    public void Shipping_room_atoms_require_the_exported_set_in_the_exported_slot()
    {
        var data = ShippingData();
        var roomAtoms = data
            .Conditions.SelectMany(groups => groups)
            .SelectMany(group => group)
            .Where(atom => atom.Kind == GateAtomKind.RoomFurnished)
            .ToList();
        Assert.NotEmpty(roomAtoms);
        foreach (var atom in roomAtoms)
        {
            var facts = new GateTestFacts();
            var gates = new GateConditions(data, facts);
            Assert.False(gates.Holds(atom));
            Assert.NotNull(atom.Slot);
            Assert.True(FurnishingPolicy.IsRoomSlot(atom.Slot));
            Assert.True(data.GateItems.ContainsKey(atom.Ref));
            facts.Rooms[atom.Slot] = atom.Ref;
            Assert.True(gates.Holds(atom));
        }
    }
}
