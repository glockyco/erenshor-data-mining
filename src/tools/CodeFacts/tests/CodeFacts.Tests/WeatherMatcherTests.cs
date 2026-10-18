using FixtureLib;
using ICSharpCode.Decompiler;
using ICSharpCode.Decompiler.CSharp;
using ICSharpCode.Decompiler.CSharp.Syntax;
using ICSharpCode.Decompiler.Metadata;
using ICSharpCode.Decompiler.TypeSystem;
using Xunit;

namespace CodeFacts.Tests;

public sealed class WeatherMatcherTests
{
    private static MethodDeclaration Method(string name, string type = "FixtureLib.FixtureWeather")
    {
        string path = typeof(FixtureWeather).Assembly.Location;
        var resolver = new UniversalAssemblyResolver(
            path,
            throwOnError: false,
            targetFramework: null
        );
        var decompiler = new CSharpDecompiler(path, resolver, new DecompilerSettings());
        return decompiler
            .DecompileType(new FullTypeName(type))
            .Descendants.OfType<MethodDeclaration>()
            .Single(method => method.Name == name);
    }

    private static FactSpec Fact(string matcher, string spell = "Invoke Storm") =>
        new(
            "fixture.weather",
            "extract",
            "FixtureLib.FixtureWeather",
            "WeatherSpells",
            matcher,
            new() { ["case"] = spell, ["switch"] = "spell" },
            null,
            null
        );

    [Fact]
    public void Rain_start_extracts_threshold_and_rejects_missing_sun()
    {
        Assert.Equal(
            "0.55",
            Matchers.WeatherRainStart(Method("RainStart"), Fact("weather_rain_start"))["threshold"]
        );
        Assert.Throws<InvalidDataException>(() =>
            Matchers.WeatherRainStart(Method("RainWithoutSun"), Fact("weather_rain_start"))
        );
    }

    [Theory]
    [InlineData("Invoke Storm", "0.9", "0.4")]
    [InlineData("Dissipate Storm", "0", "0.1")]
    public void Weather_spell_extracts_effects_and_rejects_changed_operations(
        string spell,
        string weight,
        string cloud
    )
    {
        var fact = Fact("weather_spell", spell);
        var values = Matchers.WeatherSpell(Method("WeatherSpells"), fact);
        Assert.Equal(spell, values["spell_name"]);
        Assert.Equal(weight, values["weight_goal"]);
        Assert.Equal(cloud, values["cloud_amount"]);
        if (spell == "Invoke Storm")
            Assert.Equal("-1", values["since_rain"]);
        else
            Assert.False(values.ContainsKey("since_rain"));
        Assert.Throws<InvalidDataException>(() =>
            Matchers.WeatherSpell(Method("ChangedSpell"), fact)
        );
    }

    [Theory]
    [InlineData("Classes.Count")]
    [InlineData("RequiredLevel")]
    [InlineData("MustBeEquippedToClick")]
    [InlineData("RequiredSlot ==")]
    public void Item_actions_pin_class_learning_level_and_click_guards(string condition)
    {
        var method = Method("Actions", "FixtureLib.FixtureItemActions");
        var fact = Fact("item_action_guards");
        Assert.Empty(Matchers.ItemActionGuards(method, fact));
        var guard = method
            .Descendants.OfType<IfElseStatement>()
            .Single(node =>
                node.Condition.ToString().Contains(condition, StringComparison.Ordinal)
            );
        guard.Condition = new PrimitiveExpression(true);
        Assert.Throws<InvalidDataException>(() => Matchers.ItemActionGuards(method, fact));
    }

    [Fact]
    public void Equip_actions_cannot_escape_the_item_class_guard()
    {
        var method = Method("Actions", "FixtureLib.FixtureItemActions");
        var fact = Fact("item_action_guards");
        var equip = method
            .Descendants.OfType<ExpressionStatement>()
            .Single(node => node.ToString().Trim() == "equipmentSlot.MyItem = MyItem;");
        equip.Remove();
        method.Body!.Statements.Add(equip);
        Assert.Throws<InvalidDataException>(() => Matchers.ItemActionGuards(method, fact));
    }
}
