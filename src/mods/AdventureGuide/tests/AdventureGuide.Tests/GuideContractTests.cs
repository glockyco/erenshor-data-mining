using AdventureGuide.Data;

namespace AdventureGuide.Tests;

public sealed class GuideContractTests
{
    [Fact]
    public void Embedded_shipping_guide_contains_all_valid_workflows()
    {
        using var stream = typeof(GuideData).Assembly.GetManifestResourceStream(
            "AdventureGuide.quest-guide.json"
        );
        Assert.NotNull(stream);
        using var reader = new StreamReader(stream);

        var data = GuideData.Parse(reader.ReadToEnd());
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
