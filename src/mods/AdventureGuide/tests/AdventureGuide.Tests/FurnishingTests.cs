using AdventureGuide.Data;
using AdventureGuide.State;

namespace AdventureGuide.Tests;

public sealed class FurnishingTests
{
    private const string StoneVendor = "item:furniture - stone vendor";

    [Fact]
    public void A_furnishing_requires_its_set_in_its_specific_room()
    {
        var data = GuideData.FromWrapper(
            new GuideWrapper
            {
                Version = 7,
                Quests = [],
                Conditions =
                [
                    [
                        [
                            new GateAtom
                            {
                                Kind = GateAtomKind.RoomFurnished,
                                Ref = StoneVendor,
                                Slot = "L2",
                            },
                        ],
                    ],
                ],
                GateItems = new()
                {
                    [StoneVendor] = new GateItem { Name = "Stone Vendor Set", GameId = "stone" },
                },
            }
        );
        var facts = new GateTestFacts();
        var gates = new GateConditions(data, facts);
        var spawn = new SpawnPoint { Scene = "Reliquary", Condition = 0 };

        Assert.False(gates.IsSpawnAvailable(spawn));
        facts.Rooms["L1"] = StoneVendor;
        Assert.False(gates.IsSpawnAvailable(spawn));
        facts.Rooms["L2"] = "item:furniture - wood vendor";
        Assert.False(gates.IsSpawnAvailable(spawn));
        facts.Rooms["L2"] = StoneVendor;
        Assert.True(gates.IsSpawnAvailable(spawn));
        Assert.True(gates.IsSpawnAvailable(new SpawnPoint { Scene = "Hidden" }));
    }

    [Fact]
    public void Scene_resolution_skips_a_source_without_a_furnished_placement()
    {
        var data = GuideData.FromWrapper(
            new GuideWrapper
            {
                Version = 7,
                Quests = [],
                Conditions =
                [
                    [
                        [
                            new GateAtom
                            {
                                Kind = GateAtomKind.RoomFurnished,
                                Ref = StoneVendor,
                                Slot = "L1",
                            },
                        ],
                    ],
                ],
                GateItems = new()
                {
                    [StoneVendor] = new GateItem { Name = "Stone Vendor Set", GameId = "stone" },
                },
                CharacterSpawns = new()
                {
                    ["character:vendor"] = [new SpawnPoint { Scene = "Reliquary", Condition = 0 }],
                    ["character:shopkeeper"] = [new SpawnPoint { Scene = "Stowaway" }],
                },
            }
        );
        var gates = new GateConditions(data, new GateTestFacts());
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
                        new ItemSource { SourceKey = "character:vendor" },
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
                isSourceAvailable: gates.IsSourceAvailable
            )
        );
        Assert.False(
            StepSceneResolver.HasSourceInScene(
                quest,
                step,
                data,
                "Reliquary",
                isSourceAvailable: gates.IsSourceAvailable
            )
        );
    }

    [Theory]
    [InlineData(null)]
    [InlineData("Statue")]
    public void Loading_rejects_unknown_room_slots(string? slot)
    {
        var wrapper = new GuideWrapper
        {
            Version = 7,
            Quests = [],
            Conditions =
            [
                [
                    [
                        new GateAtom
                        {
                            Kind = GateAtomKind.RoomFurnished,
                            Ref = StoneVendor,
                            Slot = slot,
                        },
                    ],
                ],
            ],
            GateItems = new() { [StoneVendor] = new GateItem { GameId = "stone" } },
        };

        Assert.Throws<InvalidDataException>(() => GuideData.FromWrapper(wrapper));
    }
}
