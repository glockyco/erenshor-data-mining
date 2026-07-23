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
    [Fact]
    public void GuardedMemberRoll_binds_fixture_pool_and_singleton_values()
    {
        var pool = Matchers.GuardedMemberRoll(Method("Init"), Fact(
            "fixture.pool_a", "extract", "Init", "guarded_member_roll",
            new() { ["member"] = "PoolA" }, ["rate", "min_level"]));
        var singleton = Matchers.GuardedMemberRoll(Method("Init"), Fact(
            "fixture.singleton_b", "extract", "Init", "guarded_member_roll",
            new() { ["member"] = "SingletonB" }, ["rate", "min_level"]));

        Assert.Equal(new Dictionary<string, string>
        {
            ["rate"] = "0.005",
            ["min_level"] = "0",
        }, pool);
        Assert.Equal(new Dictionary<string, string>
        {
            ["rate"] = "0.0125",
            ["min_level"] = "20",
        }, singleton);
    }

    [Fact]
    public void StringConstants_binds_fixture_combine_ids()
    {
        var result = Matchers.StringConstants(Method("Combine"), Fact(
            "fixture.combine_ids", "extract", "Combine", "string_constants", [], ["strings"]));

        Assert.Equal(new Dictionary<string, string>
        {
            ["strings"] = "31377423,46289586",
        }, result);
    }

    [Fact]
    public void IntComparisons_binds_fixture_auction_envelope()
    {
        var result = Matchers.IntComparisons(Method("Auctionable"), Fact(
            "fixture.auction_envelope", "extract", "Auctionable", "int_comparisons",
            new() { ["level"] = "level", ["value"] = "value" }, ["level", "value"]));

        Assert.Equal(new Dictionary<string, string>
        {
            ["level"] = "> 0,< 40",
            ["value"] = "> 0",
        }, result);
    }

    [Fact]
    public void StatementShape_binds_fixture_guarantee_statement()
    {
        var result = Matchers.StatementShape(Method("GuaranteeLike"), Fact(
            "fixture.guarantee_shape", "assert", "GuaranteeLike", "statement_shape",
            new() { ["statement"] = "Drops.Add (PoolA [Rng.Next (0, PoolA.Count)]);" }, null));

        Assert.Empty(result);
    }

    [Fact]
    public void NodeShape_binds_fixture_guarantee_retry_loop()
    {
        const string shape =
            "for (int i = 0; i < numberOfGuaranteedDrops; i++) { string text = null; int num = 0; do { text = PoolA [Rng.Next (0, PoolA.Count)]; num++; } while (num < 10 && (text == null || Drops.Contains (text))); if (text != null) { Drops.Add (text); } }";
        var result = Matchers.NodeShape(Method("GuaranteeRetryLike"), Fact(
            "fixture.guarantee_retry_loop", "assert", "GuaranteeRetryLike", "node_shape",
            new() { ["kind"] = "ForStatement", ["shape"] = shape }, null));

        Assert.Empty(result);
    }

    [Fact]
    public void StringSet_binds_fixture_trigger_strings()
    {
        var result = Matchers.StringSet(Method("Combine"), Fact(
            "fixture.trigger_strings", "assert", "Combine", "string_set",
            new() { ["strings"] = "31377423,46289586" }, null));

        Assert.Empty(result);
    }

    [Fact]
    public void GuardedMemberRoll_rejects_unmatched_member()
    {
        Assert.Throws<InvalidDataException>(() => Matchers.GuardedMemberRoll(Method("Init"), Fact(
            "invalid.member", "extract", "Init", "guarded_member_roll",
            new() { ["member"] = "MissingPool" }, ["rate", "min_level"])));
    }

    [Fact]
    public void StringConstants_rejects_method_without_comparisons()
    {
        Assert.Throws<InvalidDataException>(() => Matchers.StringConstants(Method("GuaranteeLike"), Fact(
            "invalid.strings", "extract", "GuaranteeLike", "string_constants", [], ["strings"])));
    }

    [Fact]
    public void IntComparisons_rejects_missing_comparison_member()
    {
        Assert.Throws<InvalidDataException>(() => Matchers.IntComparisons(Method("Auctionable"), Fact(
            "invalid.comparison", "extract", "Auctionable", "int_comparisons",
            new() { ["missing"] = "missing" }, ["missing"])));
    }

    [Fact]
    public void StatementShape_rejects_wrong_statement()
    {
        Assert.Throws<InvalidDataException>(() => Matchers.StatementShape(Method("GuaranteeLike"), Fact(
            "invalid.statement", "assert", "GuaranteeLike", "statement_shape",
            new() { ["statement"] = "Drops.Add (PoolA [Rng.Next (1, PoolA.Count)]);" }, null)));
    }

    [Fact]
    public void NodeShape_rejects_wrong_node_shape()
    {
        Assert.Throws<InvalidDataException>(() => Matchers.NodeShape(Method("GuaranteeRetryLike"), Fact(
            "invalid.node", "assert", "GuaranteeRetryLike", "node_shape",
            new() { ["kind"] = "ForStatement", ["shape"] = "for (int i = 0; i < 0; i++) { }" }, null)));
    }

    [Fact]
    public void StringSet_rejects_wrong_string_set()
    {
        Assert.Throws<InvalidDataException>(() => Matchers.StringSet(Method("Combine"), Fact(
            "invalid.string_set", "assert", "Combine", "string_set",
            new() { ["strings"] = "31377423" }, null)));
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

    private static FactSpec Fact(
        string id,
        string mode,
        string method,
        string matcher,
        Dictionary<string, string> args,
        List<string>? keys) => new(
            id,
            mode,
            "FixtureLib.FixtureLoot",
            method,
            matcher,
            args,
            keys,
            null);

    private static MethodDeclaration Method(string name)
    {
        var assemblyPath = typeof(FixtureLoot).Assembly.Location;
        var resolver = new UniversalAssemblyResolver(
            assemblyPath,
            throwOnError: false,
            targetFramework: null);
        var decompiler = new CSharpDecompiler(
            assemblyPath,
            resolver,
            new DecompilerSettings());
        var tree = decompiler.DecompileType(new FullTypeName("FixtureLib.FixtureLoot"));
        return Assert.Single(tree.Descendants.OfType<MethodDeclaration>(), method => method.Name == name);
    }
}
