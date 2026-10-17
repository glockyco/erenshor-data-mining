using AdventureGuide.Data;
using AdventureGuide.State;

namespace AdventureGuide.Tests;

[Collection("Game state")]
public sealed class FurnishingTests
{
    private const string StoneVendor = "item:furniture - stone vendor";

    [Fact]
    public void Stored_slot_mirror_polls_all_rooms_planar_stones_and_runes_without_warm_allocation()
    {
        var table = new PlanningTableUI();
        var inventory = new PlanningInventory();
        GameData.PlanningUI = table;
        GameData.PlayerInv = inventory;
        try
        {
            string[] slots =
            [
                "L1",
                "L2",
                "L3",
                "L4",
                "R1",
                "R2",
                "R3",
                "R4",
                "PlanarFern",
                "PlanarBrax",
                "PlanarVith",
                "PlanarSol",
                "Rune1",
                "Rune2",
                "Rune3",
                "Rune4",
                "Rune5",
                "Rune6",
            ];
            var mirror = new ReliquaryFurnishings();
            Assert.False(mirror.Poll());
            foreach (string slot in slots)
            {
                Assert.Equal(
                    !FurnishingPolicy.IsRoomSlot(slot),
                    FurnishingPolicy.IsPlanningSlot(slot)
                );
                Assert.Null(mirror.ItemKeyIn(slot));
                var icon = (ItemIcon)typeof(PlanningTableUI).GetField(slot)!.GetValue(table)!;
                icon.MyItem = new Item { name = " Stored " + slot + " " };
                Assert.True(mirror.Poll());
                Assert.Equal("item:stored " + slot.ToLowerInvariant(), mirror.ItemKeyIn(slot));
                Assert.False(mirror.Poll());
                icon.MyItem = new Item { name = "Replacement" };
                Assert.True(mirror.Poll());
                Assert.Equal("item:replacement", mirror.ItemKeyIn(slot));
                icon.MyItem = inventory.Empty;
                Assert.True(mirror.Poll());
                Assert.Null(mirror.ItemKeyIn(slot));
                icon.MyItem = null;
                Assert.True(mirror.Poll());
                Assert.Null(mirror.ItemKeyIn(slot));
            }
            Assert.Null(mirror.ItemKeyIn("unknown"));
            Assert.False(FurnishingPolicy.IsPlanningSlot("unknown"));
            table.Rune6.MyItem = new Item { name = "Rune" };
            Assert.True(mirror.Poll());
            for (int i = 0; i < 100; i++)
                mirror.Poll();
            long before = GC.GetAllocatedBytesForCurrentThread();
            bool changed = false;
            for (int i = 0; i < 1000; i++)
                changed |= mirror.Poll();
            long allocated = GC.GetAllocatedBytesForCurrentThread() - before;
            Assert.False(changed);
            Assert.Equal(0L, allocated);
            GameData.PlanningUI = null;
            Assert.True(mirror.Poll());
            Assert.Null(mirror.ItemKeyIn("Rune6"));
            Assert.False(mirror.Poll());
        }
        finally
        {
            GameData.PlanningUI = null;
            GameData.PlayerInv = null;
        }
    }

    [Fact]
    public void A_furnishing_requires_its_set_in_its_specific_room()
    {
        var data = GuideData.FromWrapper(
            new GuideWrapper
            {
                Version = 8,
                Encounters = TestData.EmptyEncounters(),
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
        facts.Rooms["PlanarFern"] = StoneVendor;
        facts.Rooms["Rune1"] = StoneVendor;
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
                Version = 8,
                Encounters = TestData.EmptyEncounters(),
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
    public void Loading_rejects_unknown_room_slots(string? slot)
    {
        var wrapper = new GuideWrapper
        {
            Version = 8,
            Encounters = TestData.EmptyEncounters(),
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
