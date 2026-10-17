using AdventureGuide.Data;

namespace AdventureGuide.Tests;

public sealed class RecipeInputPresentationTests
{
    private static ItemSource Input(int slot, string item = "item:shard")
    {
        string key = "use:recipe:" + slot;
        return new()
        {
            Type = "ingredient",
            Name = item,
            ItemStableKey = item,
            UseKey = key,
            Quantity = 1,
            CanonicalUse = new()
            {
                UseKey = key,
                ItemStableKey = item,
                Kind = "crafting_material",
                TargetStableKey = "recipe:stone",
                QuantityKind = "exact",
                QuantityMin = 1,
                QuantityMax = 1,
            },
            Children =
            [
                new()
                {
                    Type = "drop",
                    AcquisitionKey = "acquisition:" + item,
                    LocationKey = "location:one",
                    CanonicalSourceId = "acquisition:" + item + "|location:one",
                },
            ],
        };
    }

    [Theory]
    [InlineData(0, true)]
    [InlineData(1, true)]
    [InlineData(3, true)]
    [InlineData(4, true)]
    [InlineData(7, true)]
    [InlineData(8, false)]
    public void One_quantity_row_keeps_all_slots_and_requires_the_complete_input(
        int have,
        bool missing
    )
    {
        var inputs = Enumerable.Range(1, 8).Select(slot => Input(slot)).ToList();
        var row = Assert.Single(ItemSourcePolicy.PresentationSources(inputs));
        Assert.Same(inputs[7], row.Primary);
        Assert.Equal(8, ItemSourcePolicy.RequiredInputQuantity(row.Primary, inputs));
        Assert.Equal(missing, ItemSourcePolicy.NeedsUsedItem(row.Primary, _ => have, inputs));
        Assert.Equal(8, inputs.Select(input => input.UseKey).Distinct().Count());
        foreach (var input in inputs)
            Assert.Same(input, SourceChoice.FindContaining(inputs, input)!.Primary);
    }

    [Theory]
    [InlineData("item")]
    [InlineData("recipe")]
    [InlineData("variant")]
    [InlineData("quality")]
    [InlineData("condition")]
    [InlineData("external_scope")]
    [InlineData("recipe_input")]
    [InlineData("source")]
    public void Distinct_material_contexts_do_not_disappear_into_one_row(string difference)
    {
        var first = Input(1);
        var other = Input(2);
        switch (difference)
        {
            case "item":
                other.ItemStableKey = other.CanonicalUse!.ItemStableKey = "item:wood";
                break;
            case "recipe":
                other.CanonicalUse!.TargetStableKey = "recipe:other";
                break;
            case "variant":
                other.CanonicalUse!.VariantKey = "variant:other";
                break;
            case "quality":
                other.OutputQuality = "enchanted";
                break;
            case "condition":
                other.Condition = 1;
                break;
            case "external_scope":
                other.CanonicalUse!.Conditions.Add(new() { Scope = "external:room" });
                break;
            case "recipe_input":
                other.CanonicalUse!.Kind = "crafting_recipe";
                break;
            case "source":
                other.Children![0].CanonicalSourceId = "different:acquisition";
                break;
        }
        var rows = ItemSourcePolicy.PresentationSources([first, other]);
        Assert.Collection(
            rows,
            row => Assert.Same(first, row.Primary),
            row => Assert.Same(other, row.Primary)
        );
        if (difference == "external_scope")
            Assert.Equal("external:room", Assert.Single(other.CanonicalUse!.Conditions).Scope);
    }

    [Fact]
    public void Shipping_recipe_retains_eight_material_uses_and_a_separate_recipe_input()
    {
        using var stream = typeof(GuideData).Assembly.GetManifestResourceStream(
            "AdventureGuide.quest-guide.json"
        );
        using var reader = new StreamReader(stream!);
        var data = GuideData.Parse(reader.ReadToEnd());
        var quest = data.GetByRuntimeKey("ArenaToken")!;
        var recipe = quest.RequiredItems![0].Sources!.Single(source => source.Type == "crafting");
        var inputs = recipe.Children!;
        var rows = ItemSourcePolicy.PresentationSources(inputs);
        var materials = rows.Single(row => row.Primary.CanonicalUse!.Kind == "crafting_material");
        Assert.Equal(8, ItemSourcePolicy.RequiredInputQuantity(materials.Primary, inputs));
        Assert.Equal(8, inputs.Count(input => input.CanonicalUse!.Kind == "crafting_material"));
        Assert.Single(rows, row => row.Primary.CanonicalUse!.Kind == "crafting_recipe");
        Assert.Equal(2, rows.Count);
        foreach (var input in inputs)
            Assert.Same(data.ItemUses[input.UseKey!], input.CanonicalUse);
    }
}
