using FixtureLib;
using ICSharpCode.Decompiler;
using ICSharpCode.Decompiler.CSharp;
using ICSharpCode.Decompiler.CSharp.Syntax;
using ICSharpCode.Decompiler.Metadata;
using ICSharpCode.Decompiler.TypeSystem;
using Xunit;

namespace CodeFacts.Tests;

public sealed class FactionMatcherTests
{
    private static MethodDeclaration Method(string name)
    {
        string path = typeof(FixtureFaction).Assembly.Location;
        var resolver = new UniversalAssemblyResolver(
            path,
            throwOnError: false,
            targetFramework: null
        );
        var decompiler = new CSharpDecompiler(path, resolver, new DecompilerSettings());
        return decompiler
            .DecompileType(new FullTypeName("FixtureLib.FixtureFaction"))
            .Descendants.OfType<MethodDeclaration>()
            .Single(method => method.Name == name);
    }

    private static FactSpec Fact(string method, string matcher, Dictionary<string, string> args) =>
        new(
            "fixture.faction",
            "extract",
            "FixtureLib.FixtureFaction",
            method,
            matcher,
            args,
            null,
            null
        );

    [Fact]
    public void Float_expression_extracts_one_threshold_and_rejects_an_ambiguous_one()
    {
        var fact = Fact(
            "Threshold",
            "float_expression",
            new() { ["left"] = "Mine.FactionValue", ["operator"] = "<" }
        );
        Assert.Equal("0", Matchers.FloatExpression(Method("Threshold"), fact)["value"]);
        Assert.Throws<InvalidDataException>(() =>
            Matchers.FloatExpression(Method("TwoThresholds"), fact)
        );
        var other = fact with
        {
            Args = new() { ["left"] = "Mine.FactionValue", ["operator"] = "<=" },
        };
        Assert.Throws<InvalidDataException>(() =>
            Matchers.FloatExpression(Method("Threshold"), other)
        );
    }

    [Theory]
    [InlineData("SplitOverride")]
    [InlineData("ExtraOverride")]
    public void Equality_branch_assignments_extracts_an_override_and_rejects_a_changed_one(
        string changed
    )
    {
        var fact = Fact(
            "Override",
            "equality_branch_assignments",
            new()
            {
                ["left"] = "Charm.ItemName",
                ["invocation"] = "Factions.FindFactionData",
                ["member"] = "Value",
            }
        );
        Assert.Equal(
            new Dictionary<string, string>
            {
                ["literal"] = "Pin",
                ["argument"] = "School",
                ["when_equal"] = "10",
                ["otherwise"] = "-10",
            },
            Matchers.EqualityBranchAssignments(Method("Override"), fact)
        );
        Assert.Throws<InvalidDataException>(() =>
            Matchers.EqualityBranchAssignments(Method(changed), fact)
        );
    }
}
