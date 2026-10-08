using AdventureGuide.Data;

namespace AdventureGuide.Tests;

public sealed class FurnishingTests
{
    private const string StoneVendor = "item:furniture - stone vendor";
    private const string WoodVendor = "item:furniture - wood vendor";

    private sealed class Rooms : IFurnitureSlots
    {
        private readonly Dictionary<string, string> _items = new();

        public Rooms With(string slot, string itemKey)
        {
            _items[slot] = itemKey;
            return this;
        }

        public string? ItemKeyIn(string slot) => _items.TryGetValue(slot, out var key) ? key : null;
    }

    private static SpawnPoint Furnishing(string slot, string set) =>
        new()
        {
            Scene = "Reliquary",
            FurnitureSlot = slot,
            FurnitureItemStableKey = set,
        };

    [Fact]
    public void A_furnishing_stands_only_where_its_room_holds_its_set()
    {
        var spawn = Furnishing("L2", StoneVendor);

        Assert.False(FurnishingPolicy.IsPresent(spawn, new Rooms()));
        Assert.False(FurnishingPolicy.IsPresent(spawn, new Rooms().With("L1", StoneVendor)));
        Assert.False(FurnishingPolicy.IsPresent(spawn, new Rooms().With("L2", WoodVendor)));
        Assert.True(FurnishingPolicy.IsPresent(spawn, new Rooms().With("L2", StoneVendor)));
        // Game item keys and guide keys differ only in case conventions.
        Assert.True(
            FurnishingPolicy.IsPresent(
                spawn,
                new Rooms().With("L2", "item:Furniture - Stone Vendor")
            )
        );
        Assert.True(FurnishingPolicy.IsPresent(new SpawnPoint { Scene = "Hidden" }, new Rooms()));
    }

    [Fact]
    public void A_character_is_absent_until_one_of_its_rooms_holds_its_set()
    {
        var spawns = new List<SpawnPoint>
        {
            Furnishing("L1", StoneVendor),
            Furnishing("R4", StoneVendor),
        };

        Assert.Equal(FurnishingStatus.Absent, FurnishingPolicy.StatusOf(spawns, new Rooms()));
        Assert.Equal(
            FurnishingStatus.Present,
            FurnishingPolicy.StatusOf(spawns, new Rooms().With("R4", StoneVendor))
        );
        // A prefab merged into the group with a spawn of its own exists anyway.
        spawns.Add(new SpawnPoint { Scene = "Azure" });
        Assert.Equal(FurnishingStatus.Ungated, FurnishingPolicy.StatusOf(spawns, new Rooms()));
        Assert.Equal(FurnishingStatus.Ungated, FurnishingPolicy.StatusOf(null, new Rooms()));
    }

    [Fact]
    public void Requirement_names_each_set_once()
    {
        Assert.Equal(
            "Requires Stone Vendor Set or Wood Vendor Set in a Reliquary room",
            FurnishingPolicy.RequirementText(
                new[] { "Stone Vendor Set", "Wood Vendor Set", "Stone Vendor Set" }
            )
        );
    }

    [Fact]
    public void Scene_resolution_skips_an_absent_furnishing_source()
    {
        // Bread's cheapest source is a Pocket Vendor; without the set in a
        // room the tracker must name the next source's zone, not the Reliquary.
        var data = GuideData.FromWrapper(
            new GuideWrapper
            {
                Version = 6,
                Quests = [],
                CharacterSpawns = new Dictionary<string, List<SpawnPoint>>
                {
                    ["character:a rift vendor@" + StoneVendor] = [Furnishing("L1", StoneVendor)],
                    ["character:shopkeeper"] = [new SpawnPoint { Scene = "Stowaway" }],
                },
                FurnitureSets = new Dictionary<string, FurnitureSetInfo>
                {
                    [StoneVendor] = new() { DisplayName = "Stone Vendor Set" },
                },
            }
        );
        var step = new QuestStep { TargetType = "item", TargetName = "Bread" };
        var quest = new QuestEntry
        {
            RequiredItems =
            [
                new RequiredItemInfo
                {
                    ItemName = "Bread",
                    Sources =
                    [
                        new ItemSource { SourceKey = "character:a rift vendor@" + StoneVendor },
                        new ItemSource { SourceKey = "character:shopkeeper" },
                    ],
                },
            ],
        };

        Assert.Equal("Reliquary", StepSceneResolver.ResolveScene(quest, step, data));
        Assert.Equal(
            "Stowaway",
            StepSceneResolver.ResolveScene(
                quest,
                step,
                data,
                isSourceAvailable: key => !key.Contains('@')
            )
        );
        Assert.False(
            StepSceneResolver.HasSourceInScene(
                quest,
                step,
                data,
                "Reliquary",
                isSourceAvailable: key => !key.Contains('@')
            )
        );
    }

    [Theory]
    [InlineData("L2", null)]
    [InlineData(null, StoneVendor)]
    [InlineData("L2", "item:furniture - missing")]
    [InlineData("Statue", StoneVendor)]
    public void Loading_rejects_incomplete_furnishing_spawns(string? slot, string? set)
    {
        var wrapper = new GuideWrapper
        {
            Version = 6,
            Quests = [],
            CharacterSpawns = new Dictionary<string, List<SpawnPoint>>
            {
                ["character:a rift vendor"] =
                [
                    new SpawnPoint
                    {
                        Scene = "Reliquary",
                        FurnitureSlot = slot,
                        FurnitureItemStableKey = set,
                    },
                ],
            },
            FurnitureSets = new Dictionary<string, FurnitureSetInfo>
            {
                [StoneVendor] = new() { DisplayName = "Stone Vendor Set" },
            },
        };

        Assert.Throws<InvalidDataException>(() => GuideData.FromWrapper(wrapper));
    }
}
