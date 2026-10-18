using AdventureGuide.Data;
using AdventureGuide.Navigation;
using AdventureGuide.State;

namespace AdventureGuide.Tests;

public sealed class OfferingActivationTests
{
    [Theory]
    [InlineData("Bring Fee.", "Bring Fee.", true)]
    [InlineData("Bring Fee.", "Bring Fee.\nCarry only Fee.", true)]
    [InlineData("Bring Fee.", "Bring Fee. elsewhere", false)]
    [InlineData("Bring Fee.", null, false)]
    public void Preparation_dedup_preserves_different_actions(
        string preparation,
        string? guidance,
        bool repeats
    ) =>
        Assert.Equal(
            repeats,
            AdventureGuide.UI.SourceListText.RepeatsPreparation(preparation, guidance)
        );

    [Theory]
    [InlineData(false, false, true)]
    [InlineData(false, true, true)]
    [InlineData(true, false, false)]
    [InlineData(true, true, true)]
    public void Offering_placements_have_markers_only_while_the_target_is_alive(
        bool offering,
        bool alive,
        bool expected
    ) => Assert.Equal(expected, SpawnMarkerPolicy.ShowsPlacement(offering, alive));

    [Theory]
    [InlineData("key")]
    [InlineData("index")]
    [InlineData("role")]
    [InlineData("character")]
    [InlineData("item")]
    [InlineData("site")]
    [InlineData("no-site")]
    [InlineData("no-name")]
    [InlineData("unbound")]
    public void Invalid_activation_contract_fails_load(string defect)
    {
        var wrapper = Fixture();
        var spawn = wrapper.CharacterSpawns!["character:chest"][0];
        var activation = wrapper.Activations!["activation:test"];
        switch (defect)
        {
            case "key":
                spawn.Activations![0].Key = "missing";
                break;
            case "index":
                spawn.Activations![0].Offering = 3;
                break;
            case "role":
                spawn.Activations![0].Role = "other";
                break;
            case "character":
                spawn.Activations![0].Role = "spawn";
                break;
            case "item":
                wrapper.GateItems!.Clear();
                break;
            case "site":
                activation.Site.Bounds.Center.X = float.NaN;
                break;
            case "no-site":
                activation.Site = null!;
                break;
            case "no-name":
                activation.DisplayName = "";
                break;
            case "unbound":
                wrapper.CharacterSpawns.Remove("character:enemy");
                break;
        }
        Assert.Throws<InvalidDataException>(() => GuideData.FromWrapper(wrapper));
    }

    [Fact]
    public void Reward_resolution_follows_observable_state_and_warns_about_other_offerings()
    {
        var data = GuideData.FromWrapper(Fixture());
        var spawn = data.CharacterSpawns["character:chest"][0];
        var reference = spawn.Activations![0];
        var held = new HashSet<string>();
        var live = new HashSet<string>();
        var offering = data.Activations[reference.Key].Offerings[0];
        OfferingEndpoint Resolve() =>
            OfferingNavigation.Resolve(
                data,
                spawn,
                reference,
                "character:chest",
                "A",
                key => held.Contains(key) ? 1 : 0,
                live.Contains
            );
        Assert.Equal("item:fee", Resolve().MissingItem);
        held.Add("item:fee");
        Assert.Equal(10, Resolve().X);
        Assert.Equal("Bring Fee to the arena.", Resolve().Instruction);
        held.Add("item:other");
        Assert.Contains(
            "Carry only Fee; another carried offering can be used first.",
            Resolve().Instruction
        );
        live.Add("character:enemy");
        Assert.Equal("character:enemy", Resolve().LiveCharacter);
        Assert.StartsWith("Defeat ", Resolve().Instruction);
        live.Add("character:chest");
        Assert.Equal("character:chest", Resolve().LiveCharacter);
        live.Clear();
        held.Clear();
        Assert.Equal(offering.ItemStableKey, Resolve().MissingItem);
    }

    [Fact]
    public void Ordinary_placement_competes_with_missing_offering_without_being_blocked()
    {
        var wrapper = Fixture();
        var ordinary = new SpawnPoint { Scene = "A", X = 40 };
        wrapper.CharacterSpawns!["character:chest"].Add(ordinary);
        var data = GuideData.FromWrapper(wrapper);
        var quest = new QuestEntry { StableKey = "quest:test", DBName = "TEST" };
        var step = new QuestStep { TargetType = "character", TargetKey = "character:chest" };
        var facts = new GateTestFacts();
        var gates = new GateConditions(data, facts);
        var result = new RequirementResolver(
            data,
            gates,
            new ZoneGraph(data, gates),
            _ => null
        ).Resolve(quest, step, "A");
        Assert.True(result.CanNavigate);
        Assert.Same(ordinary, result.SelectedSpawn);
        Assert.Null(result.Activation);
        Assert.False(data.IsOfferingOnlyPosition("A", ordinary.X, ordinary.Y, ordinary.Z));
        Assert.True(data.IsOfferingOnlyPosition("A", 20, 0, 0));
    }

    [Fact]
    public void Shipped_arena_chest_source_transitions_from_fee_to_site_to_enemy_to_chest()
    {
        var data = ShippingData();
        var quest = data.GetByStableKey("quest:vithtokenmob2")!;
        var step = quest.Steps!.First(s => s.TargetType == "item");
        var sources = ItemSourcePolicy.SourcesFor(quest, step)!;
        var source = sources.Single(s => s.SourceKey == "character:arenachest 1");
        var selected = SourceChoice.FindContaining(sources, source)!;
        var activation = data.Activations["activation:VithArena:PlaneOfVitheo:ARENA EVENT"];
        var offering = activation.Offerings[0];
        var facts = new GateTestFacts();
        var live = new HashSet<string>();
        var gates = new GateConditions(data, facts);
        var resolver = new RequirementResolver(
            data,
            gates,
            new ZoneGraph(data, gates),
            q => q.Steps?.FirstOrDefault(),
            live.Contains
        );
        RequirementResolution Resolve() =>
            resolver.Resolve(quest, step, activation.Scene, selectedChoice: selected);

        var missing = Resolve();
        Assert.True(missing.CanNavigate, missing.DisplayText);
        Assert.Equal(step.TargetName, missing.Chain[0].Label);
        Assert.Equal("item:ore - planar stone", missing.Step.TargetKey);
        Assert.Contains(missing.Chain, link => link.Atom?.Ref == offering.ItemStableKey);
        facts.Inventory[offering.ItemStableKey] = 1;
        var prepared = Resolve();
        Assert.True(prepared.CanNavigate, prepared.DisplayText);
        Assert.Equal(step.TargetKey, prepared.Step.TargetKey);
        Assert.Equal(activation.Site!.Bounds.Center.X, prepared.Activation!.Value.X);
        Assert.Equal("Bring Vithean Arena Fee (1) to Vitheo's arena.", prepared.Message);
        Assert.Same(source.CanonicalSpawn, prepared.SelectedSpawn);
        Assert.Equal(prepared.Message, AdventureGuide.UI.SourceListText.Preparation(source));

        live.Add(offering.Spawns[0].Character);
        facts.Inventory.Clear();
        var fighting = Resolve();
        Assert.Equal(offering.Spawns[0].Character, fighting.Activation!.Value.LiveCharacter);
        Assert.StartsWith("Defeat ", fighting.Message);
        live.Add(offering.Reward!);
        Assert.Equal(offering.Reward, Resolve().Activation!.Value.LiveCharacter);
        live.Clear();
        facts.Inventory[offering.ItemStableKey] = 1;
        facts.Inventory[activation.Offerings[1].ItemStableKey] = 1;
        Assert.Contains(
            "Carry only Vithean Arena Fee (1); another carried offering can be used first.",
            Resolve().Message
        );
        Assert.Same(source, selected.Primary);
        facts.Inventory.Remove(offering.ItemStableKey);
        Assert.Contains(
            "Carry only Vithean Arena Fee (1); another carried offering can be used first.",
            Resolve().Message
        );
        Assert.Contains(
            missing.Chain,
            link =>
                link.Atom?.Kind == GateAtomKind.ItemHeld
                && link.Atom.Ref == "item:ore - planar stone"
        );
    }

    [Theory]
    [InlineData(
        "quest:stowawayritualcomplete",
        "item:gen - demented brain",
        "character:demented malaroth",
        "Malaroth",
        "Bring Odd Malaroth Feed to Malaroth feeding site."
    )]
    [InlineData(
        "quest:sivakayanore",
        "item:ore - sivakayan ore",
        "character:candlekeeper",
        "Braxonian",
        "Bring A Strange Figurine to game board."
    )]
    public void Shipped_drop_sources_follow_their_actual_offering_and_site(
        string questKey,
        string itemKey,
        string character,
        string scene,
        string instruction
    )
    {
        var data = ShippingData();
        var quest = data.GetByStableKey(questKey)!;
        var step = quest.Steps!.First(s => s.TargetKey == itemKey);
        var sources = ItemSourcePolicy.SourcesFor(quest, step)!;
        var source = sources.Single(s => s.SourceKey == character);
        var choice = SourceChoice.FindContaining(sources, source)!;
        var spawn = source.CanonicalSpawn!;
        var reference = Assert.Single(spawn.Activations!);
        var activation = data.Activations[reference.Key];
        var offering = activation.Offerings[reference.Offering];
        var facts = new GateTestFacts();
        var live = new HashSet<string>();
        var gates = new GateConditions(data, facts);
        var resolver = new RequirementResolver(
            data,
            gates,
            new ZoneGraph(data, gates),
            q => q.Steps?.FirstOrDefault(),
            live.Contains
        );
        RequirementResolution Resolve() =>
            resolver.Resolve(quest, step, scene, selectedChoice: choice);
        var missing = Resolve();
        Assert.Contains(missing.Chain, link => link.Atom?.Ref == offering.ItemStableKey);
        facts.Inventory[offering.ItemStableKey] = 1;
        var prepared = Resolve();
        Assert.True(prepared.CanNavigate, prepared.DisplayText);
        Assert.Equal(activation.Site.Bounds.Center.X, prepared.Activation!.Value.X);
        Assert.Equal(activation.Site.Bounds.Center.Y, prepared.Activation.Value.Y);
        Assert.Equal(activation.Site.Bounds.Center.Z, prepared.Activation.Value.Z);
        Assert.Equal(itemKey, prepared.Step.TargetKey);
        Assert.Equal(instruction, prepared.Message);
        live.Add(character);
        facts.Inventory.Clear();
        Assert.Equal(character, Resolve().Activation!.Value.LiveCharacter);
    }

    [Fact]
    public void Shipped_faceless_offering_keeps_all_random_outcomes_and_preparation()
    {
        var data = ShippingData();
        var activation = Assert.Single(data.Activations.Values, a => a.Script == "Chessboard");
        var random = Assert.Single(activation.Offerings, offering => offering.Random);
        Assert.Equal(6, random.Spawns.Count);
        foreach (var member in random.Spawns)
        {
            var spawn = Assert.Single(data.CharacterSpawns[member.Character]);
            var reference = Assert.Single(spawn.Activations!);
            var endpoint = OfferingNavigation.Resolve(
                data,
                spawn,
                reference,
                member.Character,
                "Braxonian",
                key => key == random.ItemStableKey ? 1 : 0,
                _ => false
            );
            Assert.Equal(
                "Bring The Faceless to game board. A random opponent appears.",
                endpoint.Instruction
            );
            Assert.Equal(activation.Site.Bounds.Center.X, endpoint.X);
        }
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

    internal static GuideWrapper Fixture() =>
        new()
        {
            Version = GuideData.SchemaVersion,
            Encounters = TestData.EmptyEncounters(),
            Quests = [],
            ZoneLookup = new()
            {
                ["A"] = new ZoneInfo { StableKey = "zone:a", DisplayName = "A" },
            },
            GateItems = new()
            {
                ["item:fee"] = new GateItem
                {
                    Name = "Fee",
                    GameId = "1",
                    Sources = [],
                },
                ["item:other"] = new GateItem
                {
                    Name = "Other",
                    GameId = "2",
                    Sources = [],
                },
            },
            Activations = new()
            {
                ["activation:test"] = new OfferingActivation
                {
                    Script = "VithArena",
                    Scene = "A",
                    DisplayName = "the arena",
                    Site = new ActivationSite
                    {
                        X = 9,
                        Bounds = new ActivationBounds
                        {
                            Center = new ActivationPosition { X = 10 },
                            Extents = new ActivationPosition
                            {
                                X = 1,
                                Y = 1,
                                Z = 1,
                            },
                        },
                    },
                    Offerings =
                    [
                        new Offering
                        {
                            ItemStableKey = "item:fee",
                            ItemName = "Fee",
                            Spawns =
                            [
                                new OfferingSpawn { Character = "character:enemy", Quantity = 1 },
                            ],
                            Reward = "character:chest",
                        },
                        new Offering
                        {
                            ItemStableKey = "item:other",
                            ItemName = "Other",
                            Spawns =
                            [
                                new OfferingSpawn { Character = "character:enemy", Quantity = 1 },
                            ],
                        },
                    ],
                },
            },
            CharacterSpawns = new()
            {
                ["character:chest"] =
                [
                    new SpawnPoint
                    {
                        Scene = "A",
                        X = 20,
                        Activations =
                        [
                            new ActivationReference
                            {
                                Key = "activation:test",
                                Offering = 0,
                                Role = "reward",
                            },
                        ],
                    },
                ],
                ["character:enemy"] =
                [
                    new SpawnPoint
                    {
                        Scene = "A",
                        X = 30,
                        Activations =
                        [
                            new ActivationReference
                            {
                                Key = "activation:test",
                                Offering = 0,
                                Role = "spawn",
                            },
                            new ActivationReference
                            {
                                Key = "activation:test",
                                Offering = 1,
                                Role = "spawn",
                            },
                        ],
                    },
                ],
            },
        };
}
