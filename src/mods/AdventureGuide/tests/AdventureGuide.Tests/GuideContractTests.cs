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

            Assert.Equal(206, data.Count);
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
            Version = 6,
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
                        RequiredQuestDBNames = ["GateQuest"],
                    },
                ],
            },
        ];
        var wrapper = new GuideWrapper
        {
            Version = 6,
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
              "_version": 6,
              "_character_spawns": {
                "character:test": [
                  {
                    "scene": "TestScene",
                    "x": 1.5,
                    "y": 2.5,
                    "z": 3.5,
                    "spawn_upon_quest_complete_stable_key": "quest:gate",
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

        Assert.Equal("quest:gate", spawn.SpawnUponQuestCompleteStableKey);
        Assert.True(spawn.IsDirectlyPlaced);
        Assert.Equal("TestSpawnScript", spawn.SourceScript);
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
