using AdventureGuide.Data;
using AdventureGuide.UI;

namespace AdventureGuide.Tests;

public sealed class SourceListTextTests
{
    private static ItemSource ParseSource(string json)
    {
        var data = GuideData.Parse(
            $$"""
            {"_version":8,
             "_encounters":{"encounter_placements":[],"encounter_conditions":[],"encounter_completions":[],"encounter_event_conditions":[]},
             "_zone_line_destination_contexts":{},
             "_source_facts":{}, "_item_uses":{}, "_quest_state_keys":{}, "quests":[{
              "stable_key":"quest:source","db_name":"Source","display_name":"Source",
              "steps":[{"order":1,"action":"collect","description":"Collect an item.",
                "target_type":"item","target_key":"item:test","target_name":"Item",
                "sources":[{{json}}]}]
            }]}
            """
        );
        return data.GetByStableKey("quest:source")!.Steps![0].Sources![0];
    }

    [Theory]
    [InlineData("drop")]
    [InlineData("mining")]
    [InlineData("fishing")]
    public void Tiny_positive_odds_never_display_as_zero(string type)
    {
        string chances =
            type == "fishing"
                ? "\"day_chance\":0.000000002,\"night_chance\":20"
                : "\"chance\":0.000000002";
        var source = ParseSource($$"""{"type":"{{type}}","name":"Rare source",{{chances}}}""");
        string details = SourceListText.Details(source);
        Assert.Contains("<0.01%", details);
        Assert.DoesNotContain(": 0%", details);
        Assert.Equal(type == "fishing" ? (double?)null : 0.000000002, source.Chance);
        if (type == "fishing")
        {
            Assert.Equal(0.000000002, source.DayChance);
            Assert.Contains("Day", details);
            Assert.Contains("night", details);
            Assert.Contains("20%", details);
            Assert.Null(source.Chance);
        }
    }
}
