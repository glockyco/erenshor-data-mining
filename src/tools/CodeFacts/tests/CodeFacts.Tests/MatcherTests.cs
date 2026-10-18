using System.Text.Json;
using FixtureLib;
using ICSharpCode.Decompiler;
using ICSharpCode.Decompiler.CSharp;
using ICSharpCode.Decompiler.CSharp.Syntax;
using ICSharpCode.Decompiler.Metadata;
using ICSharpCode.Decompiler.TypeSystem;
using Xunit;

namespace CodeFacts.Tests;

public sealed class MatcherTests
{
    private const string DamageFixture = "FixtureLib.FixtureDamageRelease";

    private const string EntryFixture = "FixtureLib.FixtureEntryState";

    [Theory]
    [InlineData("Play")]
    [InlineData("PlayAlternate")]
    public void StatementOrder_binds_each_compiled_entry_path(string method)
    {
        Assert.Empty(Matchers.StatementOrder(Method(method, EntryFixture), EntryOrderFact(method)));
        var result = RunFacts(EntryOrderFact(method));
        Assert.Empty(result.Errors);
        Assert.True(Assert.Single(result.Facts).AssertOk);
    }

    [Theory]
    [InlineData("Reversed")]
    [InlineData("MissingLoad")]
    [InlineData("MissingEntry")]
    [InlineData("DuplicateLoad")]
    [InlineData("DuplicateEntry")]
    [InlineData("ConditionalLoad")]
    [InlineData("ConditionalEntry")]
    [InlineData("NestedDuplicateLoad")]
    [InlineData("NestedDuplicateEntry")]
    [InlineData("LambdaDuplicateLoad")]
    public void StatementOrder_rejects_changed_entry_behavior(string method)
    {
        Assert.Throws<InvalidDataException>(() =>
            Matchers.StatementOrder(Method(method, EntryFixture), EntryOrderFact(method))
        );
        var result = RunFacts(EntryOrderFact(method));
        Assert.Empty(result.Facts);
        Assert.Single(result.Errors);
    }

    [Fact]
    public void StatementOrder_requires_a_method_body()
    {
        Assert.Throws<InvalidDataException>(() =>
            Matchers.StatementOrder(new MethodDeclaration(), EntryOrderFact("Play"))
        );
        Assert.Throws<InvalidDataException>(() =>
            Matchers.StatementOrder(new FieldDeclaration(), EntryOrderFact("Play"))
        );
    }

    [Fact]
    public void StatementOrder_normalizes_whitespace_without_changing_statement_identity()
    {
        var fact = EntryOrderFact("Play");
        Assert.Empty(
            Matchers.StatementOrder(
                Method("Play", EntryFixture),
                fact with
                {
                    Args = new()
                    {
                        ["before"] = "  GameData.GM.LoadReliquary  ();\n",
                        ["after"] = "GameData.InCharSelect   =\n false;",
                    },
                }
            )
        );
        Assert.Throws<InvalidDataException>(() =>
            Matchers.StatementOrder(
                Method("Play", EntryFixture),
                fact with
                {
                    Args = new(fact.Args) { ["before"] = fact.Args["after"] },
                }
            )
        );
    }

    private static FactSpec EntryOrderFact(string method) =>
        Fact(
            "fixture.entry." + method,
            "assert",
            method,
            "statement_order",
            new()
            {
                ["before"] = "GameData.GM.LoadReliquary ();",
                ["after"] = "GameData.InCharSelect = false;",
            },
            null,
            EntryFixture
        );

    [Fact]
    public void ForeachSource_pins_membership_without_pinning_the_loop_body()
    {
        var method = Method("IteratePool");
        var fact = Fact(
            "fixture.authored",
            "assert",
            "M",
            "foreach_source",
            new() { ["source"] = "PoolA" },
            []
        );
        Assert.Empty(Matchers.ForeachSource(method, fact));
        Assert.Throws<InvalidDataException>(() =>
            Matchers.ForeachSource(method, fact with { Args = new() { ["source"] = "NamePool" } })
        );
        var duplicate = Method("IteratePoolTwice");
        Assert.Throws<InvalidDataException>(() => Matchers.ForeachSource(duplicate, fact));
    }

    [Theory]
    [InlineData("ProtectorReleaseChangedActivity")]
    [InlineData("ProtectorReleaseChangedNull")]
    public void NodeShape_pins_protector_null_and_self_activity(string changedMethod)
    {
        var fact = Fact(
            "fixture.protector_release",
            "assert",
            "ProtectorRelease",
            "node_shape",
            new()
            {
                ["kind"] = "BlockStatement",
                ["shape"] =
                    "{ if (Protector != null && Protector.ActiveSelf) { Invulnerable = true; } else { Invulnerable = false; } }",
            },
            null,
            DamageFixture
        );

        Assert.Empty(Matchers.NodeShape(Method("ProtectorRelease", DamageFixture), fact));
        Assert.Throws<InvalidDataException>(() =>
            Matchers.NodeShape(Method(changedMethod, DamageFixture), fact)
        );
    }

    [Fact]
    public void NodeShape_pins_weather_last_write_order()
    {
        var fact = Fact(
            "fixture.weather_release",
            "assert",
            "WeatherRelease",
            "node_shape",
            new()
            {
                ["kind"] = "BlockStatement",
                ["shape"] =
                    "{ foreach (FixtureDamageRelease dryTarget in DryTargets) { dryTarget.ActiveSelf = false; } foreach (FixtureDamageRelease wetTarget in WetTargets) { wetTarget.ActiveSelf = true; } }",
            },
            null,
            DamageFixture
        );

        Assert.Empty(Matchers.NodeShape(Method("WeatherRelease", DamageFixture), fact));
        Assert.Throws<InvalidDataException>(() =>
            Matchers.NodeShape(Method("WeatherReleaseChangedOrder", DamageFixture), fact)
        );
    }

    [Fact]
    public void NodeShape_pins_actual_trade_holder_not_dialog_quest_collection()
    {
        var fact = Fact(
            "fixture.trade_release",
            "assert",
            "TradeRelease",
            "node_shape",
            new()
            {
                ["kind"] = "BlockStatement",
                ["shape"] =
                    "{ foreach (FixtureDamageRelease quest in Holder.Quests) { if (quest.DropInvulnOnHolder) { Holder.Invulnerable = false; } } }",
            },
            null,
            DamageFixture
        );

        Assert.Empty(Matchers.NodeShape(Method("TradeRelease", DamageFixture), fact));
        Assert.Throws<InvalidDataException>(() =>
            Matchers.NodeShape(Method("TradeReleaseChangedHolder", DamageFixture), fact)
        );
    }

    [Fact]
    public void NodeShape_pins_health_loss_before_phase_release_timer()
    {
        var fact = Fact(
            "fixture.health_phase_release",
            "assert",
            "HealthPhaseRelease",
            "node_shape",
            new()
            {
                ["kind"] = "BlockStatement",
                ["shape"] =
                    "{ if (CurrentHP < ShiftAtLife) { PhaseDelay = 200f; } if (PhaseDelay > 0f) { PhaseDelay--; if (PhaseDelay <= 0f) { Invulnerable = false; } } }",
            },
            null,
            DamageFixture
        );

        Assert.Empty(Matchers.NodeShape(Method("HealthPhaseRelease", DamageFixture), fact));
        Assert.Throws<InvalidDataException>(() =>
            Matchers.NodeShape(Method("HealthPhaseReleaseChangedBootstrap", DamageFixture), fact)
        );
    }

    [Fact]
    public void NodeShape_pins_gate_literal_and_activation_together()
    {
        var fact = Fact(
            "fixture.shiver_gate",
            "assert",
            "ShiverGate",
            "node_shape",
            new()
            {
                ["kind"] = "IfElseStatement",
                ["shape"] =
                    "if (!active && Drops.Contains (\"SHIVER-GLASSES\")) { SingletonB = \"visible\"; }",
            },
            null
        );

        Assert.Empty(Matchers.NodeShape(Method("ShiverGate"), fact));
        Assert.Throws<InvalidDataException>(() =>
            Matchers.NodeShape(Method("ShiverGateChangedLiteral"), fact)
        );
        Assert.Throws<InvalidDataException>(() =>
            Matchers.NodeShape(Method("ShiverGateChangedActivation"), fact)
        );
    }

    [Fact]
    public void NodeShape_pins_independent_reset_branches_and_their_order()
    {
        var fact = Fact(
            "fixture.shiver_reset",
            "assert",
            "ShiverReset",
            "node_shape",
            new()
            {
                ["kind"] = "BlockStatement",
                ["shape"] =
                    "{ if (Drops.Contains (\"SHIVER-TORCH\")) { Level = 2; } if (Drops.Contains (\"SHIVER-FLAMELIT\")) { Level = 3; } }",
            },
            null
        );

        Assert.Empty(Matchers.NodeShape(Method("ShiverReset"), fact));
        Assert.Throws<InvalidDataException>(() =>
            Matchers.NodeShape(Method("ShiverResetChangedBranching"), fact)
        );
    }

    [Fact]
    public void GuardedMemberRoll_binds_fixture_pool_and_singleton_values()
    {
        var pool = Matchers.GuardedMemberRoll(
            Method("Init"),
            Fact(
                "fixture.pool_a",
                "extract",
                "Init",
                "guarded_member_roll",
                new() { ["member"] = "PoolA" },
                ["rate", "min_level"]
            )
        );
        var singleton = Matchers.GuardedMemberRoll(
            Method("Init"),
            Fact(
                "fixture.singleton_b",
                "extract",
                "Init",
                "guarded_member_roll",
                new() { ["member"] = "SingletonB" },
                ["rate", "min_level"]
            )
        );

        Assert.Equal(
            new Dictionary<string, string> { ["rate"] = "0.005", ["min_level"] = "0" },
            pool
        );
        Assert.Equal(
            new Dictionary<string, string> { ["rate"] = "0.0125", ["min_level"] = "20" },
            singleton
        );
    }

    [Fact]
    public void StringConstants_binds_fixture_combine_ids()
    {
        var result = Matchers.StringConstants(
            Method("Combine"),
            Fact("fixture.combine_ids", "extract", "Combine", "string_constants", [], ["strings"])
        );

        Assert.Equal(new Dictionary<string, string> { ["strings"] = "31377423,46289586" }, result);
    }

    [Theory]
    [InlineData("SingletonB", "strings")]
    [InlineData("  SingletonB \n ", "classes")]
    public void StringConstants_extracts_closed_switch_labels_in_source_order(
        string expression,
        string key
    )
    {
        var fact = Fact(
            "fixture.switch_strings",
            "extract",
            "SwitchStrings",
            "string_constants",
            new() { ["switch"] = expression },
            [key]
        );
        Assert.Equal(
            "Zeta,Alpha,Beta",
            Matchers.StringConstants(Method("SwitchStrings"), fact)[key]
        );
        var result = RunFacts(fact);
        Assert.Empty(result.Errors);
        Assert.Equal("Zeta,Alpha,Beta", Assert.Single(result.Facts).Values![key]);
    }

    [Theory]
    [InlineData("SwitchMissing", "SingletonB", "bound 0 times")]
    [InlineData("SwitchDuplicate", "SingletonB", "bound 2 times")]
    [InlineData("SwitchNonString", "Level", "non-string literal label")]
    [InlineData("SwitchDefault", "SingletonB", "default label")]
    public void StringConstants_rejects_switches_that_do_not_define_one_closed_string_set(
        string method,
        string expression,
        string cause
    )
    {
        var fact = Fact(
            "fixture.invalid_switch",
            "extract",
            method,
            "string_constants",
            new() { ["switch"] = expression },
            ["strings"]
        );
        var error = Assert.Throws<InvalidDataException>(() =>
            Matchers.StringConstants(Method(method), fact)
        );
        Assert.Contains(cause, error.Message);
        var result = RunFacts(fact);
        Assert.Empty(result.Facts);
        Assert.Contains(cause, Assert.Single(result.Errors));
    }

    [Fact]
    public void IntComparisons_binds_fixture_auction_envelope()
    {
        var result = Matchers.IntComparisons(
            Method("Auctionable"),
            Fact(
                "fixture.auction_envelope",
                "extract",
                "Auctionable",
                "int_comparisons",
                new() { ["level"] = "level", ["value"] = "value" },
                ["level", "value"]
            )
        );

        Assert.Equal(
            new Dictionary<string, string> { ["level"] = "> 0,< 40", ["value"] = "> 0" },
            result
        );
    }

    [Fact]
    public void IntExpression_extracts_one_bound_and_rejects_ambiguous_values()
    {
        var bound = Fact(
            "fixture.cap",
            "extract",
            "Auctionable",
            "int_expression",
            new() { ["left"] = "level", ["operator"] = "<" },
            ["value"]
        );
        Assert.Equal("40", Matchers.IntExpression(Method("Auctionable"), bound)["value"]);
        var missing = bound with
        {
            Args = new() { ["left"] = "missing", ["operator"] = "<" },
        };
        Assert.Throws<InvalidDataException>(() =>
            Matchers.IntExpression(Method("Auctionable"), missing)
        );
        var method = Method("AmbiguousBounds");
        Assert.Throws<InvalidDataException>(() => Matchers.IntExpression(method, bound));
    }

    [Fact]
    public void IntExpression_scopes_relative_offsets_to_the_named_draw()
    {
        var method = Method("OffsetDraw");
        var fact = Fact(
            "fixture.offset",
            "extract",
            "M",
            "int_expression",
            new()
            {
                ["left"] = "stats.Level",
                ["operator"] = "+",
                ["within_draw"] = "empty",
            },
            ["value"]
        );
        Assert.Equal("3", Matchers.IntExpression(method, fact)["value"]);
    }

    [Fact]
    public void StringConstants_scopes_names_to_the_assignment_guard()
    {
        var method = Method("BrokerNames");
        var fact = Fact(
            "fixture.brokers",
            "extract",
            "M",
            "string_constants",
            new() { ["guard_assignment"] = "isAuctionHouse" },
            ["strings"]
        );
        Assert.Equal("Broker A,Broker B", Matchers.StringConstants(method, fact)["strings"]);
    }

    [Theory]
    [InlineData("AssignString", "SingletonB", true)]
    [InlineData("AssignString", "Missing", false)]
    [InlineData("AssignStringTwice", "SingletonB", false)]
    [InlineData("AssignNonliteral", "SingletonB", false)]
    public void StringConstants_extracts_one_literal_member_assignment(
        string method,
        string member,
        bool valid
    )
    {
        var fact = Fact(
            "fixture.assignment",
            "extract",
            method,
            "string_constants",
            new() { ["assignment"] = member },
            ["string"]
        );
        if (valid)
            Assert.Equal("start,scene", Matchers.StringConstants(Method(method), fact)["string"]);
        else
            Assert.Throws<InvalidDataException>(() =>
                Matchers.StringConstants(Method(method), fact)
            );
    }

    [Theory]
    [InlineData("InvokeString", "invocation", "Drops.Add", "0", "called")]
    [InlineData("CreateString", "creation", "Version", "0", "1.2")]
    [InlineData("InvokeSecondString", "invocation", "Drops.Insert", "1", "inserted")]
    [InlineData("InvokeSecondString", "invocation", "Drops.Insert", "0", null)]
    [InlineData("CreateSecondString", "creation", "KeyValuePair<int, string>", "1", "created")]
    [InlineData("CreateSecondString", "creation", "KeyValuePair<int, string>", "0", null)]
    [InlineData("InvokeString", "invocation", "Missing", "0", null)]
    [InlineData("CreateString", "creation", "Missing", "0", null)]
    [InlineData("InvokeStringTwice", "invocation", "Drops.Add", "0", null)]
    [InlineData("CreateStringTwice", "creation", "Version", "0", null)]
    [InlineData("InvokeNonliteral", "invocation", "Drops.Add", "0", null)]
    [InlineData("CreateNonliteral", "creation", "Version", "0", null)]
    [InlineData("InvokeString", "invocation", "Drops.Add", "1", null)]
    [InlineData("CreateString", "creation", "Version", "-1", null)]
    public void StringConstants_extracts_one_literal_call_argument(
        string method,
        string selector,
        string target,
        string position,
        string? expected
    )
    {
        var fact = Fact(
            "fixture.argument",
            "extract",
            method,
            "string_constants",
            new() { [selector] = target, ["argument"] = position },
            ["string"]
        );
        if (expected is not null)
            Assert.Equal(expected, Matchers.StringConstants(Method(method), fact)["string"]);
        else
            Assert.Throws<InvalidDataException>(() =>
                Matchers.StringConstants(Method(method), fact)
            );
    }

    [Fact]
    public void IntExpression_top_level_ignores_nested_level_thresholds()
    {
        var method = Method("LevelCap");
        var fact = Fact(
            "fixture.cap",
            "extract",
            "M",
            "int_expression",
            new()
            {
                ["left"] = "level",
                ["operator"] = "<",
                ["top_level"] = "true",
            },
            ["value"]
        );
        Assert.Equal("35", Matchers.IntExpression(method, fact)["value"]);
    }

    [Fact]
    public void BranchShape_pins_false_branch_and_rejects_changed_destination()
    {
        var method = Method("Storage");
        var fact = Fact(
            "fixture.storage",
            "assert",
            "M",
            "branch_shape",
            new()
            {
                ["condition"] = "compatible",
                ["branch"] = "false",
                ["shape"] = "{ SingletonB = \"stored\"; }",
            },
            null
        );
        Assert.Empty(Matchers.BranchShape(method, fact));
        var changed = fact with { Args = new(fact.Args) { ["shape"] = "{ Discard (item); }" } };
        Assert.Throws<InvalidDataException>(() => Matchers.BranchShape(method, changed));
    }

    [Fact]
    public void StatementShape_binds_fixture_guarantee_statement()
    {
        var result = Matchers.StatementShape(
            Method("GuaranteeLike"),
            Fact(
                "fixture.guarantee_shape",
                "assert",
                "GuaranteeLike",
                "statement_shape",
                new() { ["statement"] = "Drops.Add (PoolA [Rng.Next (0, PoolA.Count)]);" },
                null
            )
        );

        Assert.Empty(result);
    }

    [Fact]
    public void NodeShape_binds_fixture_guarantee_retry_loop()
    {
        const string shape =
            "for (int i = 0; i < numberOfGuaranteedDrops; i++) { string text = null; int num = 0; do { text = PoolA [Rng.Next (0, PoolA.Count)]; num++; } while (num < 10 && (text == null || Drops.Contains (text))); if (text != null) { Drops.Add (text); } }";
        var result = Matchers.NodeShape(
            Method("GuaranteeRetryLike"),
            Fact(
                "fixture.guarantee_retry_loop",
                "assert",
                "GuaranteeRetryLike",
                "node_shape",
                new() { ["kind"] = "ForStatement", ["shape"] = shape },
                null
            )
        );

        Assert.Empty(result);
    }

    [Fact]
    public void StringSet_binds_fixture_trigger_strings()
    {
        var result = Matchers.StringSet(
            Method("Combine"),
            Fact(
                "fixture.trigger_strings",
                "assert",
                "Combine",
                "string_set",
                new() { ["strings"] = "31377423,46289586" },
                null
            )
        );

        Assert.Empty(result);
    }

    [Fact]
    public void GuardedMemberRoll_rejects_unmatched_member()
    {
        Assert.Throws<InvalidDataException>(() =>
            Matchers.GuardedMemberRoll(
                Method("Init"),
                Fact(
                    "invalid.member",
                    "extract",
                    "Init",
                    "guarded_member_roll",
                    new() { ["member"] = "MissingPool" },
                    ["rate", "min_level"]
                )
            )
        );
    }

    [Fact]
    public void StringConstants_rejects_method_without_comparisons()
    {
        Assert.Throws<InvalidDataException>(() =>
            Matchers.StringConstants(
                Method("GuaranteeLike"),
                Fact(
                    "invalid.strings",
                    "extract",
                    "GuaranteeLike",
                    "string_constants",
                    [],
                    ["strings"]
                )
            )
        );
    }

    [Fact]
    public void IntComparisons_rejects_missing_comparison_member()
    {
        Assert.Throws<InvalidDataException>(() =>
            Matchers.IntComparisons(
                Method("Auctionable"),
                Fact(
                    "invalid.comparison",
                    "extract",
                    "Auctionable",
                    "int_comparisons",
                    new() { ["missing"] = "missing" },
                    ["missing"]
                )
            )
        );
    }

    [Fact]
    public void StatementShape_rejects_wrong_statement()
    {
        Assert.Throws<InvalidDataException>(() =>
            Matchers.StatementShape(
                Method("GuaranteeLike"),
                Fact(
                    "invalid.statement",
                    "assert",
                    "GuaranteeLike",
                    "statement_shape",
                    new() { ["statement"] = "Drops.Add (PoolA [Rng.Next (1, PoolA.Count)]);" },
                    null
                )
            )
        );
    }

    [Fact]
    public void StatementShape_binds_a_statement_that_several_branches_make()
    {
        var result = Matchers.StatementShape(
            Method("Recalculate"),
            Fact(
                "fixture.recalculate",
                "assert",
                "Recalculate",
                "statement_shape",
                new() { ["statement"] = "Level++;", ["count"] = "2" },
                null
            )
        );

        Assert.Empty(result);
    }

    [Fact]
    public void StatementShape_rejects_a_repeated_statement_without_its_count()
    {
        var error = Assert.Throws<InvalidDataException>(() =>
            Matchers.StatementShape(
                Method("Recalculate"),
                Fact(
                    "fixture.recalculate",
                    "assert",
                    "Recalculate",
                    "statement_shape",
                    new() { ["statement"] = "Level++;" },
                    null
                )
            )
        );

        Assert.StartsWith("statement_shape bound 2 times (need exactly 1)", error.Message);
    }

    [Fact]
    public void NodeShape_rejects_wrong_node_shape()
    {
        Assert.Throws<InvalidDataException>(() =>
            Matchers.NodeShape(
                Method("GuaranteeRetryLike"),
                Fact(
                    "invalid.node",
                    "assert",
                    "GuaranteeRetryLike",
                    "node_shape",
                    new()
                    {
                        ["kind"] = "ForStatement",
                        ["shape"] = "for (int i = 0; i < 0; i++) { }",
                    },
                    null
                )
            )
        );
    }

    [Fact]
    public void StringSet_rejects_wrong_string_set()
    {
        Assert.Throws<InvalidDataException>(() =>
            Matchers.StringSet(
                Method("Combine"),
                Fact(
                    "invalid.string_set",
                    "assert",
                    "Combine",
                    "string_set",
                    new() { ["strings"] = "31377423" },
                    null
                )
            )
        );
    }

    [Fact]
    public void Runner_filters_playtest_only_invalid_fact_in_process()
    {
        var specsPath = Path.Combine(Path.GetTempPath(), $"code-facts-{Guid.NewGuid():N}.json");
        var specs = new
        {
            schema = 1,
            facts = new object[]
            {
                new
                {
                    id = "fixture.combine_ids",
                    mode = "extract",
                    type = "FixtureLib.FixtureLoot",
                    method = "Combine",
                    matcher = "string_constants",
                    args = new Dictionary<string, string>(),
                    keys = new[] { "strings" },
                },
                new
                {
                    id = "fixture.playtest_only_invalid",
                    mode = "assert",
                    type = "FixtureLib.FixtureLoot",
                    method = "MissingMethod",
                    matcher = "statement_shape",
                    args = new Dictionary<string, string> { ["statement"] = "never" },
                    variants = new[] { "playtest" },
                },
            },
        };

        try
        {
            File.WriteAllText(specsPath, JsonSerializer.Serialize(specs));
            var result = Runner.Run(typeof(FixtureLoot).Assembly.Location, specsPath, "main");

            var fact = Assert.Single(result.Facts);
            Assert.Equal("fixture.combine_ids", fact.Id);
            Assert.Equal("31377423,46289586", fact.Values!["strings"]);
            Assert.Empty(result.Errors);
            Assert.True(result.Ok);
        }
        finally
        {
            File.Delete(specsPath);
        }
    }

    [Fact]
    public void Runner_binds_a_field_initializer()
    {
        var result = RunFacts(FieldFact("SingletonB = \"b\""));

        var fact = Assert.Single(result.Facts);
        Assert.Equal("fixture.singleton_default", fact.Id);
        Assert.Empty(result.Errors);
        Assert.True(result.Ok);
    }

    [Fact]
    public void Runner_rejects_a_changed_field_initializer()
    {
        var result = RunFacts(FieldFact("SingletonB = \"c\""));

        Assert.Empty(result.Facts);
        Assert.Contains(result.Errors, error => error.StartsWith("fixture.singleton_default:"));
        Assert.False(result.Ok);
    }

    [Fact]
    public void Runner_rejects_a_fact_naming_a_method_and_a_field()
    {
        var result = RunFacts(
            new
            {
                id = "fixture.ambiguous",
                mode = "assert",
                type = "FixtureLib.FixtureLoot",
                method = "Combine",
                field = "SingletonB",
                matcher = "node_shape",
                args = new Dictionary<string, string>
                {
                    ["kind"] = "VariableInitializer",
                    ["shape"] = "SingletonB = \"b\"",
                },
            }
        );

        Assert.Equal(
            ["fixture.ambiguous: a fact names exactly one of method and field"],
            result.Errors
        );
    }

    [Fact]
    public void Runner_binds_the_overload_named_by_its_parameter_types()
    {
        var result = RunFacts(ScaleFact("return value * factor;", ["int", "int"]));

        Assert.Empty(result.Errors);
        Assert.Equal("fixture.scale", Assert.Single(result.Facts).Id);
    }

    [Fact]
    public void Runner_rejects_an_overloaded_method_without_parameter_types()
    {
        var result = RunFacts(ScaleFact("return value * 2;", null));

        Assert.Equal(
            ["fixture.scale: method FixtureLib.FixtureLoot::Scale bound 2 times (need exactly 1)"],
            result.Errors
        );
    }

    private static object ScaleFact(string shape, string[]? parameters) =>
        new
        {
            id = "fixture.scale",
            mode = "assert",
            type = "FixtureLib.FixtureLoot",
            method = "Scale",
            parameters,
            matcher = "node_shape",
            args = new Dictionary<string, string>
            {
                ["kind"] = "ReturnStatement",
                ["shape"] = shape,
            },
        };

    private static object FieldFact(string shape) =>
        new
        {
            id = "fixture.singleton_default",
            mode = "assert",
            type = "FixtureLib.FixtureLoot",
            field = "SingletonB",
            matcher = "node_shape",
            args = new Dictionary<string, string>
            {
                ["kind"] = "VariableInitializer",
                ["shape"] = shape,
            },
        };

    private static RunResult RunFacts(params object[] facts)
    {
        var specsPath = Path.Combine(Path.GetTempPath(), $"code-facts-{Guid.NewGuid():N}.json");
        try
        {
            File.WriteAllText(specsPath, JsonSerializer.Serialize(new { schema = 1, facts }));
            return Runner.Run(typeof(FixtureLoot).Assembly.Location, specsPath, "main");
        }
        finally
        {
            File.Delete(specsPath);
        }
    }

    [Fact]
    public void SwitchItemGrant_extracts_native_pool_and_selected_variable()
    {
        var result = Matchers.SwitchItemGrant(ParseBody(FossilGrant), GrantFact());
        Assert.Equal("Break Fossil", result["spell_name"]);
        Assert.Equal("GameData.Misc.FossilGame", result["pool"]);
        Assert.Equal("1", result["quantity"]);
        Assert.Equal("1", result["rolls"]);
        Assert.False(result.ContainsKey("created_item_id"));
    }

    [Fact]
    public void SwitchItemGrant_extracts_direct_item_id()
    {
        var method = ParseBody(
            """
            switch (operation) {
                case "Offering Stone":
                    if (!GameData.PlayerInv.AddItemToInv(GameData.ItemDB.GetItemByID("340104"))) {
                        GameData.PlayerInv.ForceItemToInv(GameData.ItemDB.GetItemByID("340104"));
                    }
                    break;
            }
            """
        );
        var result = Matchers.SwitchItemGrant(method, GrantFact("Offering Stone", false));
        Assert.Equal("Offering Stone", result["spell_name"]);
        Assert.Equal("340104", result["created_item_id"]);
        Assert.Equal("1", result["quantity"]);
        Assert.False(result.ContainsKey("pool"));
    }

    [Fact]
    public void SwitchItemGrant_is_dispatched_against_the_compiled_fixture()
    {
        var result = RunFacts(
            new
            {
                id = "fixture.fossil_grant",
                mode = "extract",
                type = "FixtureLib.FixtureItemOperations",
                method = "Grants",
                matcher = "switch_item_grant",
                args = new Dictionary<string, string>
                {
                    ["case"] = "Break Fossil",
                    ["pool"] = "GameData.Misc.FossilGame",
                },
                keys = new[] { "spell_name", "pool", "quantity", "rolls" },
            }
        );
        Assert.Empty(result.Errors);
        Assert.Single(result.Facts);
    }

    [Theory]
    [InlineData(
        "Random.Range(0, GameData.Misc.FossilGame.Count)",
        "Random.Range(1, GameData.Misc.FossilGame.Count)"
    )]
    [InlineData(
        "Random.Range(0, GameData.Misc.FossilGame.Count)",
        "Random.Range(0, GameData.Misc.FossilGame.Count - 1)"
    )]
    [InlineData(
        "Random.Range(0, GameData.Misc.FossilGame.Count)",
        "OtherRandom.Range(0, GameData.Misc.FossilGame.Count)"
    )]
    [InlineData("Item selectedFossil", "OtherItem selectedFossil")]
    [InlineData("AddItemToInv(selectedFossil)", "AddItemToInv(selectedFossil, 2)")]
    [InlineData("ForceItemToInv(selectedFossil)", "ForceItemToInv(otherItem)")]
    [InlineData("ForceItemToInv(selectedFossil)", "ForceItemToInv(selectedFossil, 2)")]
    [InlineData("!GameData.PlayerInv.AddItemToInv", "GameData.PlayerInv.AddItemToInv")]
    [InlineData(
        "if (!GameData.PlayerInv.AddItemToInv(selectedFossil))",
        "if (eligible && !GameData.PlayerInv.AddItemToInv(selectedFossil))"
    )]
    [InlineData("GameData.PlayerInv.ForceItemToInv", "otherInventory.ForceItemToInv")]
    [InlineData("case \"Break Fossil\":", "case \"Break Fossil\": case \"Other\":")]
    [InlineData("break;", "GameData.PlayerInv.AddItemToInv(selectedFossil); break;")]
    [InlineData("break;", "else { GameData.PlayerInv.ForceItemToInv(selectedFossil); } break;")]
    [InlineData(
        "break;",
        "while (eligible) { GameData.PlayerInv.AddItemToInv(selectedFossil); } break;"
    )]
    [InlineData("break;", "if (eligible) { UpdateSocialLog.LogAdd(\"different gate\"); } break;")]
    [InlineData(
        "UpdateSocialLog.LogAdd(\"public text\");",
        "UpdateSocialLog.LogAdd(GameData.PlayerInv.AddItemToInv(selectedFossil));"
    )]
    public void SwitchItemGrant_rejects_changed_gameplay(string original, string replacement)
    {
        Assert.Throws<InvalidDataException>(() =>
            Matchers.SwitchItemGrant(
                ParseBody(FossilGrant.Replace(original, replacement)),
                GrantFact()
            )
        );
    }

    [Fact]
    public void SwitchItemGrant_rejects_missing_or_ambiguous_case()
    {
        Assert.Throws<InvalidDataException>(() =>
            Matchers.SwitchItemGrant(
                ParseBody(FossilGrant.Replace("Break Fossil", "Other")),
                GrantFact()
            )
        );
        Assert.Throws<InvalidDataException>(() =>
            Matchers.SwitchItemGrant(ParseBody(FossilGrant + FossilGrant), GrantFact())
        );
    }

    [Fact]
    public void SwitchItemGrant_ignores_chat_text_but_not_item_identity()
    {
        var changed = FossilGrant
            .Replace("public text", "new wording")
            .Replace("selectedFossil", "nativeSelection");
        Assert.Equal("1", Matchers.SwitchItemGrant(ParseBody(changed), GrantFact())["quantity"]);
    }

    [Theory]
    [InlineData("GameData.ItemDB.GetItemByID(\"340104\")", "GameData.ItemDB.GetItemByID(itemId)")]
    [InlineData("GameData.ItemDB.GetItemByID(\"340104\")", "otherDatabase.GetItemByID(\"340104\")")]
    [InlineData(
        "ForceItemToInv(GameData.ItemDB.GetItemByID(\"340104\"))",
        "ForceItemToInv(GameData.ItemDB.GetItemByID(\"other\"))"
    )]
    public void SwitchItemGrant_rejects_nonliteral_or_mismatched_direct_grants(
        string original,
        string replacement
    )
    {
        const string direct = """
            switch (operation) {
                case "Offering Stone":
                    if (!GameData.PlayerInv.AddItemToInv(GameData.ItemDB.GetItemByID("340104"))) {
                        GameData.PlayerInv.ForceItemToInv(GameData.ItemDB.GetItemByID("340104"));
                    }
                    break;
            }
            """;
        Assert.Throws<InvalidDataException>(() =>
            Matchers.SwitchItemGrant(
                ParseBody(direct.Replace(original, replacement)),
                GrantFact("Offering Stone", false)
            )
        );
    }

    [Theory]
    [InlineData("2", true)]
    [InlineData("1", false)]
    [InlineData("3", false)]
    public void NodeShape_honors_explicit_occurrence_count(string count, bool accepted)
    {
        var fact = Fact(
            "fixture.count",
            "assert",
            "Recalculate",
            "node_shape",
            new()
            {
                ["kind"] = "ExpressionStatement",
                ["shape"] = "Level++;",
                ["count"] = count,
            },
            null
        );
        if (accepted)
            Assert.Empty(Matchers.NodeShape(Method("Recalculate"), fact));
        else
            Assert.Throws<InvalidDataException>(() =>
                Matchers.NodeShape(Method("Recalculate"), fact)
            );
    }

    [Fact]
    public void NodeShape_still_requires_one_occurrence_by_default()
    {
        var fact = Fact(
            "fixture.count",
            "assert",
            "Recalculate",
            "node_shape",
            new() { ["kind"] = "ExpressionStatement", ["shape"] = "Level++;" },
            null
        );
        Assert.Throws<InvalidDataException>(() => Matchers.NodeShape(Method("Recalculate"), fact));
    }

    [Fact]
    public void NodeShape_can_ignore_only_social_log_statements_without_mutating_the_scope()
    {
        var fact = SocialLogFact();
        foreach (string message in new[] { "original warning", "different warning" })
        {
            var method = ParseBody($"UpdateSocialLog.LogAdd(\"{message}\"); Quantity = 1;");
            string original = method.ToString();
            Assert.Empty(Matchers.NodeShape(method, fact));
            Assert.Equal(original, method.ToString());
            Assert.Throws<InvalidDataException>(() =>
                Matchers.NodeShape(
                    method,
                    fact with
                    {
                        Args = new(fact.Args) { ["ignore_social_logs"] = "false" },
                    }
                )
            );
        }
    }

    [Theory]
    [InlineData("UpdateSocialLog.LogAdd(\"warning\"); Quantity = 2;")]
    [InlineData("if (eligible) { UpdateSocialLog.LogAdd(\"warning\"); Quantity = 1; }")]
    [InlineData("UpdateSocialLog.LogAdd(GameData.PlayerInv.AddItemToInv(item)); Quantity = 1;")]
    [InlineData("UpdateSocialLog.LogAdd(GameData.PlayerInv.ForceItemToInv(item)); Quantity = 1;")]
    [InlineData(
        "UpdateSocialLog.LogAdd(GameData.PlayerInv.OtherInventoryMethod(item)); Quantity = 1;"
    )]
    [InlineData("UpdateSocialLog.LogAdd(Quantity = 2); Quantity = 1;")]
    [InlineData("UpdateSocialLog.LogAdd(++Quantity); Quantity = 1;")]
    [InlineData("UpdateSocialLog.LogAdd(Quantity++); Quantity = 1;")]
    [InlineData("UpdateSocialLog.LogAdd(--Quantity); Quantity = 1;")]
    [InlineData("UpdateSocialLog.LogAdd(Quantity--); Quantity = 1;")]
    [InlineData("OtherLog.LogAdd(\"warning\"); Quantity = 1;")]
    public void NodeShape_does_not_discard_inventory_or_control_effects(string body)
    {
        Assert.Throws<InvalidDataException>(() =>
            Matchers.NodeShape(ParseBody(body), SocialLogFact())
        );
    }

    private static FactSpec SocialLogFact() =>
        Fact(
            "fixture.logs",
            "assert",
            "Execute",
            "node_shape",
            new()
            {
                ["kind"] = "MethodDeclaration",
                ["shape"] = "private void Execute () { Quantity = 1; }",
                ["ignore_social_logs"] = "true",
            },
            null
        );

    private static MethodDeclaration ParseBody(string body) => NativeAstFixture.FromBody(body);

    private static FactSpec GrantFact(string spell = "Break Fossil", bool pool = true)
    {
        var args = new Dictionary<string, string> { ["case"] = spell };
        if (pool)
            args["pool"] = "GameData.Misc.FossilGame";
        return Fact("fixture.grant", "extract", "Execute", "switch_item_grant", args, null);
    }

    private const string FossilGrant = """
        switch (operation) {
            case "Break Fossil": {
                Item selectedFossil = GameData.Misc.FossilGame[Random.Range(0, GameData.Misc.FossilGame.Count)];
                UpdateSocialLog.LogAdd("public text");
                if (!GameData.PlayerInv.AddItemToInv(selectedFossil)) {
                    GameData.PlayerInv.ForceItemToInv(selectedFossil);
                }
                break;
            }
        }
        """;

    private static FactSpec Fact(
        string id,
        string mode,
        string method,
        string matcher,
        Dictionary<string, string> args,
        List<string>? keys,
        string typeName = "FixtureLib.FixtureLoot"
    ) => new(id, mode, typeName, method, matcher, args, keys, null);

    private static MethodDeclaration Method(string name, string typeName = "FixtureLib.FixtureLoot")
    {
        var assemblyPath = typeof(FixtureLoot).Assembly.Location;
        var resolver = new UniversalAssemblyResolver(
            assemblyPath,
            throwOnError: false,
            targetFramework: null
        );
        var decompiler = new CSharpDecompiler(assemblyPath, resolver, new DecompilerSettings());
        var tree = decompiler.DecompileType(new FullTypeName(typeName));
        return Assert.Single(
            tree.Descendants.OfType<MethodDeclaration>(),
            method => method.Name == name
        );
    }
}
