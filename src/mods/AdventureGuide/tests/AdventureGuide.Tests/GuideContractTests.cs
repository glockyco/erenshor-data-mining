using AdventureGuide.Data;

namespace AdventureGuide.Tests;

public sealed class GuideContractTests
{
    [Fact]
    public void Embedded_shipping_guide_contains_all_valid_workflows()
    {
        string tempDirectory = Path.Combine(
            Path.GetTempPath(),
            $"AdventureGuide.Tests-{Guid.NewGuid():N}"
        );
        Directory.CreateDirectory(tempDirectory);

        try
        {
            string guidePath = Path.Combine(tempDirectory, "AdventureGuide.quest-guide.json");
            using var stream = typeof(GuideData).Assembly.GetManifestResourceStream(
                "AdventureGuide.quest-guide.json"
            );
            Assert.NotNull(stream);
            using (var file = File.Create(guidePath))
            {
                stream.CopyTo(file);
            }

            var data = GuideData.Parse(File.ReadAllText(guidePath));
            var workflows = data.All.Where(quest => quest.IsGuideOnly).ToList();

            Assert.Equal(200, data.Count);
            Assert.Equal(10, workflows.Count);
            Assert.All(
                workflows,
                quest =>
                {
                    Assert.True(quest.Flags?.Repeatable);
                    Assert.NotNull(quest.WorkflowCycle);
                }
            );
            Assert.Contains(workflows, quest => quest.DisplayName == "Demented Malaroth");
            Assert.Contains(workflows, quest => quest.DisplayName == "Shivunax");
            // The dead Reliquary portal quests are excluded, not stubbed.
            Assert.False(data.ShouldStubUnknownQuest("RELIQ-HIDDEN"));
            Assert.False(data.ShouldStubUnknownQuest("AmethiKeys"));
            for (int round = 1; round <= 8; round++)
            {
                string expected = $"Vitheo's arena - Round {round}";
                Assert.Contains(workflows, quest => quest.DisplayName == expected);
            }
        }
        finally
        {
            Directory.Delete(tempDirectory, recursive: true);
        }
    }

    [Fact]
    public void Validation_rejects_cross_namespace_quest_identity_collisions()
    {
        var wrapper = new GuideWrapper
        {
            Version = 7,
            Quests =
            [
                OrdinaryQuest("quest:first", "FirstDB"),
                OrdinaryQuest("FirstDB", "SecondDB"),
            ],
        };

        var error = Assert.Throws<InvalidDataException>(() => GuideData.ValidateWrapper(wrapper));
        Assert.Contains("identity collides", error.Message);
    }

    [Fact]
    public void Unknown_quests_are_stubbed_unless_excluded_or_known()
    {
        var data = GuideData.FromWrapper(
            new GuideWrapper
            {
                Version = 7,
                Quests = [OrdinaryQuest("quest:known", "KnownDB")],
                ExcludedQuests = ["PlaceholderDB"],
            }
        );

        // A quest a game update adds still shows up before the guide catches up.
        Assert.True(data.ShouldStubUnknownQuest("AddedByUpdateDB"));
        Assert.False(data.ShouldStubUnknownQuest("placeholderdb"));
        Assert.False(data.ShouldStubUnknownQuest("KnownDB"));
    }

    [Fact]
    public void Validation_rejects_a_quest_both_excluded_and_in_the_guide()
    {
        var wrapper = new GuideWrapper
        {
            Version = 7,
            Quests = [OrdinaryQuest("quest:known", "KnownDB")],
            ExcludedQuests = ["KnownDB"],
        };

        Assert.Throws<InvalidDataException>(() => GuideData.ValidateWrapper(wrapper));
    }

    [Fact]
    public void Vendor_instruction_is_generic_and_seller_gate_is_structured()
    {
        var workflow = TestData.WorkflowQuest();
        workflow.RequiredItems =
        [
            new RequiredItemInfo
            {
                ItemName = "Test Token",
                ItemStableKey = "item:test token",
                Sources =
                [
                    new ItemSource
                    {
                        Type = "vendor",
                        Name = "Seller",
                        SourceKey = "character:seller",
                        Instruction = "Buy Test Token.",
                        Condition = 0,
                    },
                ],
            },
        ];
        var wrapper = new GuideWrapper
        {
            Version = 7,
            Conditions =
            [
                [
                    [new GateAtom { Kind = GateAtomKind.QuestDone, Ref = "GateQuest" }],
                ],
            ],
            Quests = [OrdinaryQuest("quest:gate", "GateQuest"), workflow],
        };

        GuideData.ValidateWrapper(wrapper);

        workflow.RequiredItems[0].Sources![0].Instruction = "Buy Test Token from Seller.";
        Assert.Throws<InvalidDataException>(() => GuideData.ValidateWrapper(wrapper));
    }

    [Fact]
    public void Spawn_metadata_parses_direct_placement_and_respawn_fields()
    {
        const string json = """
            {
              "_version": 7,
              "_conditions": [
                [[{"kind": "quest_done", "ref": "GateQuest"}]]
              ],
              "_character_spawns": {
                "character:test": [
                  {
                    "scene": "TestScene",
                    "x": 1.5,
                    "y": 2.5,
                    "z": 3.5,
                    "condition": 0,
                    "is_directly_placed": true,
                    "source_script": "TestSpawnScript"
                  }
                ]
              },
              "quests": [
                {
                  "stable_key": "quest:gate",
                  "db_name": "GateQuest",
                  "display_name": "Gate quest"
                }
              ]
            }
            """;

        var data = GuideData.Parse(json);
        var spawn = Assert.Single(data.CharacterSpawns["character:test"]);

        Assert.Equal(0, spawn.Condition);
        var atom = Assert.Single(Assert.Single(Assert.Single(data.Conditions)));
        Assert.Equal(GateAtomKind.QuestDone, atom.Kind);
        Assert.Equal("GateQuest", atom.Ref);
        Assert.True(spawn.IsDirectlyPlaced);
        Assert.Equal("TestSpawnScript", spawn.SourceScript);
    }

    [Fact]
    public void Loading_rejects_unknown_json_atom_kinds()
    {
        const string json = """
            {
              "_version": 7,
              "_conditions": [
                [[{"kind": "unknown_kind", "ref": "GateQuest"}]]
              ],
              "quests": []
            }
            """;

        Assert.Throws<InvalidDataException>(() => GuideData.Parse(json));
    }

    private static QuestEntry OrdinaryQuest(
        string stableKey,
        string dbName,
        bool repeatable = false
    ) =>
        new()
        {
            StableKey = stableKey,
            DBName = dbName,
            DisplayName = dbName,
            Flags = new QuestFlags { Repeatable = repeatable },
        };
}
