using AdventureGuide.Data;
using AdventureGuide.Navigation;
using AdventureGuide.State;

namespace AdventureGuide.Tests;

public sealed class RequirementResolverTests
{
    [Fact]
    public void Null_variant_requirements_remain_ordinary_and_requirements()
    {
        var wrapper = TestData.NativeRequirements(("item:a", null, [1]), ("item:b", null, [3]));
        var (data, quest, state) = RequirementState(wrapper, ("item:a", 1), ("item:b", 1));

        Assert.Equal(1, StepProgress.GetCurrentStepIndex(quest, state, data));
        Assert.False(StepProgress.HasRequiredItems(quest, state.CountItemDelegate));
    }

    [Theory]
    [InlineData(0, 0)]
    [InlineData(1, 0)]
    [InlineData(3, 0)]
    [InlineData(4, 1)]
    public void Repeated_native_slots_require_their_combined_inventory_quantity(
        int inventory,
        int current
    )
    {
        var wrapper = TestData.NativeRequirements(("item:runner", null, [1, 3]));
        var (data, quest, state) = RequirementState(wrapper, ("item:runner", inventory));

        Assert.Equal(current, StepProgress.GetCurrentStepIndex(quest, state, data));
        Assert.Equal(inventory >= 4, StepProgress.HasRequiredItems(quest, state.CountItemDelegate));
    }

    [Theory]
    [InlineData(0, 0, 0)]
    [InlineData(1, 0, 1)]
    [InlineData(0, 1, 0)]
    [InlineData(1, 1, 2)]
    public void All_distinct_items_in_a_native_bundle_are_required(int a, int b, int current)
    {
        var wrapper = TestData.NativeRequirements(("item:a", "A", [1]), ("item:b", "A", [1]));
        var (data, quest, state) = RequirementState(wrapper, ("item:a", a), ("item:b", b));

        Assert.Equal(current, StepProgress.GetCurrentStepIndex(quest, state, data));
        Assert.Equal(
            a == 1 && b == 1,
            StepProgress.HasRequiredItems(quest, state.CountItemDelegate)
        );
    }

    [Theory]
    [InlineData(0, 0, 0)]
    [InlineData(1, 0, 2)]
    [InlineData(0, 1, 2)]
    public void A_complete_single_slot_variant_satisfies_the_native_alternatives(
        int a,
        int b,
        int current
    )
    {
        var wrapper = TestData.NativeRequirements(("item:a", "A", [1]), ("item:b", "B", [1]));
        var (data, quest, state) = RequirementState(wrapper, ("item:a", a), ("item:b", b));

        Assert.Equal(current, StepProgress.GetCurrentStepIndex(quest, state, data));
        Assert.Equal(
            a == 1 || b == 1,
            StepProgress.HasRequiredItems(quest, state.CountItemDelegate)
        );
        Assert.Equal(a == 1, StepProgress.IsStepComplete(quest.Steps![0], state, data));
    }

    [Theory]
    [InlineData(1, 1, 0, 0, 4)]
    [InlineData(0, 0, 1, 1, 4)]
    [InlineData(1, 0, 0, 1, 1)]
    [InlineData(0, 1, 1, 0, 0)]
    [InlineData(0, 0, 0, 0, 0)]
    public void Native_multi_slot_alternatives_cannot_mix_partial_bundles(
        int a,
        int b,
        int c,
        int d,
        int current
    )
    {
        var wrapper = TestData.NativeRequirements(
            ("item:a", "A", [1]),
            ("item:b", "A", [1]),
            ("item:c", "B", [1]),
            ("item:d", "B", [1])
        );
        var (data, quest, state) = RequirementState(
            wrapper,
            ("item:a", a),
            ("item:b", b),
            ("item:c", c),
            ("item:d", d)
        );

        Assert.Equal(current, StepProgress.GetCurrentStepIndex(quest, state, data));
        Assert.Equal(current == 4, StepProgress.HasRequiredItems(quest, state.CountItemDelegate));
        Assert.Equal(a == 1, StepProgress.IsStepComplete(quest.Steps![0], state, data));
    }

    [Theory]
    [InlineData(0, 0)]
    [InlineData(1, 2)]
    [InlineData(3, 2)]
    [InlineData(4, 2)]
    public void Repeated_items_are_never_summed_across_native_variants(int count, int current)
    {
        var wrapper = TestData.NativeRequirements(
            ("item:runner", "A", [1]),
            ("item:runner", "B", [3])
        );
        var (data, quest, state) = RequirementState(wrapper, ("item:runner", count));

        Assert.Equal(current, StepProgress.GetCurrentStepIndex(quest, state, data));
    }

    [Fact]
    public void Same_item_in_different_native_variants_uses_its_own_sources()
    {
        var wrapper = TestData.NativeRequirements(
            ("item:runner", "A", [1]),
            ("item:runner", "B", [3])
        );
        var quest = wrapper.Quests![0];
        var first = new ItemSource { Type = "drop", SourceKey = "character:first" };
        var second = new ItemSource { Type = "drop", SourceKey = "character:second" };
        quest.RequiredItems![0].Sources = [first];
        quest.RequiredItems[1].Sources = [second];
        var firstSpawn = new SpawnPoint { Scene = "A", X = 10 };
        var secondSpawn = new SpawnPoint { Scene = "A", X = 20 };
        wrapper.CharacterSpawns = new()
        {
            ["character:first"] = [firstSpawn],
            ["character:second"] = [secondSpawn],
        };
        wrapper.ZoneLookup = new()
        {
            ["A"] = new ZoneInfo { StableKey = "zone:a", DisplayName = "A" },
        };
        foreach (var (source, spawn) in new[] { (first, firstSpawn), (second, secondSpawn) })
        {
            source.AcquisitionKey = "acquisition:" + source.SourceKey;
            source.LocationKey = "location:" + source.SourceKey;
            wrapper.SourceFacts.Add(
                source.AcquisitionKey,
                new SourceFact
                {
                    AcquisitionKey = source.AcquisitionKey,
                    ItemStableKey = "item:runner",
                    Kind = "character_drop",
                    SourceStableKey = source.SourceKey,
                    SourceCopyStableKey = source.SourceKey,
                    PlayerAccessState = "verified_player",
                    ProbabilityKind = "unknown",
                    ProbabilityStage = "final_acquisition",
                    QuantityKind = "unknown",
                    Locations =
                    [
                        new SourceLocation
                        {
                            LocationKey = source.LocationKey,
                            Relation = "spawn",
                            Scene = spawn.Scene,
                            X = spawn.X,
                            Y = spawn.Y,
                            Z = spawn.Z,
                            SourceCopyStableKey = source.SourceKey,
                        },
                    ],
                }
            );
        }
        var data = GuideData.FromWrapper(wrapper);
        var resolver = Resolver(data);

        Assert.Equal(10, resolver.Resolve(quest, quest.Steps![0], "A").SelectedSpawn?.X);
        Assert.Equal(20, resolver.Resolve(quest, quest.Steps[1], "A").SelectedSpawn?.X);

        // Reading or acquiring the item does not select a native turn-in variant.
        var readStep = new QuestStep
        {
            Action = "read",
            TargetType = "item",
            TargetKey = "item:runner",
        };
        Assert.Equal(10, resolver.Resolve(quest, readStep, "A").SelectedSpawn?.X);
        quest.Acquisition =
        [
            new AcquisitionSource { Method = "item_read", SourceStableKey = "item:runner" },
        ];
        var acquisitionStep = resolver.BuildAcquisitionStep(quest);
        Assert.NotNull(acquisitionStep);
        Assert.Equal(10, resolver.Resolve(quest, acquisitionStep, "A").SelectedSpawn?.X);
        Assert.Null(
            ItemSourcePolicy.SourcesFor(
                quest,
                new QuestStep { TargetKey = "item:runner", RequirementVariant = "missing" }
            )
        );
        Assert.Null(
            ItemSourcePolicy.SourcesFor(
                quest,
                new QuestStep
                {
                    TargetKey = "item:wrong",
                    TargetName = "item:runner",
                    RequirementVariant = "A",
                }
            )
        );
    }

    [Fact]
    public void Authored_or_groups_keep_their_original_alternative_semantics()
    {
        var quest = Quest(
            "authored",
            new QuestStep
            {
                Order = 1,
                Action = "collect",
                Description = "Collect item a.",
                TargetKey = "item:a",
                Quantity = 1,
                OrGroup = "authored",
            }
        );
        quest.Steps!.AddRange([
            new QuestStep
            {
                Order = 2,
                Action = "collect",
                Description = "Collect item b.",
                TargetKey = "item:b",
                Quantity = 1,
                OrGroup = "authored",
            },
            new QuestStep
            {
                Order = 3,
                Action = "turn_in",
                Description = "Turn in the requirements.",
            },
        ]);
        var wrapper = new GuideWrapper
        {
            Version = GuideData.SchemaVersion,
            Encounters = TestData.EmptyEncounters(),
            Quests = [quest],
        };
        var (data, _, state) = RequirementState(wrapper, ("item:b", 1));

        Assert.Equal(2, StepProgress.GetCurrentStepIndex(quest, state, data));
        Assert.Empty(state.ActiveQuests);
        Assert.Empty(state.CompletedQuests);
    }

    private static (GuideData Data, QuestEntry Quest, QuestStateTracker State) RequirementState(
        GuideWrapper wrapper,
        params (string Item, int Count)[] inventory
    )
    {
        var data = GuideData.FromWrapper(wrapper);
        var snapshot = new RequirementSnapshot();
        foreach (var (item, count) in inventory)
            snapshot.Inventory[item] = count;
        var state = new QuestStateTracker(data, snapshot);
        state.SyncFromGameData();
        return (data, wrapper.Quests![0], state);
    }

    private sealed class RequirementSnapshot : IQuestGameState
    {
        public Dictionary<string, int> Inventory { get; } = new(StringComparer.OrdinalIgnoreCase);

        public void CopyActiveQuestsTo(HashSet<string> destination) { }

        public void CopyCompletedQuestsTo(HashSet<string> destination) { }

        public void CopyInventoryCountsTo(Dictionary<string, int> destination)
        {
            foreach (var pair in Inventory)
                destination.Add(pair.Key, pair.Value);
        }

        public bool ReadAccountState(string key) => false;

        public string? ReadCharacterZoneState(string key) => null;

        public UnityEngine.Vector3? ReadCharacterPositionState(string key) => null;

        public int PlayerLevel => 1;
    }

    private static QuestEntry Quest(string name, QuestStep step) =>
        new()
        {
            StableKey = "quest:" + name,
            DBName = name,
            DisplayName = name,
            Steps = [step],
        };

    private static QuestStep Character(string key) =>
        new()
        {
            Order = 1,
            Action = "talk",
            TargetType = "character",
            TargetKey = key,
            TargetName = key,
            Description = "Talk to " + key,
        };

    private static GateAtom Atom(GateAtomKind kind, string reference) =>
        new() { Kind = kind, Ref = reference };

    private static GuideData Data(
        List<List<List<GateAtom>>> conditions,
        Dictionary<string, List<SpawnPoint>> spawns,
        List<QuestEntry>? quests = null,
        Dictionary<string, GateItem>? items = null,
        List<ZoneLineEntry>? lines = null
    ) =>
        GuideData.FromWrapper(
            new GuideWrapper
            {
                Version = GuideData.SchemaVersion,
                Encounters = TestData.EmptyEncounters(),
                Quests = quests ?? [],
                Conditions = conditions,
                CharacterSpawns = spawns,
                GateItems = items,
                ZoneLines = lines,
                ZoneLookup = new()
                {
                    ["A"] = new ZoneInfo { StableKey = "zone:a", DisplayName = "A" },
                    ["B"] = new ZoneInfo { StableKey = "zone:b", DisplayName = "B" },
                    ["C"] = new ZoneInfo { StableKey = "zone:c", DisplayName = "C" },
                },
            }
        );

    private static RequirementResolver Resolver(GuideData data, GateTestFacts? facts = null)
    {
        var gates = new GateConditions(data, facts ?? new GateTestFacts());
        return new RequirementResolver(
            data,
            gates,
            new ZoneGraph(data, gates),
            quest => quest.Steps?.FirstOrDefault()
        );
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
    public void Lighthouse_target_routes_to_real_key_source_and_keyring_restores_target()
    {
        var data = ShippingData();
        var key = data.GateItems.Single(item =>
            item.Value.Name == "Stowaway's Step Lighthouse Key"
        );
        var target = data.CharacterSpawns.Single(pair =>
            pair.Key.StartsWith("character:lighthouse demon:", StringComparison.Ordinal)
        );
        var step = Character(target.Key);
        step.TargetName = "Occuphage";
        var quest = Quest("Lighthouse scenario", step);
        var facts = new GateTestFacts();
        var resolver = Resolver(data, facts);

        var result = resolver.Resolve(quest, step, "Stowaway");

        Assert.True(result.CanNavigate, result.Message);
        Assert.Equal(key.Key, result.Step.TargetKey);
        Assert.All(result.Step.Sources!, source => Assert.Equal("Garrey Ambrose", source.Name));
        Assert.All(result.AvailableSpawns!, spawn => Assert.Equal("Stowaway", spawn.Scene));
        facts.Keyring.Add(key.Value.GameId);
        var opened = resolver.Resolve(quest, step, "Stowaway");
        Assert.True(opened.CanNavigate, opened.Message);
        Assert.Same(step, opened.Step);
        Assert.Empty(opened.Chain);
    }

    [Fact]
    public void Lighthouse_placement_from_Salted_Strand_uses_Stowaway_then_exact_lighthouse_entry()
    {
        var data = ShippingData();
        var key = data.GateItems.Single(item =>
            item.Value.Name == "Stowaway's Step Lighthouse Key"
        );
        var target = data.CharacterSpawns.Single(pair =>
            pair.Key.StartsWith("character:lighthouse demon:", StringComparison.Ordinal)
        );
        var spawn = Assert.Single(target.Value);
        ZoneLineEntry StowawayLine(string key) =>
            data.ZoneLines.Single(line => line.StableKey == "zoneline:stowaway:tutorial:" + key);
        var lighthouse = StowawayLine("808.08:14.08:592.64");
        var beach = StowawayLine("407.55:10.20:312.47");
        var cliff = StowawayLine("809.72:19.36:645.26");
        var step = Character(target.Key);
        var quest = Quest("Lighthouse scenario", step);
        var facts = new GateTestFacts();
        facts.Quests.Add("MEETBASSLE");
        facts.Quests.Add("ANGLERRING");
        facts.Keyring.Add(key.Value.GameId);
        var gates = new GateConditions(data, facts);
        var graph = new ZoneGraph(data, gates);
        var resolver = new RequirementResolver(
            data,
            gates,
            graph,
            entry => entry.Steps?.FirstOrDefault()
        );

        var result = resolver.Resolve(quest, step, "SaltedStrand");
        var approach = graph.GetPlacementRoute(spawn, "SaltedStrand");

        Assert.True(result.CanNavigate, result.Message);
        Assert.Same(spawn, result.SelectedSpawn);
        Assert.Same(lighthouse, result.EntryLine);
        Assert.NotNull(approach);
        Assert.Equal(new[] { "SaltedStrand", "Stowaway" }, approach.Value.Route!.Path);
        Assert.Equal("zone:stowaway", approach.Value.Route.NextHopZoneKey);
        Assert.Same(lighthouse, approach.Value.EntryLine);

        var atEntry = graph.GetPlacementRoute(spawn, "Stowaway");
        Assert.NotNull(atEntry);
        Assert.Null(atEntry.Value.Route);
        Assert.Same(lighthouse, atEntry.Value.EntryLine);
        Assert.NotSame(beach, atEntry.Value.EntryLine);
        Assert.NotSame(cliff, atEntry.Value.EntryLine);

        var pinnedBeach = resolver.Resolve(quest, step, "Stowaway", beach);
        Assert.True(pinnedBeach.CanNavigate, pinnedBeach.Message);
        Assert.Same(lighthouse, pinnedBeach.EntryLine);

        facts.Keyring.Clear();
        graph.Rebuild();
        var missingKey = resolver.Resolve(quest, step, "SaltedStrand");
        Assert.True(missingKey.CanNavigate, missingKey.Message);
        Assert.Equal(key.Key, missingKey.Step.TargetKey);
        Assert.All(missingKey.Step.Sources!, source => Assert.Equal("Garrey Ambrose", source.Name));
        Assert.All(missingKey.AvailableSpawns!, spawn => Assert.Equal("Stowaway", spawn.Scene));
        Assert.Null(missingKey.EntryLine);
    }

    [Fact]
    public void Shivering_Step_reaches_Hidden_Hills_through_Stowaway_not_its_disabled_exit()
    {
        // A Way To Erenshor shows the Shivering Step exit to Hidden Hills, whose component stays disabled.
        var data = ShippingData();
        var facts = new GateTestFacts();
        facts.Quests.Add("A Way To Erenshor");
        var graph = new ZoneGraph(data, new GateConditions(data, facts));

        Assert.Equal(
            new[] { "ShiveringStep", "Stowaway", "Hidden" },
            graph.FindRoute("ShiveringStep", "Hidden")!.Path
        );
    }

    [Fact]
    public void Jaws_route_names_real_alternatives_and_chooses_nearest_first_requirement()
    {
        var data = ShippingData();
        var quest = data.GetByDBName("JAWSENTRY")!;
        var travelStep = new QuestStep
        {
            Order = 1,
            Action = "travel",
            Description = "Travel to Jaws of Sivakaya.",
            TargetType = "zone",
            TargetKey = "zone:jaws",
            TargetName = "Jaws of Sivakaya",
            ZoneName = "Jaws of Sivakaya",
        };
        var gates = new GateConditions(data, new GateTestFacts());
        var graph = new ZoneGraph(data, gates);
        var result = new RequirementResolver(
            data,
            gates,
            graph,
            entry => entry.Steps?.FirstOrDefault()
        ).Resolve(quest, travelStep, "Duskenlight");

        Assert.True(result.CanNavigate, result.Message);
        Assert.Contains(result.Chain, link => link.Alternatives.Count > 0);
        Assert.Contains("Nighthollow Candle", result.DisplayText);
        Assert.Contains("She Sees You", result.DisplayText);
        Assert.DoesNotContain(result.Chain, link => link.Atom?.Kind == GateAtomKind.QuestNotDone);
    }

    [Fact]
    public void Meet_the_Fisherman_follows_Anglers_Ring_to_missing_crafting_materials()
    {
        var data = ShippingData();
        var meet = data.GetByDBName("MEETBASSLE")!;
        var ring = data.GetByDBName("ANGLERRING")!;
        Assert.Null(ring.Acquisition);
        var result = Resolver(data).Resolve(meet, meet.Steps![0], "AzynthiClear");

        Assert.True(result.CanNavigate, result.Message);
        Assert.Same(ring, result.Quest);
        Assert.Contains(
            ring.RequiredItems![0].Sources!.Single(source => source.Type == "crafting").Children!,
            input => input.ItemStableKey == result.Step.TargetKey
        );
    }

    [Fact]
    public void Acquisition_sources_are_used_when_a_quest_has_no_steps()
    {
        var required = new QuestEntry
        {
            StableKey = "quest:required",
            DBName = "Required",
            DisplayName = "Required Quest",
            Acquisition =
            [
                new AcquisitionSource
                {
                    Method = "dialog",
                    SourceName = "Quest Giver",
                    SourceStableKey = "giver",
                },
            ],
        };
        var original = Character("target");
        var data = Data(
            [
                [
                    [Atom(GateAtomKind.QuestDone, "Required")],
                ],
            ],
            new()
            {
                ["target"] = [new SpawnPoint { Scene = "A", Condition = 0 }],
                ["giver"] = [new SpawnPoint { Scene = "A" }],
            },
            quests: [required]
        );
        var gates = new GateConditions(data, new GateTestFacts());
        RequirementResolver? resolver = null;
        resolver = new RequirementResolver(
            data,
            gates,
            new ZoneGraph(data, gates),
            quest => resolver!.BuildAcquisitionStep(quest) ?? quest.Steps?.FirstOrDefault()
        );
        var result = resolver.Resolve(Quest("Original", original), original, "A");

        Assert.True(result.CanNavigate, result.Message);
        Assert.Same(required, result.Quest);
        Assert.Equal("giver", Assert.Single(result.Step.Sources!).SourceKey);
    }

    [Theory]
    [InlineData(
        GateAtomKind.KeyHeld,
        "Ghostly Key",
        "No reachable source is known for Ghostly Key."
    )]
    [InlineData(
        GateAtomKind.QuestDone,
        "Missing Quest",
        "Missing Quest cannot be started from a known source."
    )]
    public void Missing_requirement_messages_use_bare_names(
        GateAtomKind kind,
        string name,
        string message
    )
    {
        var step = Character("target");
        var data = Data(
            [
                [
                    [Atom(kind, "missing")],
                ],
            ],
            new() { ["target"] = [new SpawnPoint { Scene = "A", Condition = 0 }] },
            quests:
            [
                new QuestEntry
                {
                    StableKey = "quest:missing",
                    DBName = "missing",
                    DisplayName = name,
                },
            ],
            items: new() { ["missing"] = new GateItem { Name = name } }
        );
        var result = Resolver(data).Resolve(Quest("Original", step), step, "A");

        Assert.False(result.CanNavigate);
        Assert.Equal(message, result.Message);
    }

    [Fact]
    public void Two_hop_item_requirement_chain_keeps_original_source_nodes()
    {
        var step = Character("target");
        var quest = Quest("Original", step);
        var first = new ItemSource
        {
            Type = "drop",
            SourceKey = "first",
            Name = "First",
            Condition = 1,
        };
        var second = new ItemSource
        {
            Type = "drop",
            SourceKey = "second",
            Name = "Second",
        };
        var data = Data(
            [
                [
                    [Atom(GateAtomKind.KeyHeld, "item:first")],
                ],
                [
                    [Atom(GateAtomKind.ItemHeld, "item:second")],
                ],
            ],
            new()
            {
                ["target"] = [new SpawnPoint { Scene = "A", Condition = 0 }],
                ["first"] = [new SpawnPoint { Scene = "A" }],
                ["second"] = [new SpawnPoint { Scene = "A" }],
            },
            items: new()
            {
                ["item:first"] = new GateItem
                {
                    Name = "First key",
                    GameId = "1",
                    Sources = [first],
                },
                ["item:second"] = new GateItem
                {
                    Name = "Second item",
                    GameId = "2",
                    Sources = [second],
                },
            }
        );

        var result = Resolver(data).Resolve(quest, step, "A");

        Assert.True(result.CanNavigate, result.Message);
        Assert.Equal("item:second", result.Step.TargetKey);
        Assert.Same(second, Assert.Single(result.Step.Sources!));
        Assert.Equal(
            new[] { "item:first", "item:second" },
            result.Chain.Where(link => link.Atom != null).Select(link => link.Atom!.Ref)
        );
    }

    [Fact]
    public void Gated_later_route_hop_redirects_before_entering_the_open_first_hop()
    {
        var step = Character("target");
        var keySource = new ItemSource
        {
            Type = "pickup",
            SourceKey = "itembag:a:1:2:3",
            Scene = "A",
        };
        var data = Data(
            [
                [
                    [Atom(GateAtomKind.KeyHeld, "item:key")],
                ],
            ],
            new() { ["target"] = [new SpawnPoint { Scene = "C" }] },
            items: new()
            {
                ["item:key"] = new GateItem
                {
                    Name = "Route Key",
                    GameId = "1",
                    Sources = [keySource],
                },
            },
            lines:
            [
                new ZoneLineEntry { Scene = "A", DestinationZoneKey = "zone:b" },
                new ZoneLineEntry
                {
                    Scene = "B",
                    DestinationZoneKey = "zone:c",
                    Condition = 0,
                },
            ]
        );

        var result = Resolver(data).Resolve(Quest("Original", step), step, "A");

        Assert.True(result.CanNavigate, result.Message);
        Assert.Equal("item:key", result.Step.TargetKey);
        Assert.Contains("Route Key", result.DisplayText);
    }

    [Fact]
    public void Equal_groups_choose_nearest_requirement_and_name_other_group()
    {
        var step = Character("target");
        var farStep = Character("far");
        var nearStep = Character("near");
        var data = Data(
            [
                [
                    [Atom(GateAtomKind.QuestDone, "Far")],
                    [Atom(GateAtomKind.QuestDone, "Near")],
                ],
            ],
            new()
            {
                ["target"] = [new SpawnPoint { Scene = "A", Condition = 0 }],
                ["far"] = [new SpawnPoint { Scene = "B" }],
                ["near"] = [new SpawnPoint { Scene = "A" }],
            },
            quests: [Quest("Far", farStep), Quest("Near", nearStep)],
            lines: [new ZoneLineEntry { Scene = "A", DestinationZoneKey = "zone:b" }]
        );

        var result = Resolver(data).Resolve(Quest("Original", step), step, "A");

        Assert.Same(nearStep, result.Step);
        var requirement = Assert.Single(result.Chain, link => link.Atom != null);
        Assert.Equal("Near", requirement.Atom!.Ref);
        Assert.Contains("Complete Far", requirement.Alternatives);
    }

    [Fact]
    public void Fewer_unmet_atoms_win_before_route_cost()
    {
        var step = Character("target");
        var first = Quest("First", Character("near"));
        var second = Quest("Second", Character("near"));
        var far = Quest("Far", Character("far"));
        var data = Data(
            [
                [
                    [Atom(GateAtomKind.QuestDone, "First"), Atom(GateAtomKind.QuestDone, "Second")],
                    [Atom(GateAtomKind.QuestDone, "Far")],
                ],
            ],
            new()
            {
                ["target"] = [new SpawnPoint { Scene = "A", Condition = 0 }],
                ["near"] = [new SpawnPoint { Scene = "A" }],
                ["far"] = [new SpawnPoint { Scene = "B" }],
            },
            quests: [first, second, far],
            lines: [new ZoneLineEntry { Scene = "A", DestinationZoneKey = "zone:b" }]
        );
        var result = Resolver(data).Resolve(Quest("Original", step), step, "A");
        Assert.Same(far, result.Quest);
        Assert.True(result.CanNavigate);
    }

    [Fact]
    public void Removed_target_has_no_navigation_or_requirement_guidance()
    {
        var step = Character("removed");
        var data = Data(
            [
                [
                    [Atom(GateAtomKind.QuestNotDone, "Done")],
                ],
            ],
            new() { ["removed"] = [new SpawnPoint { Scene = "A", Condition = 0 }] }
        );
        var facts = new GateTestFacts();
        facts.Quests.Add("Done");
        var result = Resolver(data, facts).Resolve(Quest("Original", step), step, "A");
        Assert.False(result.CanNavigate);
        Assert.Contains("no longer available", result.Message);
        Assert.Empty(result.Chain);
    }

    [Fact]
    public void Advisory_atoms_from_every_group_stay_on_original_target()
    {
        var step = Character("restored");
        var first = Atom(GateAtomKind.EncounterWon, "first");
        var second = Atom(GateAtomKind.EncounterWon, "second");
        var data = Data(
            [
                [
                    [first],
                    [second],
                ],
            ],
            new() { ["restored"] = [new SpawnPoint { Scene = "A", Condition = 0 }] }
        );
        var result = Resolver(data).Resolve(Quest("Original", step), step, "A");
        Assert.True(result.CanNavigate);
        Assert.Same(step, result.Step);
        Assert.Equal(new[] { first, second }, result.Advisories);
        Assert.All(result.Chain, link => Assert.Equal(GateAtomKind.EncounterWon, link.Atom!.Kind));
    }

    [Fact]
    public void Encounter_focus_retains_original_advice_through_key_and_scene_changes()
    {
        var data = ShippingData();
        var quest = data.GetByDBName("Riftstone")!;
        var origin = quest.Steps![0];
        var facts = new GateTestFacts();
        var resolver = Resolver(data, facts);
        var original = resolver.Resolve(quest, origin, "Stowaway");
        var context = NavigationResolutionPolicy.CaptureAdvisories(original);
        var encounter = context.Single(link => link.Atom?.Ref == "character:eldoth molorai");
        var focus = new QuestStep
        {
            Order = origin.Order,
            Action = "kill",
            Description = encounter.Label,
            TargetType = "character",
            TargetKey = encounter.Atom!.Ref,
            TargetName = "Eldoth Molorai",
        };

        foreach (
            var (scene, key, targetType) in new[]
            {
                ("Stowaway", (string?)null, "item"),
                ("Stowaway", "item:key - ghostly key", "item"),
                ("AzynthiClear", "item:key - intricate", "character"),
            }
        )
        {
            if (key != null)
                facts.Keyring.Add(data.GateItems[key].GameId);
            var result = NavigationResolutionPolicy.PreserveAdvisories(
                resolver.Resolve(quest, focus, scene),
                context
            );
            Assert.True(result.CanNavigate, result.Message);
            Assert.Single(result.Chain, link => link.Atom?.Ref == "character:eldoth molorai");
            Assert.Equal(targetType, result.Step.TargetType);
            if (targetType == "character")
                Assert.Equal("character:eldoth molorai", result.Step.TargetKey);
            context = NavigationResolutionPolicy.CaptureAdvisories(result);
        }

        var unreachable = NavigationResolutionPolicy.PreserveAdvisories(
            resolver.Resolve(quest, focus, "MainMenu"),
            context
        );
        Assert.False(unreachable.CanNavigate);
        Assert.Single(unreachable.Chain, link => link.Atom?.Ref == "character:eldoth molorai");
    }

    [Theory]
    [InlineData(false)]
    [InlineData(true)]
    public void Empty_condition_and_unreachable_target_fail_with_explanation(bool unreachable)
    {
        var step = Character("target");
        var data = Data(
            [
                [],
            ],
            new()
            {
                ["target"] =
                [
                    new SpawnPoint
                    {
                        Scene = unreachable ? "B" : "A",
                        Condition = unreachable ? null : 0,
                    },
                ],
            }
        );
        var result = Resolver(data).Resolve(Quest("Original", step), step, "A");
        Assert.False(result.CanNavigate);
        Assert.False(string.IsNullOrWhiteSpace(result.Message));
    }

    [Fact]
    public void Route_requirement_cycle_stops_without_recursive_feasibility_search()
    {
        var step = Character("target");
        var source = new ItemSource
        {
            Type = "pickup",
            SourceKey = "itembag:b:1:2:3",
            Scene = "B",
        };
        var data = Data(
            [
                [
                    [Atom(GateAtomKind.KeyHeld, "item:key")],
                ],
            ],
            new() { ["target"] = [new SpawnPoint { Scene = "B" }] },
            items: new()
            {
                ["item:key"] = new GateItem
                {
                    Name = "Key",
                    GameId = "1",
                    Sources = [source],
                },
            },
            lines:
            [
                new ZoneLineEntry
                {
                    Scene = "A",
                    DestinationZoneKey = "zone:b",
                    Condition = 0,
                },
            ]
        );
        var result = Resolver(data).Resolve(Quest("Original", step), step, "A");
        Assert.False(result.CanNavigate);
        Assert.Contains("cycle", result.Message);
    }

    [Fact]
    public void Reachable_available_placement_wins_over_local_gate_and_unreachable_placement()
    {
        var step = Character("target");
        var data = Data(
            [
                [],
            ],
            new()
            {
                ["target"] =
                [
                    new SpawnPoint { Scene = "A", Condition = 0 },
                    new SpawnPoint { Scene = "C" },
                    new SpawnPoint { Scene = "B" },
                ],
            },
            lines: [new ZoneLineEntry { Scene = "A", DestinationZoneKey = "zone:b" }]
        );
        var result = Resolver(data).Resolve(Quest("Original", step), step, "A");
        Assert.True(result.CanNavigate);
        Assert.Equal("B", result.SelectedScene);
        Assert.Same(step, result.Step);
    }

    [Theory]
    [InlineData(false, "PlanarFern")]
    [InlineData(true, "PlanarFern")]
    [InlineData(false, "Rune1")]
    [InlineData(true, "Rune6")]
    public void Stored_portal_requirement_gets_the_stone_then_installs_it(
        bool hasStone,
        string slot
    )
    {
        var step = Character("target");
        var atom = Atom(GateAtomKind.PlanningSlotItem, "item:stone");
        atom.Slot = slot;
        atom.Instruction = slot.StartsWith("Rune", StringComparison.Ordinal)
            ? "Place Portal stone in a rune slot on your planning table."
            : "Place Portal stone in the planning-table slot for Fernalla.";
        var planning = new ItemSource
        {
            Type = "pickup",
            Name = "Planning Table",
            SourceKey = "planningtable:a:12:3:45",
            Scene = "A",
        };
        var planningQuest = Quest("Planning", Character("planner"));
        planningQuest.RequiredItems =
        [
            new RequiredItemInfo
            {
                ItemStableKey = "item:portals",
                ItemName = "Box of Portals",
                Sources = [planning],
            },
        ];
        var data = Data(
            [
                [
                    [atom],
                ],
            ],
            new()
            {
                ["target"] = [new SpawnPoint { Scene = "A", Condition = 0 }],
                ["merchant"] = [new SpawnPoint { Scene = "A" }],
            },
            quests: [planningQuest],
            items: new()
            {
                ["item:stone"] = new GateItem
                {
                    Name = "Portal stone",
                    GameId = "134379",
                    Sources =
                    [
                        new ItemSource
                        {
                            Type = "vendor",
                            SourceKey = "merchant",
                            Scene = "A",
                        },
                    ],
                },
            }
        );
        var facts = new GateTestFacts();
        if (hasStone)
            facts.Inventory["item:stone"] = 1;
        var resolver = Resolver(data, facts);
        var quest = Quest("Original", step);
        var result = resolver.Resolve(quest, step, "A");
        Assert.True(result.CanNavigate, result.Message);
        Assert.Equal(hasStone ? planning.SourceKey : "item:stone", result.Step.TargetKey);
        Assert.Equal(hasStone ? atom.Instruction : "Obtain Portal stone.", result.Step.Description);
        facts.Rooms[slot] = "item:stone";
        var installed = resolver.Resolve(quest, step, "A");
        Assert.Same(step, installed.Step);
    }

    [Fact]
    public void Furnishing_requirement_uses_planning_table_coordinates_from_guide()
    {
        var step = Character("vendor");
        var room = Atom(GateAtomKind.RoomFurnished, "item:furniture");
        room.Slot = "L1";
        var planning = new ItemSource
        {
            Type = "pickup",
            Name = "Planning Table",
            SourceKey = "planningtable:a:12:3:45",
            Scene = "A",
        };
        var planningQuest = Quest("Planning", Character("planner"));
        planningQuest.RequiredItems =
        [
            new RequiredItemInfo
            {
                ItemStableKey = "item:portals",
                ItemName = "Box of Portals",
                Sources = [planning],
            },
        ];
        var data = Data(
            [
                [
                    [room],
                ],
            ],
            new() { ["vendor"] = [new SpawnPoint { Scene = "A", Condition = 0 }] },
            quests: [planningQuest],
            items: new()
            {
                ["item:furniture"] = new GateItem { Name = "Wood Vendor Set", GameId = "1" },
            }
        );
        var result = Resolver(data).Resolve(Quest("Original", step), step, "A");
        Assert.True(result.CanNavigate, result.Message);
        Assert.Equal(planning.SourceKey, result.Step.TargetKey);
        Assert.Equal(12f, result.Step.Location!.X);
        Assert.Equal(3f, result.Step.Location.Y);
        Assert.Equal(45f, result.Step.Location.Z);
        Assert.Contains("Wood Vendor Set", result.DisplayText);
    }

    [Fact]
    public void Available_source_is_constrained_when_another_source_is_gated()
    {
        var gated = new ItemSource
        {
            Type = "drop",
            SourceKey = "gated",
            Condition = 0,
        };
        var available = new ItemSource { Type = "drop", SourceKey = "available" };
        var step = new QuestStep
        {
            Order = 1,
            Action = "collect",
            TargetType = "item",
            TargetKey = "item:goal",
            TargetName = "Goal",
            Description = "Collect Goal.",
            Sources = [gated, available],
        };
        var data = Data(
            [
                [],
            ],
            new()
            {
                ["gated"] = [new SpawnPoint { Scene = "A" }],
                ["available"] = [new SpawnPoint { Scene = "A" }],
            }
        );
        var result = Resolver(data).Resolve(Quest("Original", step), step, "A");
        Assert.True(result.CanNavigate);
        Assert.Same(available, Assert.Single(result.Step.Sources!));
        Assert.Equal(2, step.Sources.Count);
        Assert.Empty(result.Chain);
    }

    [Theory]
    [InlineData(false)]
    [InlineData(true)]
    public void One_gated_or_unreachable_source_preserves_every_available_source(bool unreachable)
    {
        var blocked = new ItemSource
        {
            Type = "drop",
            SourceKey = "blocked",
            Condition = unreachable ? null : 0,
        };
        var first = new ItemSource { Type = "drop", SourceKey = "first" };
        var second = new ItemSource { Type = "drop", SourceKey = "second" };
        var firstSpawn = new SpawnPoint { Scene = "A", X = 100 };
        var secondSpawn = new SpawnPoint { Scene = "A", X = 1 };
        var step = new QuestStep
        {
            Order = 1,
            Action = "collect",
            Description = "Collect Goal.",
            TargetType = "item",
            TargetKey = "item:goal",
            Sources = [blocked, first, second],
        };
        var data = Data(
            [
                [
                    [Atom(GateAtomKind.KeyHeld, "item:key")],
                ],
            ],
            new()
            {
                ["blocked"] = [new SpawnPoint { Scene = unreachable ? "C" : "A" }],
                ["first"] = [firstSpawn],
                ["second"] = [secondSpawn],
            },
            items: new()
            {
                ["item:key"] = new GateItem
                {
                    Name = "Key",
                    GameId = "key",
                    Sources = [new ItemSource { Type = "pickup", SourceKey = "itembag:a:1:2:3" }],
                },
            }
        );

        var result = Resolver(data).Resolve(Quest("Original", step), step, "A");

        Assert.True(result.CanNavigate, result.Message);
        Assert.Equal(new[] { first, second }, result.Step.Sources);
        Assert.Equal(new[] { firstSpawn, secondSpawn }, result.AvailableSpawns);
        Assert.Null(result.SelectedScene);
        Assert.Null(result.SelectedSpawn);
        Assert.Null(result.EntryLine);
        Assert.Empty(result.Chain);
        Assert.Equal(3, step.Sources.Count);
    }

    [Fact]
    public void Filtering_parent_and_child_conditions_keeps_all_usable_leaves_without_reintroducing_gates()
    {
        var blockedByParent = new ItemSource { Type = "drop", SourceKey = "blocked_parent" };
        var blockedChild = new ItemSource
        {
            Type = "drop",
            SourceKey = "blocked_child",
            Condition = 0,
        };
        var first = new ItemSource { Type = "drop", SourceKey = "first" };
        var second = new ItemSource { Type = "drop", SourceKey = "second" };
        var step = new QuestStep
        {
            Order = 1,
            Action = "collect",
            Description = "Collect Goal.",
            TargetType = "item",
            TargetKey = "item:goal",
            Sources =
            [
                new ItemSource
                {
                    Type = "item_use",
                    SourceKey = "item:blocked",
                    Condition = 0,
                    Children = [blockedByParent],
                },
                new ItemSource
                {
                    Type = "item_use",
                    SourceKey = "item:usable",
                    Children = [blockedChild, first, second],
                },
            ],
        };
        var data = Data(
            [
                [],
            ],
            new()
            {
                ["blocked_parent"] = [new SpawnPoint { Scene = "A" }],
                ["blocked_child"] = [new SpawnPoint { Scene = "A" }],
                ["first"] = [new SpawnPoint { Scene = "A" }],
                ["second"] = [new SpawnPoint { Scene = "A" }],
            }
        );

        var result = Resolver(data).Resolve(Quest("Original", step), step, "A");

        Assert.True(result.CanNavigate, result.Message);
        Assert.Equal(new[] { first, second }, result.Step.Sources);
        Assert.All(result.Step.Sources!, source => Assert.Null(source.Children));
        Assert.Equal(2, result.AvailableSpawns!.Count);
        Assert.Null(result.SelectedScene);
        Assert.Empty(result.Chain);
        Assert.Equal(3, step.Sources[1].Children!.Count);
    }

    [Fact]
    public void Shared_source_keeps_usable_placements_but_excludes_gated_and_unreachable_placements()
    {
        var gated = new SpawnPoint { Scene = "A", Condition = 0 };
        var unreachable = new SpawnPoint { Scene = "C" };
        var available = new SpawnPoint { Scene = "B" };
        var local = new SpawnPoint { Scene = "A" };
        var sharedSource = new ItemSource { Type = "drop", SourceKey = "shared" };
        var localSource = new ItemSource { Type = "drop", SourceKey = "local" };
        var step = new QuestStep
        {
            Order = 1,
            Action = "collect",
            Description = "Collect Goal.",
            TargetType = "item",
            TargetKey = "item:goal",
            Sources = [sharedSource, localSource],
        };
        var data = Data(
            [
                [],
            ],
            new() { ["shared"] = [gated, unreachable, available], ["local"] = [local] },
            lines: [new ZoneLineEntry { Scene = "A", DestinationZoneKey = "zone:b" }]
        );

        var result = Resolver(data).Resolve(Quest("Original", step), step, "A");

        Assert.True(result.CanNavigate, result.Message);
        Assert.Equal(new[] { sharedSource, localSource }, result.Step.Sources);
        Assert.Equal(new[] { available, local }, result.AvailableSpawns);
        Assert.Null(result.SelectedScene);
        Assert.Null(result.SelectedSpawn);
        Assert.Empty(result.Chain);
    }

    [Fact]
    public void Requirement_endpoint_retains_all_available_sources_and_origin_can_reconsider_an_opened_source()
    {
        var first = new ItemSource { Type = "drop", SourceKey = "first" };
        var second = new ItemSource { Type = "drop", SourceKey = "second" };
        var gated = new ItemSource
        {
            Type = "drop",
            SourceKey = "gated",
            Condition = 1,
        };
        var step = Character("target");
        var quest = Quest("Original", step);
        var data = Data(
            [
                [
                    [Atom(GateAtomKind.ItemHeld, "item:goal")],
                ],
                [
                    [Atom(GateAtomKind.KeyHeld, "item:key")],
                ],
            ],
            new()
            {
                ["target"] = [new SpawnPoint { Scene = "A", Condition = 0 }],
                ["gated"] = [new SpawnPoint { Scene = "A" }],
                ["first"] = [new SpawnPoint { Scene = "A" }],
                ["second"] = [new SpawnPoint { Scene = "A" }],
            },
            items: new()
            {
                ["item:goal"] = new GateItem
                {
                    Name = "Goal",
                    GameId = "goal",
                    Sources = [gated, first, second],
                },
                ["item:key"] = new GateItem { Name = "Key", GameId = "key" },
            }
        );
        var facts = new GateTestFacts();
        var resolver = Resolver(data, facts);

        var before = resolver.Resolve(quest, step, "A");

        Assert.True(before.CanNavigate, before.Message);
        Assert.Equal(new[] { first, second }, before.Step.Sources);
        Assert.Null(before.SelectedSpawn);
        facts.Keyring.Add("key");

        var after = resolver.Resolve(quest, step, "A");

        Assert.True(after.CanNavigate, after.Message);
        Assert.Equal(new[] { gated, first, second }, after.Step.Sources);
        Assert.Equal(3, after.AvailableSpawns!.Count);
    }

    [Fact]
    public void Completed_candle_reward_quest_is_not_followed_back_to_its_acquisition()
    {
        var data = ShippingData();
        var candle = data.GateItems.Single(item => item.Value.Name == "Nighthollow Candle");
        var completed = data.GetByStableKey("quest:ignitingnighthollow")!;
        var step = new QuestStep
        {
            Order = 1,
            Action = "collect",
            Description = "Collect Nighthollow Candle.",
            TargetType = "item",
            TargetKey = candle.Key,
            TargetName = candle.Value.Name,
            Sources = candle.Value.Sources,
        };
        var facts = new GateTestFacts();
        facts.Quests.Add(completed.DBName);
        var gates = new GateConditions(data, facts);
        RequirementResolver? resolver = null;
        resolver = new RequirementResolver(
            data,
            gates,
            new ZoneGraph(data, gates),
            quest =>
                !NavigationResolutionPolicy.CanResolveQuest(facts.IsQuestCompleted(quest.DBName))
                    ? null
                    : resolver!.BuildAcquisitionStep(quest) ?? quest.Steps?.FirstOrDefault()
        );

        var result = resolver.Resolve(Quest("Original", step), step, "Duskenlight");

        Assert.Equal(0, facts.ItemCount(candle.Key));
        Assert.False(result.CanNavigate);
        Assert.Same(step, result.Step);
        Assert.Empty(result.Chain);
        Assert.DoesNotContain("Complete " + completed.DisplayName, result.DisplayText);
        Assert.Equal("No reachable source is known for Nighthollow Candle.", result.Message);
    }

    [Fact]
    public void Pinned_locked_line_resolves_key_even_when_an_open_route_exists()
    {
        var step = Character("target");
        var pinned = new ZoneLineEntry
        {
            Scene = "A",
            DestinationZoneKey = "zone:b",
            Condition = 0,
        };
        var source = new ItemSource { Type = "pickup", SourceKey = "itembag:a:1:2:3" };
        var data = Data(
            [
                [
                    [Atom(GateAtomKind.KeyHeld, "item:key")],
                ],
            ],
            new() { ["target"] = [new SpawnPoint { Scene = "B" }] },
            items: new()
            {
                ["item:key"] = new GateItem
                {
                    Name = "Pinned Key",
                    GameId = "1",
                    Sources = [source],
                },
            },
            lines: [new ZoneLineEntry { Scene = "A", DestinationZoneKey = "zone:b" }, pinned]
        );
        var quest = Quest("Original", step);
        var resolver = Resolver(data);
        Assert.Same(step, resolver.Resolve(quest, step, "A").Step);
        var result = resolver.Resolve(quest, step, "A", pinned);
        Assert.True(result.CanNavigate, result.Message);
        Assert.Equal("item:key", result.Step.TargetKey);
        Assert.Contains("Pinned Key", result.DisplayText);
    }

    [Fact]
    public void Ungated_item_preserves_all_sources_and_manual_scene_selection()
    {
        var step = new QuestStep
        {
            Order = 1,
            Action = "collect",
            Description = "Collect Goal.",
            TargetType = "item",
            TargetKey = "item:goal",
            Sources =
            [
                new ItemSource { Type = "drop", SourceKey = "first" },
                new ItemSource { Type = "drop", SourceKey = "second" },
            ],
        };
        var data = Data(
            [],
            new()
            {
                ["first"] = [new SpawnPoint { Scene = "A" }],
                ["second"] = [new SpawnPoint { Scene = "B" }],
            },
            lines: [new ZoneLineEntry { Scene = "A", DestinationZoneKey = "zone:b" }]
        );
        var result = Resolver(data).Resolve(Quest("Original", step), step, "A");
        Assert.True(result.CanNavigate);
        Assert.Same(step, result.Step);
        Assert.Null(result.SelectedScene);
        Assert.Null(result.SelectedSpawn);
        Assert.Null(result.EntryLine);
        Assert.Equal(2, result.Step.Sources!.Count);
    }

    [Fact]
    public void Unreachable_first_requirement_falls_back_to_reachable_larger_group()
    {
        var step = Character("target");
        var unreachable = Quest("Unreachable", Character("far"));
        var reachable = Quest("Reachable", Character("near"));
        var other = Quest("Other", Character("near"));
        var data = Data(
            [
                [
                    [Atom(GateAtomKind.QuestDone, "Unreachable")],
                    [
                        Atom(GateAtomKind.QuestDone, "Reachable"),
                        Atom(GateAtomKind.QuestDone, "Other"),
                    ],
                ],
            ],
            new()
            {
                ["target"] = [new SpawnPoint { Scene = "A", Condition = 0 }],
                ["far"] = [new SpawnPoint { Scene = "B" }],
                ["near"] = [new SpawnPoint { Scene = "A" }],
            },
            quests: [unreachable, reachable, other]
        );
        var result = Resolver(data).Resolve(Quest("Original", step), step, "A");
        Assert.True(result.CanNavigate, result.Message);
        Assert.Same(reachable, result.Quest);
        Assert.Same(reachable.Steps![0], result.Step);
        Assert.Contains(result.Chain, link => link.Alternatives.Contains("Complete Unreachable"));
    }

    [Theory]
    [InlineData("world_drop")]
    [InlineData("common_world_item")]
    [InlineData("fishing_bonus")]
    [InlineData("treasure_chest")]
    public void Random_only_origin_preserves_existing_special_source_handling(string sourceType)
    {
        var step = new QuestStep
        {
            Order = 1,
            Action = "collect",
            Description = "Collect Goal.",
            TargetType = "item",
            TargetKey = "item:goal",
            Sources = [new ItemSource { Type = sourceType }],
        };
        var data = Data([], new());
        var result = Resolver(data).Resolve(Quest("Original", step), step, "A");
        Assert.True(result.CanNavigate);
        Assert.Same(step, result.Step);
        Assert.Null(result.SelectedScene);
        Assert.Empty(result.Chain);
    }
}
