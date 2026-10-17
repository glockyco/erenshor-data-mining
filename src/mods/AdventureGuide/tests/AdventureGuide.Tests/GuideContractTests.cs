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
            Version = 8,
            Encounters = TestData.EmptyEncounters(),
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
                Version = 8,
                Encounters = TestData.EmptyEncounters(),
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
            Version = 8,
            Encounters = TestData.EmptyEncounters(),
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
            Version = 8,
            Encounters = TestData.EmptyEncounters(),
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
    public void Loading_rejects_unknown_json_atom_kinds()
    {
        const string json = """
            {
              "_version": 8,
              "_encounters": {"encounter_placements":[],"encounter_conditions":[],"encounter_completions":[],"encounter_event_conditions":[]},
              "_source_facts": {}, "_item_uses": {}, "_quest_state_keys": {},
              "_conditions": [
                [[{"kind": "unknown_kind", "ref": "GateQuest"}]]
              ],
              "quests": []
            }
            """;

        Assert.Throws<InvalidDataException>(() => GuideData.Parse(json));
    }

    [Theory]
    [InlineData("_source_facts", false)]
    [InlineData("_source_facts", true)]
    [InlineData("_item_uses", false)]
    [InlineData("_item_uses", true)]
    [InlineData("_quest_state_keys", false)]
    [InlineData("_quest_state_keys", true)]
    [InlineData("_zone_line_destination_contexts", false)]
    [InlineData("_zone_line_destination_contexts", true)]
    public void Loading_rejects_missing_or_null_required_source_contracts(
        string field,
        bool explicitNull
    )
    {
        var payload = Newtonsoft.Json.Linq.JObject.FromObject(
            TestData.NativeRequirements(("item:runner", null, [4]))
        );
        if (explicitNull)
            payload[field] = Newtonsoft.Json.Linq.JValue.CreateNull();
        else
            payload.Remove(field);

        Assert.Throws<Newtonsoft.Json.JsonSerializationException>(() =>
            GuideData.Parse(payload.ToString())
        );
    }

    [Fact]
    public void Native_slot_evidence_survives_json_loading_without_collapsing_slots()
    {
        var wrapper = TestData.NativeRequirements(("item:runner", "A", [1, 3]));
        var data = GuideData.Parse(Newtonsoft.Json.JsonConvert.SerializeObject(wrapper));
        var item = Assert.Single(Assert.Single(data.All).RequiredItems!);

        Assert.Equal(4, item.Quantity);
        Assert.Equal(new[] { "use:native:0", "use:native:1" }, item.UseKeys);
        Assert.Equal("A", item.VariantKey);
        Assert.Equal(2, data.ItemUses.Count);
        Assert.Equal("A", Assert.Single(data.All).Steps![0].RequirementVariant);
    }

    [Theory]
    [InlineData("missing_evidence")]
    [InlineData("empty_evidence")]
    [InlineData("unknown_slot")]
    [InlineData("duplicate_slot")]
    [InlineData("omitted_slot")]
    [InlineData("wrong_quest")]
    [InlineData("wrong_item")]
    [InlineData("wrong_variant")]
    [InlineData("wrong_kind")]
    [InlineData("wrong_quantity")]
    [InlineData("fractional_quantity")]
    [InlineData("unknown_quantity")]
    [InlineData("wrong_quality")]
    [InlineData("native_or_group")]
    [InlineData("step_or_group")]
    [InlineData("step_quantity")]
    [InlineData("step_variant")]
    [InlineData("missing_step")]
    public void Native_requirements_reject_missing_or_mismatched_slot_evidence(string defect)
    {
        var wrapper = TestData.NativeRequirements(("item:runner", "A", [1, 3]));
        var quest = wrapper.Quests![0];
        var item = quest.RequiredItems![0];
        var use = wrapper.ItemUses!["use:native:0"];
        switch (defect)
        {
            case "missing_evidence":
                item.UseKeys = null;
                break;
            case "empty_evidence":
                item.UseKeys = [];
                break;
            case "unknown_slot":
                item.UseKeys![0] = "use:missing";
                break;
            case "duplicate_slot":
                item.UseKeys![1] = item.UseKeys[0];
                break;
            case "omitted_slot":
                item.UseKeys!.RemoveAt(1);
                item.Quantity = 1;
                break;
            case "wrong_quest":
                use.TargetStableKey = "quest:other";
                break;
            case "wrong_item":
                use.ItemStableKey = "item:other";
                break;
            case "wrong_variant":
                use.VariantKey = "B";
                break;
            case "wrong_kind":
                use.Kind = "recipe_material";
                break;
            case "wrong_quantity":
                item.Quantity = 3;
                break;
            case "fractional_quantity":
                use.QuantityMin = use.QuantityMax = 0.5;
                break;
            case "unknown_quantity":
                use.QuantityMin = use.QuantityMax = null;
                break;
            case "wrong_quality":
                item.OutputQuality = "rare";
                break;
            case "native_or_group":
                item.OrGroup = "A";
                break;
            case "step_or_group":
                quest.Steps![0].OrGroup = "A";
                break;
            case "step_quantity":
                quest.Steps![0].Quantity = 1;
                break;
            case "step_variant":
                quest.Steps![0].RequirementVariant = "B";
                break;
            case "missing_step":
                quest.Steps!.RemoveAt(0);
                quest.Steps[0].Order = 1;
                break;
        }

        Assert.Throws<InvalidDataException>(() => GuideData.FromWrapper(wrapper));
    }

    [Fact]
    public void Stale_single_slot_json_is_not_accepted_as_an_authored_requirement()
    {
        var wrapper = TestData.NativeRequirements(("item:runner", null, [1, 3]));
        var json = Newtonsoft.Json.Linq.JObject.FromObject(wrapper);
        var item = (Newtonsoft.Json.Linq.JObject)json["quests"]![0]!["required_items"]![0]!;
        item.Remove("use_keys");
        item["use_key"] = "use:native:0";
        json["_item_uses"] = new Newtonsoft.Json.Linq.JObject();

        Assert.Throws<Newtonsoft.Json.JsonSerializationException>(() =>
            GuideData.Parse(json.ToString())
        );
    }

    [Fact]
    public void Null_variant_native_requirements_still_require_slot_evidence()
    {
        var wrapper = TestData.NativeRequirements(("item:runner", null, [1, 3]));
        wrapper.Quests![0].RequiredItems![0].UseKeys = null;

        Assert.Throws<InvalidDataException>(() => GuideData.FromWrapper(wrapper));
    }

    [Fact]
    public void Native_slot_coverage_rejects_omitting_the_whole_requirement()
    {
        var wrapper = TestData.NativeRequirements(("item:runner", null, [1, 3]));
        wrapper.Quests![0].RequiredItems = [];

        Assert.Throws<InvalidDataException>(() => GuideData.FromWrapper(wrapper));
    }

    [Fact]
    public void Native_bundles_cannot_reappear_after_another_bundle()
    {
        var wrapper = TestData.NativeRequirements(
            ("item:a", "A", [1]),
            ("item:b", "B", [1]),
            ("item:c", "A", [1])
        );

        Assert.Throws<InvalidDataException>(() => GuideData.FromWrapper(wrapper));
    }

    [Fact]
    public void Quality_specific_native_rows_keep_distinct_slot_and_source_identity()
    {
        var wrapper = TestData.NativeRequirements(
            ("item:runner", "A", [1]),
            ("item:runner", "A", [3])
        );
        var quest = wrapper.Quests![0];
        quest.RequiredItems![1].OutputQuality = "rare";
        quest.Steps![1].OutputQuality = "rare";
        wrapper
            .ItemUses!["use:native:1"]
            .Conditions.Add(
                new SourceCondition
                {
                    Predicate = "quality",
                    Phase = "operation_input",
                    Value = "rare",
                    Actor = "player",
                    Scope = "use:native:1",
                    GateKey = "quality",
                }
            );
        var ordinary = new ItemSource { Type = "drop", SourceKey = "ordinary" };
        var rare = new ItemSource { Type = "drop", SourceKey = "rare" };
        quest.RequiredItems[0].Sources = [ordinary];
        quest.RequiredItems[1].Sources = [rare];
        GuideData.FromWrapper(wrapper);

        Assert.Same(ordinary, Assert.Single(ItemSourcePolicy.SourcesFor(quest, quest.Steps[0])!));
        Assert.Same(rare, Assert.Single(ItemSourcePolicy.SourcesFor(quest, quest.Steps[1])!));
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
