using AdventureGuide.Data;
using AdventureGuide.State;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace AdventureGuide.Tests;

public sealed class GuideWireTests
{
    private static JObject Payload() =>
        JObject.Parse(
            """
            {"_version":11,
             "_encounters":{"encounter_placements":[],"encounter_conditions":[],"encounter_completions":[],"encounter_event_conditions":[]},
             "_sources":{},"_place_sets":{},"_item_uses":{},"_quest_state_keys":{},"_zone_line_destination_contexts":{},"quests":[]}
            """
        );

    private static JObject MarkerPayload()
    {
        var payload = Payload();
        payload["_zone_lookup"] = JObject.Parse(
            """{"A":{"display_name":"A zone","stable_key":"zone:a"}}"""
        );
        payload["_spawn_points"] = JArray.Parse("""[[1952,"A","spawn:test",1,2,3]]""");
        payload["_character_spawns"] = JObject.Parse(
            """{"character:first":[0],"character:second":[0]}"""
        );
        payload["_place_sets"] = JObject.Parse(
            """{"places:test":[[76,"spawn:test","0","fixed"]]}"""
        );
        payload["_sources"] = JObject.Parse(
            """{"source:test":{"type":"pickup","kind":"item_bag","item_stable_key":"item:test","place_set_key":"places:test","rank":{"tier":2,"depth":3}}}"""
        );
        payload["quests"] = JArray.Parse(
            """
            [{"stable_key":"quest:test","db_name":"Test","display_name":"Test",
              "steps":[{"order":1,"action":"obtain","description":"Obtain the item.","sources":[{"acquisition_key":"source:test"}]}]}]
            """
        );
        return payload;
    }

    [Fact]
    public void Pool_expands_property_names_values_and_literal_tilde_strings_once()
    {
        const string json = """
            {"_strings":["_version","_sources","source:test","item:test","kind","auction_house","name","~literal","_place_sets"],
             "~0":11,"~1":{"~2":{"type":"auction_house","~4":"~5","item_stable_key":"~3","~6":"~7"}},
             "~8":{},"_item_uses":{},"_quest_state_keys":{},"_zone_line_destination_contexts":{},
             "_encounters":{"encounter_placements":[],"encounter_conditions":[],"encounter_completions":[],"encounter_event_conditions":[]},
             "quests":[]}
            """;
        var data = GuideData.Parse(json);
        var source = data.Sources["source:test"];
        Assert.Equal("item:test", source.ItemStableKey);
        Assert.Equal("auction_house", source.Kind);
        Assert.Equal("~literal", source.Name);
    }

    [Fact]
    public void Pool_is_consumed_without_exposing_it_to_the_deserializer()
    {
        using var text = new StringReader("""{"_strings":["field","value"],"~0":"~1"}""");
        using var reader = new GuideJsonReader(text);
        var serializer = JsonSerializer.Create(
            new JsonSerializerSettings { MissingMemberHandling = MissingMemberHandling.Error }
        );
        var value = serializer.Deserialize<Dictionary<string, string>>(reader);
        Assert.Equal("value", Assert.Single(value!).Value);
        Assert.DoesNotContain("_strings", value!.Keys);
    }

    [Theory]
    [InlineData("~")]
    [InlineData("~-1")]
    [InlineData("~+0")]
    [InlineData("~ 0")]
    [InlineData("~1")]
    [InlineData("~999999999999999999999")]
    public void Pool_rejects_invalid_value_and_property_references(string reference)
    {
        foreach (
            string json in new[]
            {
                "{\"_strings\":[\"value\"],\"field\":"
                    + JsonConvert.SerializeObject(reference)
                    + "}",
                "{\"_strings\":[\"value\"]," + JsonConvert.SerializeObject(reference) + ":0}",
            }
        )
        {
            using var text = new StringReader(json);
            using var reader = new GuideJsonReader(text);
            Assert.Throws<JsonSerializationException>(() => JToken.ReadFrom(reader));
        }
    }

    [Theory]
    [InlineData("{\"_strings\":null}")]
    [InlineData("{\"_strings\":{}}")]
    [InlineData("{\"_strings\":[null]}")]
    [InlineData("{\"_strings\":[1]}")]
    [InlineData("{\"field\":0,\"_strings\":[]}")]
    [InlineData("{\"_strings\":[],\"_strings\":[]}")]
    [InlineData("{\"field\":\"~0\"}")]
    public void Pool_rejects_malformed_or_misplaced_tables(string json)
    {
        using var text = new StringReader(json);
        using var reader = new GuideJsonReader(text);
        Assert.Throws<JsonSerializationException>(() => JToken.ReadFrom(reader));
    }

    [Fact]
    public void Native_object_list_and_condition_references_survive_pool_expansion()
    {
        const string json = """
            {"_strings":["source:test","item:test","acquisition_key","gate_key","gate","predicate","actor_level","actor","player","phase","availability"],
             "_version":11,
             "_sources":{"~0":{"type":"auction_house","kind":"auction_house","item_stable_key":"~1",
               "conditions":{"$id":"~conditions","$values":[{"$id":"~condition","~3":"~4","~5":"~6","~7":"~8","minimum":10,"maximum":20,"minimum_inclusive":false,"maximum_inclusive":false,"~9":"~10"}]}}},
             "_place_sets":{},"_item_uses":{"use:test":{"use_key":"use:test","item_stable_key":"~1","conditions":[{"$ref":"~condition"}]}},"_quest_state_keys":{},"_zone_line_destination_contexts":{},
             "_encounters":{"encounter_placements":[],"encounter_conditions":[],"encounter_completions":[],"encounter_event_conditions":[]},
             "quests":[{"stable_key":"quest:test","db_name":"Test","display_name":"Test",
               "required_items":[{"item_stable_key":"~1","item_name":"Item","sources":{"$id":"~sources","$values":[{"$id":"~source","~2":"~0"}]}}],
               "steps":[{"order":1,"action":"obtain","description":"Obtain the item.","sources":{"$ref":"~sources"}}]}],
             "_gate_items":{"~1":{"name":"Item","sources":{"$ref":"~sources"}}}}
            """;
        var data = GuideData.Parse(json);
        var quest = data.All[0];
        var sources = quest.RequiredItems![0].Sources!;
        Assert.Same(sources, quest.Steps![0].Sources);
        Assert.Same(sources, data.GateItems["item:test"].Sources);
        Assert.Same(data.Sources["source:test"], sources[0].CanonicalFact);
        var condition = Assert.Single(data.Sources["source:test"].Conditions);
        Assert.Same(condition, data.ItemUses["use:test"].Conditions[0]);
        Assert.False(condition.MinimumInclusive);
        Assert.False(condition.MaximumInclusive);
        Assert.Equal(0, condition.GateIndex);
        Assert.Equal(0, condition.AlternativeIndex);
        Assert.Equal(0, condition.AtomIndex);
        var facts = new GateTestFacts { PlayerLevel = 10 };
        var gates = new GateConditions(data, facts);
        Assert.False(gates.IsSourceAvailable(sources[0]));
        facts.PlayerLevel = 11;
        Assert.True(gates.IsSourceAvailable(sources[0]));
        facts.PlayerLevel = 20;
        Assert.False(gates.IsSourceAvailable(sources[0]));
    }

    [Fact]
    public void Shared_native_source_objects_and_condition_lists_keep_identity()
    {
        var payload = Payload();
        payload["_sources"] = JObject.Parse(
            """
            {"source:first":{"type":"auction_house","kind":"auction_house","item_stable_key":"item:first","conditions":{"$id":"conditions","$values":[]}},
             "source:second":{"type":"auction_house","kind":"auction_house","item_stable_key":"item:second","conditions":{"$ref":"conditions"}}}
            """
        );
        payload["quests"] = JArray.Parse(
            """
            [{"stable_key":"quest:test","db_name":"Test","display_name":"Test","steps":[
              {"order":1,"action":"obtain","description":"First.","sources":[{"$id":"source","acquisition_key":"source:first"}]},
              {"order":2,"action":"obtain","description":"Second.","sources":[{"$ref":"source"}]}]}]
            """
        );
        var data = GuideData.Parse(payload.ToString());
        Assert.Same(
            data.Sources["source:first"].Conditions,
            data.Sources["source:second"].Conditions
        );
        Assert.Same(data.All[0].Steps![0].Sources![0], data.All[0].Steps![1].Sources![0]);
    }

    [Fact]
    public void Shared_source_objects_expand_every_place_in_each_distinct_list_once()
    {
        var payload = MarkerPayload();
        payload["_place_sets"] = JObject.Parse(
            """{"places:test":[[76,"spawn:test","0","fixed"],[76,"spawn:test","1","fixed"]]}"""
        );
        payload["quests"] = JArray.Parse(
            """
            [{"stable_key":"quest:test","db_name":"Test","display_name":"Test","steps":[
              {"order":1,"action":"obtain","description":"First.",
               "sources":{"$id":"list","$values":[{"$id":"source","acquisition_key":"source:test"}]}},
              {"order":2,"action":"obtain","description":"Second.","sources":[{"$ref":"source"}]},
              {"order":3,"action":"obtain","description":"Third.","sources":{"$ref":"list"}}]}]
            """
        );
        var steps = GuideData.Parse(payload.ToString()).All[0].Steps!;
        foreach (var step in steps)
            Assert.Equal(new[] { "0", "1" }, step.Sources!.Select(source => source.LocationKey));
        Assert.Same(steps[0].Sources, steps[2].Sources);
        Assert.Same(steps[0].Sources![0], steps[1].Sources![0]);
    }

    [Fact]
    public void Spawn_rows_follow_sorted_fields_and_keep_omitted_defaults()
    {
        var defaults = JsonConvert.DeserializeObject<SpawnPoint>("[0]")!;
        Assert.False(defaults.IsDirectlyPlaced);
        Assert.False(defaults.NightSpawn);
        Assert.Null(defaults.Condition);
        Assert.Null(defaults.Entries);
        Assert.Null(defaults.Activations);
        Assert.Null(defaults.SourceScript);
        Assert.Equal("", defaults.Scene);
        Assert.Equal(0, defaults.X);
        var spawn = JsonConvert.DeserializeObject<SpawnPoint>(
            """[2047,[],0,[0],true,true,"A","SpawnPoint","spawn:test",1,2,3]"""
        )!;
        Assert.Empty(spawn.Activations!);
        Assert.Equal(0, spawn.Condition);
        Assert.Equal(new[] { 0 }, spawn.Entries);
        Assert.True(spawn.IsDirectlyPlaced);
        Assert.True(spawn.NightSpawn);
        Assert.Equal("A", spawn.Scene);
        Assert.Equal("SpawnPoint", spawn.SourceScript);
        Assert.Equal("spawn:test", spawn.StableKey);
        Assert.Equal((1f, 2f, 3f), (spawn.X, spawn.Y, spawn.Z));
    }

    [Fact]
    public void Place_rows_follow_sorted_fields_and_keep_omitted_defaults()
    {
        var defaults = JsonConvert.DeserializeObject<SourceLocation>("[0]")!;
        Assert.Empty(defaults.Conditions);
        Assert.Empty(defaults.EntryZoneLineKeys);
        Assert.Null(defaults.Scene);
        Assert.Null(defaults.X);
        Assert.Null(defaults.PlayerLevelMin);
        var location = JsonConvert.DeserializeObject<SourceLocation>(
            """[16383,[],["line"],"spawn:test","0",20,10,"fixed","A","character:copy",1,2,3,"A zone","zone:a"]"""
        )!;
        Assert.Empty(location.Conditions);
        Assert.Equal(new[] { "line" }, location.EntryZoneLineKeys);
        Assert.Equal("spawn:test", location.MarkerStableKey);
        Assert.Equal("0", location.PlaceKey);
        Assert.Equal(20, location.PlayerLevelMax);
        Assert.Equal(10, location.PlayerLevelMin);
        Assert.Equal("fixed", location.Relation);
        Assert.Equal("A", location.Scene);
        Assert.Equal("character:copy", location.SourceCopyStableKey);
        Assert.Equal((1f, 2f, 3f), (location.X!.Value, location.Y!.Value, location.Z!.Value));
        Assert.Equal("A zone", location.Zone);
        Assert.Equal("zone:a", location.ZoneStableKey);
    }

    [Fact]
    public void Row_list_values_support_native_reference_metadata()
    {
        var spawns = JsonConvert.DeserializeObject<List<SpawnPoint>>(
            """[[4,{"$id":"entries","$values":[0]}],[4,{"$ref":"entries"}]]"""
        )!;
        Assert.Same(spawns[0].Entries, spawns[1].Entries);
        var locations = JsonConvert.DeserializeObject<List<SourceLocation>>(
            """[[1,{"$id":"conditions","$values":[{"$id":"condition","minimum_inclusive":false}]}],[1,{"$ref":"conditions"}],[1,[{"$ref":"condition"}]]]"""
        )!;
        Assert.Same(locations[0].Conditions, locations[1].Conditions);
        Assert.Same(locations[0].Conditions[0], locations[2].Conditions[0]);
        Assert.False(locations[2].Conditions[0].MinimumInclusive);
    }

    [Theory]
    [InlineData("[]")]
    [InlineData("[-1]")]
    [InlineData("[2048]")]
    [InlineData("[2147483648]")]
    [InlineData("[1.5]")]
    [InlineData("[\"1\"]")]
    [InlineData("[null]")]
    [InlineData("[0,1]")]
    [InlineData("[32]")]
    [InlineData("[32,null]")]
    [InlineData("[32,10]")]
    [InlineData("[8,\"true\"]")]
    [InlineData("[2,1.5]")]
    [InlineData("[256,\"1\"]")]
    [InlineData("[4,0]")]
    public void Spawn_rows_reject_invalid_masks_types_and_lengths(string json) =>
        Assert.Throws<JsonSerializationException>(() =>
            JsonConvert.DeserializeObject<SpawnPoint>(json)
        );

    [Theory]
    [InlineData("[]")]
    [InlineData("[16384]")]
    [InlineData("[1,null]")]
    [InlineData("[2,null]")]
    [InlineData("[8,null]")]
    [InlineData("[8,0]")]
    [InlineData("[16,1.5]")]
    [InlineData("[64,false]")]
    [InlineData("[512,true]")]
    [InlineData("[0,[]]")]
    public void Place_rows_reject_invalid_masks_types_and_lengths(string json) =>
        Assert.Throws<JsonSerializationException>(() =>
            JsonConvert.DeserializeObject<SourceLocation>(json)
        );

    [Fact]
    public void Hand_authored_objects_and_default_inclusive_flags_remain_readable()
    {
        var spawn = JsonConvert.DeserializeObject<SpawnPoint>("""{"scene":"A","x":1}""")!;
        Assert.Equal("A", spawn.Scene);
        Assert.Equal(1, spawn.X);
        var location = JsonConvert.DeserializeObject<SourceLocation>(
            """{"place_key":"0","relation":"unlocated"}"""
        )!;
        Assert.Equal("0", location.PlaceKey);
        Assert.Empty(location.Conditions);
        var condition = JsonConvert.DeserializeObject<SourceCondition>("{}")!;
        Assert.True(condition.MinimumInclusive);
        Assert.True(condition.MaximumInclusive);
    }

    [Fact]
    public void Compact_marker_places_restore_before_coordinate_validation_and_resolution()
    {
        var payload = MarkerPayload();
        payload.AddFirst(new JProperty("_strings", new JArray("A", "spawn:test", "fixed")));
        payload["_spawn_points"] = JArray.Parse("""[[1952,"~0","~1",1,2,3]]""");
        payload["_place_sets"] = JObject.Parse("""{"places:test":[[76,"~1","0","~2"]]}""");
        var data = GuideData.Parse(payload.ToString());
        Assert.NotSame(
            data.CharacterSpawns["character:first"][0],
            data.CharacterSpawns["character:second"][0]
        );
        var place = Assert.Single(data.PlaceSets["places:test"]);
        Assert.Equal("A", place.Scene);
        Assert.Equal((1f, 2f, 3f), (place.X!.Value, place.Y!.Value, place.Z!.Value));
        Assert.Equal("A zone", place.Zone);
        Assert.Equal("zone:a", place.ZoneStableKey);
        var source = data.All[0].Steps![0].Sources![0];
        Assert.Equal("source:test|0", source.MakeSourceId());
        Assert.Equal("A zone", source.Zone);
        Assert.Same(data.Sources["source:test"].Rank, source.Rank);
        Assert.Equal(2, source.Rank!.Tier);
        Assert.Equal(3, source.Rank.Depth);
        Assert.Equal(
            (1f, 2f, 3f),
            (source.CanonicalSpawn!.X, source.CanonicalSpawn.Y, source.CanonicalSpawn.Z)
        );
    }

    [Fact]
    public void Shared_wire_index_lists_restore_distinct_runtime_placement_occurrences()
    {
        var payload = MarkerPayload();
        payload["_character_spawns"] = JObject.Parse(
            """{"character:first":{"$id":"indexes","$values":[0]},"character:second":{"$ref":"indexes"}}"""
        );
        var data = GuideData.Parse(payload.ToString());
        Assert.NotSame(
            data.CharacterSpawns["character:first"],
            data.CharacterSpawns["character:second"]
        );
        var first = data.CharacterSpawns["character:first"][0];
        var second = data.CharacterSpawns["character:second"][0];
        Assert.NotSame(first, second);
        Assert.Equal(
            (first.StableKey, first.Scene, first.X),
            (second.StableKey, second.Scene, second.X)
        );
    }

    [Fact]
    public void Duplicate_marker_payloads_may_have_distinct_conditions_and_entries()
    {
        var payload = MarkerPayload();
        payload["_conditions"] = JArray.Parse("[[],[]]");
        payload["_spawn_points"] = JArray.Parse(
            """[[1954,0,"A","spawn:test",1,2,3],[1958,1,[],"A","spawn:test",1,2,3]]"""
        );
        payload["_character_spawns"] = JObject.Parse(
            """{"character:first":[0],"character:second":[1]}"""
        );
        var data = GuideData.Parse(payload.ToString());
        Assert.NotSame(
            data.CharacterSpawns["character:first"][0],
            data.CharacterSpawns["character:second"][0]
        );
        Assert.Equal(0, data.All[0].Steps![0].Sources![0].CanonicalSpawn!.Condition);
        Assert.Null(data.All[0].Steps![0].Sources![0].CanonicalSpawn!.Entries);
    }

    [Theory]
    [InlineData("scene")]
    [InlineData("x")]
    [InlineData("y")]
    [InlineData("z")]
    [InlineData("zone")]
    [InlineData("zone_stable_key")]
    public void Marker_and_explicit_place_representations_must_agree(string field)
    {
        var payload = MarkerPayload();
        var location = JObject.Parse(
            """{"marker_stable_key":"spawn:test","place_key":"0","relation":"fixed"}"""
        );
        location[field] = field is "x" or "y" or "z" ? new JValue(99) : new JValue("conflict");
        payload["_place_sets"] = new JObject { ["places:test"] = new JArray(location) };
        Assert.Throws<InvalidDataException>(() => GuideData.Parse(payload.ToString()));
    }

    [Fact]
    public void Matching_explicit_marker_fields_are_accepted()
    {
        var payload = MarkerPayload();
        payload["_place_sets"] = JObject.Parse(
            """{"places:test":[{"marker_stable_key":"spawn:test","place_key":"0","relation":"fixed","scene":"A","x":1,"y":2,"z":3,"zone":"A zone","zone_stable_key":"zone:a"}]}"""
        );
        Assert.Equal("A", GuideData.Parse(payload.ToString()).PlaceSets["places:test"][0].Scene);
    }

    [Theory]
    [InlineData("scene")]
    [InlineData("x")]
    [InlineData("y")]
    [InlineData("z")]
    public void Duplicate_marker_positions_must_agree(string field)
    {
        var payload = MarkerPayload();
        var duplicate = JObject.Parse(
            """{"stable_key":"spawn:test","scene":"A","x":1,"y":2,"z":3}"""
        );
        duplicate[field] = field == "scene" ? new JValue("B") : new JValue(99);
        ((JArray)payload["_spawn_points"]!).Add(duplicate);
        payload["_character_spawns"] = JObject.Parse("""{"character:first":[0,1]}""");
        Assert.Throws<InvalidDataException>(() => GuideData.Parse(payload.ToString()));
    }

    [Theory]
    [InlineData("marker")]
    [InlineData("zone")]
    [InlineData("spawn_table")]
    [InlineData("negative_index")]
    [InlineData("large_index")]
    [InlineData("null_indexes")]
    public void Compact_marker_places_reject_missing_or_invalid_dependencies(string defect)
    {
        var payload = MarkerPayload();
        switch (defect)
        {
            case "marker":
                payload["_character_spawns"] = new JObject();
                break;
            case "zone":
                payload["_zone_lookup"] = new JObject();
                break;
            case "spawn_table":
                payload.Remove("_spawn_points");
                break;
            case "negative_index":
                payload["_character_spawns"]!["character:first"] = new JArray(-1);
                break;
            case "large_index":
                payload["_character_spawns"]!["character:first"] = new JArray(1);
                break;
            case "null_indexes":
                payload["_character_spawns"]!["character:first"] = JValue.CreateNull();
                break;
        }
        Assert.Throws<InvalidDataException>(() => GuideData.Parse(payload.ToString()));
    }

    [Fact]
    public void Full_places_without_a_character_marker_remain_readable()
    {
        var payload = MarkerPayload();
        payload.Remove("_spawn_points");
        payload.Remove("_character_spawns");
        payload["_place_sets"] = JObject.Parse(
            """{"places:test":[[3788,"spawn:test","0","fixed","A",1,2,3]]}"""
        );
        var location = GuideData.Parse(payload.ToString()).PlaceSets["places:test"][0];
        Assert.Equal("A", location.Scene);
        Assert.Equal(1, location.X);
    }
}
