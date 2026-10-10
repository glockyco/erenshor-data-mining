using AdventureGuide.Data;
using AdventureGuide.Navigation;
using AdventureGuide.UI;
using Newtonsoft.Json;

namespace AdventureGuide.Tests;

public sealed class SpecialItemSourceTests
{
    private static ItemSource WorldDrop(double? chance = 0.1) =>
        new()
        {
            Type = "world_drop",
            Name = "Any enemy above level 15",
            Level = 16,
            Chance = chance,
        };

    private static ItemSource FishingBonus() =>
        new()
        {
            Type = "fishing_bonus",
            Name = "Any fishing catch",
            Chance = 1.25,
        };

    private static ItemSource Chest() =>
        new()
        {
            Type = "treasure_chest",
            Name = "Treasure map chest",
            Level = 30,
            LevelMax = 35,
            Chance = 56.57,
            SourceKey = "character:treasurechest 30-35",
            Instruction = "Read a Treasure Map and dig at the marked spot.",
        };

    private static ItemSource UsedItem() =>
        new()
        {
            Type = "item_use",
            Name = "Bag of Offering Stones",
            SourceKey = "item:bag",
            Instruction = "Use Bag of Offering Stones.",
            Children =
            [
                new ItemSource
                {
                    Type = "drop",
                    Name = "Seller",
                    SourceKey = "character:seller",
                },
            ],
        };

    private static QuestEntry Quest(List<ItemSource> sources) =>
        new()
        {
            StableKey = "quest:test",
            DBName = "Test",
            DisplayName = "Test",
            Steps =
            [
                new QuestStep
                {
                    Order = 1,
                    Action = "collect",
                    Description = "Collect Test Token",
                    TargetType = "item",
                    TargetKey = "item:test",
                    TargetName = "Test Token",
                },
            ],
            RequiredItems =
            [
                new RequiredItemInfo
                {
                    ItemName = "Test Token",
                    ItemStableKey = "item:test",
                    Quantity = 1,
                    Sources = sources,
                },
            ],
        };

    private static void Validate(ItemSource source)
    {
        GuideData.ValidateWrapper(new GuideWrapper { Version = 6, Quests = [Quest([source])] });
    }

    [Fact]
    public void New_sources_validate_and_parse_percent_and_level_range()
    {
        foreach (var source in new[] { WorldDrop(), FishingBonus(), Chest(), UsedItem() })
            Validate(source);
        var parsed = JsonConvert.DeserializeObject<ItemSource>(
            """{"type":"treasure_chest","chance":56.57,"level":30,"level_max":35}"""
        )!;
        Assert.Equal(56.57, parsed.Chance);
        Assert.Equal(35, parsed.LevelMax);
    }

    [Theory]
    [InlineData(null)]
    [InlineData(0.0)]
    [InlineData(-0.1)]
    [InlineData(100.01)]
    [InlineData(double.NaN)]
    [InlineData(double.PositiveInfinity)]
    public void Invalid_world_chances_are_rejected(double? chance) =>
        Assert.Throws<InvalidDataException>(() => Validate(WorldDrop(chance)));

    [Fact]
    public void Hundred_percent_is_valid() => Validate(WorldDrop(100));

    [Fact]
    public void Random_sources_cannot_claim_fixed_locations()
    {
        var world = WorldDrop();
        world.Scene = "Fake";
        Assert.Throws<InvalidDataException>(() => Validate(world));
        var fishing = FishingBonus();
        fishing.Level = 1;
        Assert.Throws<InvalidDataException>(() => Validate(fishing));
        fishing.Level = null;
        fishing.SourceKey = "character:fake";
        Assert.Throws<InvalidDataException>(() => Validate(fishing));
    }

    [Fact]
    public void Treasure_chest_requires_ordered_bracket_chance_and_instruction()
    {
        var chest = Chest();
        chest.LevelMax = 29;
        Assert.Throws<InvalidDataException>(() => Validate(chest));
        chest.LevelMax = 35;
        chest.Chance = null;
        Assert.Throws<InvalidDataException>(() => Validate(chest));
        chest.Chance = 56.57;
        chest.Instruction = null;
        Assert.Throws<InvalidDataException>(() => Validate(chest));
    }

    [Fact]
    public void Item_use_requires_item_identity_and_children_and_validates_child_vendor_name()
    {
        var source = UsedItem();
        source.SourceKey = "character:seller";
        Assert.Throws<InvalidDataException>(() => Validate(source));
        source.SourceKey = "item:bag";
        source.Children = null;
        Assert.Throws<InvalidDataException>(() => Validate(source));
        source.Children =
        [
            new ItemSource { Type = "vendor", Instruction = "Buy Bag of Offering Stones." },
        ];
        Validate(source);
    }

    [Fact]
    public void Step_sources_are_validated_without_required_items()
    {
        var quest = Quest([]);
        quest.RequiredItems = null;
        quest.Steps![0].Sources = [WorldDrop(null)];
        Assert.Throws<InvalidDataException>(() =>
            GuideData.ValidateWrapper(new GuideWrapper { Version = 6, Quests = [quest] })
        );
    }

    [Fact]
    public void Random_source_text_uses_percent_not_fraction_and_chest_bracket()
    {
        Assert.Equal(
            "Drops from: Any enemy above level 15  ·  0.1%",
            SourceListText.Label(WorldDrop())
        );
        Assert.Equal("Fishing: Any fishing catch  ·  1.25%", SourceListText.Label(FishingBonus()));
        Assert.Equal("Treasure map chest (dig at Lv 30-35)  ·  57%", SourceListText.Label(Chest()));
        Assert.Equal("Use: Bag of Offering Stones", SourceListText.Label(UsedItem()));
    }

    [Fact]
    public void Hidden_bonus_sources_do_not_suggest_a_recommended_level()
    {
        Assert.Equal(
            "3 more sources",
            SourceListText.MoreSources([WorldDrop(), FishingBonus(), Chest()], 0)
        );
        Assert.Equal(
            "4 more sources (Lv 25)",
            SourceListText.MoreSources(
                [WorldDrop(), new ItemSource { Level = 25 }, FishingBonus(), Chest()],
                0
            )
        );
    }

    [Fact]
    public void Random_sources_are_never_static_candidates_even_with_spawn_shaped_keys()
    {
        var quest = Quest([WorldDrop(), FishingBonus(), Chest()]);
        var data = GuideData.FromWrapper(
            new GuideWrapper
            {
                Version = 6,
                Quests = [Quest([])],
                CharacterSpawns = new Dictionary<string, List<SpawnPoint>>
                {
                    ["character:fake"] = [new SpawnPoint { Scene = "Fake" }],
                },
            }
        );
        foreach (var source in quest.RequiredItems![0].Sources!)
        {
            source.SourceKey = "character:fake";
            source.Scene = "Fake";
            Assert.False(ItemSourcePolicy.IsStaticCandidate(source));
        }
        Assert.Null(StepSceneResolver.FindFirstSourceKey(quest, quest.Steps![0]));
        Assert.Null(StepSceneResolver.ResolveScene(quest, quest.Steps[0], data));
        Assert.False(StepSceneResolver.HasSourceInScene(quest, quest.Steps[0], data, "Fake"));
        Assert.Null(WorldDrop().MakeSourceId());
        Assert.Null(FishingBonus().MakeSourceId());
        Assert.Equal("treasure:dig-site", Chest().MakeSourceId());
    }

    [Theory]
    [InlineData(0, "character:seller")]
    [InlineData(1, null)]
    [InlineData(2, null)]
    public void Item_use_navigates_children_only_while_used_item_is_missing(
        int have,
        string? expected
    )
    {
        var source = UsedItem();
        var quest = Quest([source]);
        Assert.Null(source.MakeSourceId());
        Assert.Equal(
            expected,
            StepSceneResolver.FindFirstSourceKey(quest, quest.Steps![0], countItem: _ => have)
        );
        var needed = new HashSet<string>();
        CorpsePriorityPolicy.FillItems(quest.Steps[0], quest, _ => have, needed);
        Assert.Equal(have == 0, needed.Contains("Bag of Offering Stones"));
        Assert.Contains("Test Token", needed);
    }

    [Fact]
    public void Empty_container_does_not_hide_later_obtainable_sources()
    {
        var quest = Quest([new ItemSource { Type = "quest_reward", Children = [] }, UsedItem()]);
        Assert.Equal(
            "character:seller",
            StepSceneResolver.FindFirstSourceKey(quest, quest.Steps![0])
        );
    }

    [Fact]
    public void Step_source_list_takes_precedence_over_item_summary()
    {
        var quest = Quest([WorldDrop()]);
        quest.Steps![0].Sources = [UsedItem()];
        Assert.Equal(
            "character:seller",
            StepSceneResolver.FindFirstSourceKey(quest, quest.Steps[0])
        );
    }

    [Fact]
    public void Planning_table_is_a_fixed_pickup_not_a_ground_bag()
    {
        const string key = "planningtable:reliquary:267.40:0.09:321.30";
        Assert.True(PositionedSource.TryParse(key, out var location));
        Assert.Equal("planningtable", location.Kind);
        Assert.Equal("reliquary", location.Scene);
        Assert.False(location.IsZoneWide);
        Assert.Equal((267.4f, 0.09f, 321.3f), (location.X, location.Y, location.Z));
        var quest = Quest([
            new ItemSource
            {
                Type = "pickup",
                Name = "Planning Table",
                SourceKey = key,
                Scene = "Reliquary",
            },
        ]);
        var data = GuideData.FromWrapper(new GuideWrapper { Version = 6, Quests = [quest] });
        Assert.Equal("reliquary", StepSceneResolver.ResolveScene(quest, quest.Steps![0], data));
        Assert.True(StepSceneResolver.HasSourceInScene(quest, quest.Steps[0], data, "Reliquary"));
    }
}
