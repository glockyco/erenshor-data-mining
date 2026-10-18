using AdventureGuide.Data;
using AdventureGuide.State;

namespace AdventureGuide.Tests;

public sealed class CanonicalSourceConditionsTests
{
    [Fact]
    public void Current_availability_ignores_initialization_and_outcome_requirements()
    {
        var source = new ItemSource
        {
            Type = "pickup",
            AcquisitionKey = "acq",
            LocationKey = "loc",
        };
        var fact = Fact();
        fact.Conditions.Add(Condition("item_held", "item:required", "availability"));
        fact.Conditions.Add(Condition("item_not_owned", "item:required", "source_initialization"));
        fact.Conditions.Add(
            Condition(
                "account_state",
                EncounterStateKeys.ReliquaryClaimed,
                "operation_outcome",
                "true",
                "account"
            )
        );
        var (data, facts) = Load(source, fact);
        var gates = new GateConditions(data, facts);
        Assert.False(gates.IsSourceAvailable(source));
        facts.Inventory["item:required"] = 1;
        Assert.True(gates.IsSourceAvailable(source));
        facts.Account = true;
        Assert.True(gates.IsSourceAvailable(source));
    }

    [Fact]
    public void Location_gates_do_not_leak_between_two_placements_of_one_source()
    {
        var first = new ItemSource
        {
            Type = "drop",
            AcquisitionKey = "acq",
            LocationKey = "loc",
        };
        var second = new ItemSource
        {
            Type = "drop",
            AcquisitionKey = "acq",
            LocationKey = "other",
        };
        var fact = Fact();
        fact.Locations[0].Conditions.Add(Condition("item_held", "item:key", "availability"));
        fact.Locations.Add(new SourceLocation { LocationKey = "other", Relation = "unlocated" });
        var (data, facts) = Load(first, fact, second);
        var gates = new GateConditions(data, facts);
        Assert.False(gates.IsSourceAvailable(first));
        Assert.True(gates.IsSourceAvailable(second));
        facts.Inventory["item:key"] = 1;
        Assert.True(gates.IsSourceAvailable(first));
    }

    [Fact]
    public void Alternative_groups_remain_OR_and_independent_gates_remain_AND()
    {
        var source = new ItemSource
        {
            Type = "pickup",
            AcquisitionKey = "acq",
            LocationKey = "loc",
        };
        var fact = Fact();
        fact.Conditions.Add(Condition("item_held", "item:a", "availability"));
        var alternative = Condition("item_held", "item:b", "availability");
        alternative.GroupIndex = 1;
        fact.Conditions.Add(alternative);
        var independent = Condition("item_held", "item:c", "availability");
        independent.GateKey = "independent";
        fact.Conditions.Add(independent);
        var (data, facts) = Load(source, fact);
        var gates = new GateConditions(data, facts);
        facts.Inventory["item:b"] = 1;
        Assert.False(gates.IsSourceAvailable(source));
        facts.Inventory["item:c"] = 1;
        Assert.True(gates.IsSourceAvailable(source));
        facts.Inventory.Remove("item:b");
        Assert.False(gates.IsSourceAvailable(source));
    }

    [Fact]
    public void Player_level_bounds_are_not_sim_actor_bounds()
    {
        var source = new ItemSource
        {
            Type = "auction_house",
            AcquisitionKey = "acq",
            LocationKey = "loc",
        };
        var fact = Fact();
        fact.Conditions.Add(
            new SourceCondition
            {
                GateKey = "player",
                Scope = "source",
                Phase = "availability",
                Predicate = "actor_level",
                Actor = "player",
                Minimum = 10,
                Maximum = 20,
                MaximumInclusive = false,
            }
        );
        fact.Conditions.Add(
            new SourceCondition
            {
                GateKey = "sim",
                Scope = "source",
                Phase = "availability",
                Predicate = "actor_level",
                Actor = "sim",
                Minimum = 99,
            }
        );
        var (data, facts) = Load(source, fact);
        var gates = new GateConditions(data, facts);
        facts.Level = 9;
        Assert.False(gates.IsSourceAvailable(source));
        facts.Level = 10;
        Assert.True(gates.IsSourceAvailable(source));
        facts.Level = 20;
        Assert.False(gates.IsSourceAvailable(source));
    }

    [Fact]
    public void Missing_location_and_unconfirmed_acquisition_cannot_become_routes()
    {
        var source = new ItemSource
        {
            Type = "drop",
            AcquisitionKey = "acq",
            LocationKey = "missing",
        };
        Assert.Throws<InvalidDataException>(() => Load(source, Fact()));
        source.LocationKey = "loc";
        var unconfirmed = Fact();
        unconfirmed.PlayerAccessState = "unconfirmed_player";
        Assert.Throws<InvalidDataException>(() => Load(source, unconfirmed));
    }

    [Theory]
    [InlineData(null)]
    [InlineData("another-acquisition")]
    public void Operation_input_cannot_bind_to_another_outcome(string? outcome)
    {
        var source = new ItemSource
        {
            Type = "item_use",
            AcquisitionKey = "acq",
            OperationUseKeys = ["input"],
        };
        var input = new ItemUseFact
        {
            UseKey = "input",
            ItemStableKey = "item:material",
            Kind = "smithing",
            OutcomeKey = outcome,
        };
        Assert.Throws<InvalidDataException>(() => Load(source, Fact(), input: input));
    }

    [Fact]
    public void Canonical_fishing_phase_keeps_its_window_and_bounded_final_odds()
    {
        var source = new ItemSource
        {
            Type = "fishing",
            Name = "Water",
            AcquisitionKey = "acq",
            LocationKey = "loc",
            Chance = 5,
            ChanceMax = 7,
            DayChance = 5,
            NightChance = 0,
            TimeRestriction = "day",
        };
        var fact = Fact();
        fact.Kind = "fishing";
        fact.ProbabilityKind = "bounded";
        fact.ProbabilityMin = 5;
        fact.ProbabilityMax = 7;
        var (data, facts) = Load(source, fact);
        Assert.Equal(5, ItemSourcePolicy.FishingChance(source, 12));
        Assert.Equal(0, ItemSourcePolicy.FishingChance(source, 23));
        Assert.True(new GateConditions(data, facts).IsSourceAvailable(source));
        source.NightChance = 6;
        source.TimeRestriction = null;
        Assert.Throws<InvalidDataException>(() => Load(source, fact));
    }

    private static SourceCondition Condition(
        string predicate,
        string reference,
        string phase,
        string? value = null,
        string? actor = null
    ) =>
        new()
        {
            GateKey = "gate",
            Predicate = predicate,
            ReferenceStableKey = reference,
            Scope = "source",
            Phase = phase,
            Value = value,
            Actor = actor,
        };

    [Theory]
    [InlineData(null, 1, "character:raval", "Defeat Raval")]
    [InlineData(9.0, 9, "character:stardust", "Defeat all 9 Stardust")]
    public void Canonical_defeat_count_reaches_condition_text(
        double? quantity,
        int expected,
        string reference,
        string description
    )
    {
        var source = new ItemSource
        {
            Type = "drop",
            AcquisitionKey = "acq",
            LocationKey = "loc",
        };
        var fact = Fact();
        var condition = Condition("encounter_won", reference, "availability");
        condition.Minimum = quantity;
        fact.Conditions.Add(condition);
        var (data, facts) = Load(source, fact);
        var gates = new GateConditions(data, facts);
        var atom = Assert.Single(Assert.Single(Assert.Single(gates.SourceRequirements(source))));
        Assert.Equal(expected, atom.Quantity);
        Assert.Equal(description, gates.Describe(atom));
        Assert.True(gates.IsSourceAvailable(source));
    }

    [Theory]
    [InlineData(0)]
    [InlineData(-1)]
    [InlineData(1.5)]
    public void Canonical_defeat_count_must_be_a_positive_integer(double quantity)
    {
        var source = new ItemSource
        {
            Type = "drop",
            AcquisitionKey = "acq",
            LocationKey = "loc",
        };
        var fact = Fact();
        var condition = Condition("encounter_won", "character:stardust", "availability");
        condition.Minimum = quantity;
        fact.Conditions.Add(condition);
        Assert.Throws<InvalidDataException>(() => Load(source, fact));
    }

    private static SourceFact Fact() =>
        new()
        {
            AcquisitionKey = "acq",
            ItemStableKey = "item:result",
            Kind = "item_bag",
            PlayerAccessState = "verified_player",
            ProbabilityKind = "unknown",
            ProbabilityStage = "final_acquisition",
            QuantityKind = "exact",
            QuantityMin = 1,
            QuantityMax = 1,
            Locations = new()
            {
                new SourceLocation { LocationKey = "loc", Relation = "unlocated" },
            },
        };

    private static (GuideData Data, Facts Facts) Load(
        ItemSource source,
        SourceFact fact,
        ItemSource? other = null,
        ItemUseFact? input = null
    )
    {
        var sources = new List<ItemSource> { source };
        if (other != null)
            sources.Add(other);
        var data = GuideData.FromWrapper(
            new GuideWrapper
            {
                Version = GuideData.SchemaVersion,
                Quests = new()
                {
                    new QuestEntry
                    {
                        StableKey = "quest:test",
                        DBName = "TEST",
                        DisplayName = "Test",
                        RequiredItems = new()
                        {
                            new RequiredItemInfo
                            {
                                ItemStableKey = "item:result",
                                ItemName = "Result",
                                Sources = sources,
                            },
                        },
                    },
                },
                Encounters = TestData.EmptyEncounters(),
                SourceFacts = new() { ["acq"] = fact },
                ItemUses = input == null ? new() : new() { ["input"] = input },
            }
        );
        return (data, new Facts());
    }

    private sealed class Facts : IGateFacts
    {
        public Dictionary<string, int> Inventory { get; } = new();
        public bool Account { get; set; }
        public int Level { get; set; } = 1;
        public int PlayerLevel => Level;

        public bool IsQuestCompleted(string key) => false;

        public bool ReadAccountState(string key) => Account;

        public string? ReadCharacterZoneState(string key) => null;

        public UnityEngine.Vector3? ReadCharacterPositionState(string key) => null;

        public int ItemCount(string key) => Inventory.GetValueOrDefault(key);

        public bool IsOnKeyring(string id) => false;

        public string? StoredItemIn(string slot) => null;
    }
}
