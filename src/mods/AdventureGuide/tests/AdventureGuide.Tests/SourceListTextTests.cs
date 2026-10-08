using AdventureGuide.Data;
using AdventureGuide.UI;

namespace AdventureGuide.Tests;

public sealed class SourceListTextTests
{
    private static List<ItemSource> Sources(params int?[] levels) =>
        levels.Select(level => new ItemSource { Type = "drop", Level = level }).ToList();

    [Fact]
    public void Range_spans_hidden_sources_with_a_level_even_when_an_unleveled_one_is_last() =>
        Assert.Equal(
            "3 more sources (Lv 4-38)",
            SourceListText.MoreSources(Sources(1, 2, 4, 38, null), 2)
        );

    [Fact]
    public void Single_hidden_level_shows_once() =>
        Assert.Equal("2 more sources (Lv 7)", SourceListText.MoreSources(Sources(1, 7, 7), 1));

    [Fact]
    public void Hidden_sources_without_levels_show_no_range() =>
        Assert.Equal("2 more sources", SourceListText.MoreSources(Sources(1, null, null), 1));
}
