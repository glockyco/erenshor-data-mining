using AdventureGuide.Data;
using AdventureGuide.State;
using AdventureGuide.UI;

namespace AdventureGuide.Tests;

public sealed class ResourceSourceChanceTests
{
    private static ItemSource ParseSource(string sourceJson)
    {
        var data = GuideData.Parse(
            $$"""
            {
              "_version": 8,
              "_encounters": {"encounter_placements":[],"encounter_conditions":[],"encounter_completions":[],"encounter_event_conditions":[]},
              "_zone_line_destination_contexts": {},
              "_source_facts": {}, "_item_uses": {}, "_quest_state_keys": {},
              "quests": [{
                "stable_key": "quest:fishing", "db_name": "Fishing", "display_name": "Fishing",
                "steps": [{
                  "order": 1, "action": "collect", "description": "Collect a fish.",
                  "target_type": "item", "target_key": "item:fish", "target_name": "Fish",
                  "sources": [{{sourceJson}}]
                }]
              }]
            }
            """
        );
        return data.GetByStableKey("quest:fishing")!.Steps![0].Sources![0];
    }

    [Fact]
    public void Differing_positive_phases_keep_context_without_an_unconditional_rate()
    {
        var source = ParseSource(
            """{"type":"fishing","zone":"Brake","source_key":"water:Brake:1:2:3","day_chance":5.9375,"night_chance":19}"""
        );
        Assert.Null(source.Chance);
        Assert.Equal(5.9375, ItemSourcePolicy.FishingChance(source, 12));
        Assert.Equal(19, ItemSourcePolicy.FishingChance(source, 23));
        Assert.Null(SourceListText.Timing(source, 12));
        Assert.Null(SourceListText.Timing(source, 23));
    }

    [Theory]
    [InlineData(5, false)]
    [InlineData(6, true)]
    [InlineData(21, true)]
    [InlineData(22, false)]
    [InlineData(4, false)]
    [InlineData(23, false)]
    [InlineData(0, false)]
    public void Fishing_phase_follows_Water_Update_not_NPC_night_spawns(int hour, bool day)
    {
        var source = ParseSource("""{"type":"fishing","day_chance":25,"night_chance":50}""");
        Assert.Equal(day ? 25 : 50, ItemSourcePolicy.FishingChance(source, hour));
    }

    [Theory]
    [InlineData("day", 12, 22)]
    [InlineData("night", 22, 6)]
    public void Restricted_phase_keeps_odds_and_identity_without_becoming_an_access_gate(
        string phase,
        int availableHour,
        int unavailableHour
    )
    {
        string day = phase == "day" ? "13.5714283" : "0";
        string night = phase == "night" ? "13.5714283" : "0";
        var source = ParseSource(
            $$"""{"type":"fishing","source_key":"water:Vitheo:1:2:3","day_chance":{{day}},"night_chance":{{night}},"time_restriction":"{{phase}}"}"""
        );
        Assert.Equal(0, ItemSourcePolicy.FishingChance(source, unavailableHour));
        Assert.Equal(13.5714283, ItemSourcePolicy.FishingChance(source, availableHour));
        Assert.Equal("water:Vitheo:1:2:3", source.MakeSourceId());
        var gates = new GateConditions(new GuideData(), new GateTestFacts());
        Assert.True(gates.IsSourceAvailable(source));
    }

    [Theory]
    [InlineData("\"day_chance\":0,\"night_chance\":0")]
    [InlineData("\"day_chance\":-1,\"night_chance\":1")]
    [InlineData("\"day_chance\":1,\"night_chance\":101")]
    [InlineData("\"day_chance\":\"NaN\",\"night_chance\":1")]
    [InlineData("\"day_chance\":1,\"night_chance\":\"Infinity\"")]
    [InlineData("\"night_chance\":1")]
    [InlineData("\"day_chance\":1")]
    [InlineData("\"day_chance\":0,\"night_chance\":1")]
    [InlineData("\"day_chance\":1,\"night_chance\":0,\"time_restriction\":\"night\"")]
    [InlineData("\"day_chance\":1,\"night_chance\":2,\"time_restriction\":\"day\"")]
    [InlineData("\"day_chance\":1,\"night_chance\":2,\"chance\":2")]
    [InlineData("\"day_chance\":1,\"night_chance\":1,\"chance\":2")]
    [InlineData("\"day_chance\":1,\"night_chance\":1")]
    [InlineData("\"day_chance\":1,\"night_chance\":1,\"chance\":1,\"chance_max\":1")]
    public void Invalid_or_inconsistent_temporal_sources_fail_loading(string fields) =>
        Assert.Throws<InvalidDataException>(() =>
            ParseSource("{\"type\":\"fishing\"," + fields + "}")
        );

    [Theory]
    [InlineData("mining")]
    [InlineData("drop")]
    public void Local_non_fishing_chances_survive_loading_and_display(string type)
    {
        var source = ParseSource(
            $$"""{"type":"{{type}}","name":"Rock","chance":40.666666666666664}"""
        );
        Assert.Equal(40.666666666666664, source.Chance);
        Assert.Contains("40.67%", SourceListText.OptionOdds(source));
        Assert.Null(SourceListText.Timing(source, 22));
        Assert.Throws<InvalidDataException>(() =>
            ParseSource($$"""{"type":"{{type}}","day_chance":1,"night_chance":2}""")
        );
    }

    [Theory]
    [InlineData("\"NaN\"")]
    [InlineData("\"Infinity\"")]
    public void Non_finite_chance_ranges_fail_loading(string maximum) =>
        Assert.Throws<InvalidDataException>(() =>
            ParseSource(
                $$"""{"type":"common_world_item","name":"Common drops","chance":1,"chance_max":{{maximum}}}"""
            )
        );
}
