using System.Text.Json;
using FixtureLib;
using ICSharpCode.Decompiler;
using ICSharpCode.Decompiler.CSharp;
using ICSharpCode.Decompiler.CSharp.Syntax;
using ICSharpCode.Decompiler.Metadata;
using ICSharpCode.Decompiler.TypeSystem;
using Xunit;

namespace CodeFacts.Tests;

public sealed class TravelMatcherTests
{
    private static MethodDeclaration Method(string name)
    {
        string path = typeof(FixtureTravel).Assembly.Location;
        var resolver = new UniversalAssemblyResolver(
            path,
            throwOnError: false,
            targetFramework: null
        );
        var decompiler = new CSharpDecompiler(path, resolver, new DecompilerSettings());
        return decompiler
            .DecompileType(new FullTypeName("FixtureLib.FixtureTravel"))
            .Descendants.OfType<MethodDeclaration>()
            .Single(method => method.Name == name);
    }

    private static readonly FactSpec Fact = new(
        "fixture.travel",
        "extract",
        "FixtureLib.FixtureTravel",
        "Spells",
        "scene_changes",
        new() { ["invocation"] = "GameData.SceneChange.ChangeScene" },
        null,
        null
    );

    private static List<JsonElement> Changes(string method) =>
        Matchers
            .SceneChanges(Method(method), Fact)
            .OrderBy(pair => int.Parse(pair.Key))
            .Select(pair => JsonDocument.Parse(pair.Value).RootElement)
            .ToList();

    private static string[] Strings(JsonElement change, string key) =>
        change.GetProperty(key).EnumerateArray().Select(item => item.GetString()!).ToArray();

    [Fact]
    public void Spell_switch_keeps_each_case_its_guards_and_its_scene_conditions()
    {
        var changes = Changes("Spells");
        Assert.Equal(5, changes.Count);

        Assert.Equal("Windwashed", changes[0].GetProperty("to").GetString());
        Assert.Equal("755.27,66,-474.4", changes[0].GetProperty("landing").GetString());
        Assert.Equal("true", changes[0].GetProperty("sun").GetString());
        Assert.Equal(new[] { "spell == \"Portal to Windwashed\"" }, Strings(changes[0], "when"));

        // A destination that is no literal keeps its source text.
        Assert.Equal("expr:GameData.BindZone", changes[1].GetProperty("to").GetString());
        Assert.Equal("expr:GameData.BindLoc", changes[1].GetProperty("landing").GetString());

        // The guard that breaks out of the case becomes a condition the call needs to fail.
        Assert.Equal(
            new[] { "SceneManager.GetActiveScene ().name == \"Reliquary\"" },
            Strings(changes[2], "unless")
        );

        // An else-if chain keeps the outer negation before the inner condition.
        Assert.Equal(
            new[]
            {
                "spell == \"Dimensional Rift\"",
                "!(SceneManager.GetActiveScene ().name == \"Azynthi\")",
                "SceneManager.GetActiveScene ().name == \"AzynthiClear\"",
            },
            Strings(changes[4], "when")
        );
    }

    [Fact]
    public void Method_level_return_guards_the_later_change_and_loop_breaks_do_not()
    {
        var changes = Changes("Release");
        Assert.Equal(new[] { "Timer <= 1f", "!Released" }, Strings(changes[0], "when"));
        Assert.Empty(Strings(changes[0], "unless"));
        Assert.Equal(new[] { "Timer <= 1f" }, Strings(changes[1], "when"));
        Assert.Equal(new[] { "!Released" }, Strings(changes[1], "unless"));
    }

    [Theory]
    [InlineData("InLoop")]
    [InlineData("UnreadableExit")]
    public void Control_flow_that_the_matcher_cannot_read_fails(string method)
    {
        Assert.Throws<InvalidDataException>(() => Matchers.SceneChanges(Method(method), Fact));
    }
}
