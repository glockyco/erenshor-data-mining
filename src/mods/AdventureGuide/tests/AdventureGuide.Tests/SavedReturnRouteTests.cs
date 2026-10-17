using AdventureGuide.Data;
using AdventureGuide.Navigation;
using AdventureGuide.State;
using Newtonsoft.Json;
using UnityEngine;

namespace AdventureGuide.Tests;

[Collection("Game state")]
public sealed class SavedReturnRouteTests
{
    private const string ReturnLine = "zoneline:home:return";

    private sealed class Facts : IGateFacts, IQuestGameState
    {
        public string? ReturnScene = "A";
        public Vector3? ReturnLanding = new Vector3(11, 12, 13);
        public int PlayerLevel => 1;

        public bool IsQuestCompleted(string questDbName) => false;

        public bool ReadAccountState(string key) =>
            key == EncounterStateKeys.ReliquaryClaimed ? false : throw new ArgumentException(key);

        public string? ReadCharacterZoneState(string key) =>
            key == EncounterStateKeys.ReturnZone ? ReturnScene : throw new ArgumentException(key);

        public Vector3? ReadCharacterPositionState(string key) =>
            key == EncounterStateKeys.ReturnLanding
                ? ReturnLanding
                : throw new ArgumentException(key);

        public int ItemCount(string itemStableKey) => 0;

        public bool IsOnKeyring(string gameId) => false;

        public string? StoredItemIn(string slot) => null;

        public Vector3? PlayerPosition => null;

        public void CopyActiveQuestsTo(HashSet<string> destination) { }

        public void CopyCompletedQuestsTo(HashSet<string> destination) { }

        public void CopyInventoryCountsTo(Dictionary<string, int> destination) { }
    }

    private static GuideWrapper Wrapper(bool locked = false) =>
        new()
        {
            Version = 8,
            Quests = [],
            Encounters = new()
            {
                Placements = [],
                Conditions = [],
                Completions = [],
                EventConditions = [],
            },
            ZoneLookup = new()
            {
                ["Home"] = new() { StableKey = "zone:home", DisplayName = "Home" },
                ["A"] = new() { StableKey = "zone:a", DisplayName = "Destination A" },
                ["B"] = new() { StableKey = "zone:b", DisplayName = "Destination B" },
                ["Static"] = new() { StableKey = "zone:static", DisplayName = "Static" },
                ["Other"] = new() { StableKey = "zone:other", DisplayName = "Other" },
                ["Hidden"] = new() { StableKey = "zone:hidden", DisplayName = "Hidden" },
            },
            ZoneLines =
            [
                new()
                {
                    StableKey = ReturnLine,
                    Scene = "Home",
                    X = 3,
                    Y = 4,
                    Z = 5,
                    DestinationZoneKey = "zone:hidden",
                    DestinationDisplay = "Hidden",
                    LandingX = 90,
                    LandingY = 91,
                    LandingZ = 92,
                    Condition = locked ? 0 : null,
                },
                new()
                {
                    StableKey = "zoneline:home:static",
                    Scene = "Home",
                    DestinationZoneKey = "zone:static",
                    DestinationDisplay = "Static",
                    LandingX = 21,
                    LandingY = 22,
                    LandingZ = 23,
                },
                new()
                {
                    StableKey = "zoneline:other:return-copy",
                    Scene = "Other",
                    DestinationZoneKey = "zone:hidden",
                    DestinationDisplay = "Hidden",
                },
            ],
            ZoneLineDestinationContexts = new()
            {
                [ReturnLine] = new()
                {
                    ZoneLineStableKey = ReturnLine,
                    Kind = "stored_return",
                    DestinationStateKey = EncounterStateKeys.ReturnZone,
                    LandingStateKey = EncounterStateKeys.ReturnLanding,
                    SourceKey = "script:home:return-controller",
                },
            },
            Conditions = locked
                ?
                [
                    [
                        [new() { Kind = GateAtomKind.KeyHeld, Ref = "item:key" }],
                    ],
                ]
                : [],
            GateItems = new()
            {
                ["item:key"] = new() { Name = "Key", GameId = "key" },
            },
        };

    private static (GuideData data, ZoneGraph graph) Build(GuideWrapper wrapper, Facts facts)
    {
        var data = GuideData.FromWrapper(wrapper);
        return (data, new ZoneGraph(data, new GateConditions(data, facts)));
    }

    private static void AssertLanding(Vector3? actual, float x, float y, float z)
    {
        Assert.True(actual.HasValue);
        Assert.Equal(x, actual.Value.x);
        Assert.Equal(y, actual.Value.y);
        Assert.Equal(z, actual.Value.z);
    }

    [Fact]
    public void Shipping_return_routes_directly_when_native_saved_state_is_valid()
    {
        using var stream = typeof(GuideData).Assembly.GetManifestResourceStream(
            "AdventureGuide.quest-guide.json"
        );
        Assert.NotNull(stream);
        using var reader = new StreamReader(stream);
        var data = GuideData.Parse(reader.ReadToEnd());
        var facts = new Facts
        {
            ReturnScene = "ShiveringStep",
            ReturnLanding = new Vector3(11, 12, 13),
        };
        var graph = new ZoneGraph(data, new GateConditions(data, facts));
        var line = data.ZoneLines.First(entry =>
            data.ZoneLineDestinationContexts.ContainsKey(entry.StableKey!)
        );
        var destination = graph.ResolveDestination(line);
        Assert.NotNull(destination);
        Assert.Equal(facts.ReturnScene, destination.Value.Scene);
        AssertLanding(destination.Value.Landing, 11, 12, 13);
        var route = graph.FindRoute(line.Scene!, facts.ReturnScene);
        Assert.NotNull(route);
        Assert.False(route.IsLocked);
        Assert.Equal(new[] { line.Scene, facts.ReturnScene }, route.Path);

        facts.ReturnScene = null;
        graph.Rebuild();
        Assert.Null(graph.ResolveDestination(line));
    }

    [Fact]
    public void Saved_scene_projects_to_zone_key_and_preserves_physical_line_identity()
    {
        var facts = new Facts { ReturnScene = "a" };
        var (data, graph) = Build(Wrapper(), facts);
        var line = data.ZoneLines[0];
        var destination = graph.ResolveDestination(line);
        Assert.NotNull(destination);
        Assert.Equal("zone:a", destination.Value.ZoneKey);
        Assert.Equal("A", destination.Value.Scene);
        AssertLanding(destination.Value.Landing, 11, 12, 13);
        Assert.Equal("zone:a", graph.FindRoute("Home", "A")!.NextHopZoneKey);
        Assert.Equal("zone:a", graph.BuildRouteLookup("Home").FindRoute("A")!.NextHopZoneKey);
        Assert.Null(graph.FindRoute("Home", "Hidden"));
        Assert.Same(line, Assert.Single(graph.LinesForHop("Home", "A")));
        Assert.Equal(ReturnLine, line.StableKey);
        Assert.Equal((3f, 4f, 5f), (line.X, line.Y, line.Z));
        Assert.Equal("zone:hidden", line.DestinationZoneKey);
        AssertLanding(graph.ResolveDestination(data.ZoneLines[1])!.Value.Landing, 21, 22, 23);
    }

    [Fact]
    public void Character_switch_changes_destination_landing_and_entry_selection()
    {
        var facts = new Facts();
        var (data, graph) = Build(Wrapper(), facts);
        var placementA = new SpawnPoint { Scene = "A", Entries = [0] };
        var placementB = new SpawnPoint { Scene = "B", Entries = [0] };
        Assert.Same(
            data.ZoneLines[0],
            graph.GetPlacementRoute(placementA, "Home")!.Value.EntryLine
        );
        Assert.Null(graph.GetPlacementRoute(placementB, "Home"));
        facts.ReturnScene = "B";
        facts.ReturnLanding = new Vector3(31, 32, 33);
        graph.Rebuild();
        Assert.Null(graph.FindRoute("Home", "A"));
        Assert.Equal("zone:b", graph.FindRoute("Home", "B")!.NextHopZoneKey);
        AssertLanding(graph.ResolveDestination(data.ZoneLines[0])!.Value.Landing, 31, 32, 33);
        Assert.Null(graph.GetPlacementRoute(placementA, "Home"));
        Assert.Same(
            data.ZoneLines[0],
            graph.GetPlacementRoute(placementB, "Home")!.Value.EntryLine
        );
        Assert.Empty(graph.LinesForHop("Home", "A"));
        Assert.Equal("zone:static", graph.FindRoute("Home", "Static")!.NextHopZoneKey);
        Assert.Equal("zone:hidden", graph.FindRoute("Other", "Hidden")!.NextHopZoneKey);
    }

    public static TheoryData<string?, Vector3?> InvalidStates =>
        new()
        {
            { null, new Vector3(1, 2, 3) },
            { "", new Vector3(1, 2, 3) },
            { " ", new Vector3(1, 2, 3) },
            { "unknown", new Vector3(1, 2, 3) },
            { "zone:a", new Vector3(1, 2, 3) },
            { "Destination A", new Vector3(1, 2, 3) },
            { "A", null },
            { "A", new Vector3(float.NaN, 2, 3) },
            { "A", new Vector3(1, float.PositiveInfinity, 3) },
            { "A", new Vector3(1, 2, float.NegativeInfinity) },
        };

    [Theory]
    [MemberData(nameof(InvalidStates))]
    public void Invalid_state_is_absent_even_from_locked_fallback(string? scene, Vector3? landing)
    {
        var facts = new Facts();
        var (data, graph) = Build(Wrapper(locked: true), facts);
        Assert.True(graph.FindRoute("Home", "A")!.IsLocked);
        facts.ReturnScene = scene;
        facts.ReturnLanding = landing;
        graph.Rebuild();
        Assert.Null(graph.ResolveDestination(data.ZoneLines[0]));
        Assert.Null(graph.FindRoute("Home", "A"));
        Assert.Null(graph.FindRoute("Home", "Hidden"));
        Assert.Null(graph.BuildRouteLookup("Home").FindRoute("A"));
        Assert.Null(graph.GetPlacementRoute(new SpawnPoint { Scene = "A", Entries = [0] }, "Home"));
        Assert.Empty(graph.LinesForHop("Home", "A"));
        Assert.NotNull(graph.FindRoute("Home", "Static"));
        Assert.NotNull(graph.FindRoute("Other", "Hidden"));
    }

    [Fact]
    public void A_real_zero_landing_is_valid_but_is_not_invented_for_missing_state()
    {
        var facts = new Facts { ReturnLanding = new Vector3(0, 0, 0) };
        var (data, graph) = Build(Wrapper(), facts);
        AssertLanding(graph.ResolveDestination(data.ZoneLines[0])!.Value.Landing, 0, 0, 0);
        facts.ReturnLanding = null;
        Assert.Null(graph.ResolveDestination(data.ZoneLines[0]));
    }

    [Fact]
    public void Unchanged_facts_keep_existing_lookup_results_and_static_missing_landings()
    {
        var (data, graph) = Build(Wrapper(), new Facts());
        var lookup = graph.BuildRouteLookup("Home");
        var route = lookup.FindRoute("A");
        Assert.Same(route, lookup.FindRoute("A"));
        Assert.Null(graph.ResolveDestination(data.ZoneLines[2])!.Value.Landing);
        Assert.Equal("zone:hidden", graph.ResolveDestination(data.ZoneLines[2])!.Value.ZoneKey);
    }

    [Fact]
    public void Primitive_observation_rebuilds_once_per_change_and_not_for_unchanged_saved_state()
    {
        var data = GuideData.FromWrapper(Wrapper());
        var facts = new Facts();
        var tracker = new QuestStateTracker(data, new EntityRegistry(), facts);
        tracker.OnSceneChanged("Home");
        var graph = new ZoneGraph(data, tracker.Gates);
        int rebuilds = 0;
        tracker.PrimitiveStateChanged += () =>
        {
            rebuilds++;
            graph.Rebuild();
        };
        int version = tracker.Version;
        tracker.Update(0);
        Assert.Equal(version, tracker.Version);
        Assert.Equal(0, rebuilds);
        facts.ReturnScene = "B";
        facts.ReturnLanding = new Vector3(31, 32, 33);
        tracker.Update(0);
        Assert.Equal(version + 1, tracker.Version);
        Assert.Equal(1, rebuilds);
        Assert.Null(graph.FindRoute("Home", "A"));
        Assert.NotNull(graph.FindRoute("Home", "B"));
        tracker.Update(0);
        Assert.Equal(1, rebuilds);
        facts.ReturnLanding = new Vector3(float.NaN, 32, 33);
        tracker.Update(0);
        Assert.Equal(2, rebuilds);
        Assert.Null(graph.FindRoute("Home", "B"));
        tracker.Update(0);
        Assert.Equal(2, rebuilds);
    }

    [Theory]
    [InlineData("line")]
    [InlineData("kind")]
    [InlineData("zone-key")]
    [InlineData("landing-key")]
    [InlineData("source")]
    [InlineData("mismatch")]
    [InlineData("duplicate")]
    public void Malformed_or_unknown_context_binding_fails_load(string defect)
    {
        var wrapper = Wrapper();
        var context = wrapper.ZoneLineDestinationContexts![ReturnLine];
        switch (defect)
        {
            case "line":
                wrapper.ZoneLines![0].StableKey = "zoneline:missing";
                break;
            case "kind":
                context.Kind = "static";
                break;
            case "zone-key":
                context.DestinationStateKey = "character_state:unknown";
                break;
            case "landing-key":
                context.LandingStateKey = "character_state:unknown";
                break;
            case "source":
                context.SourceKey = "";
                break;
            case "mismatch":
                context.ZoneLineStableKey = "zoneline:other";
                break;
            case "duplicate":
                wrapper.ZoneLines![1].StableKey = ReturnLine;
                break;
        }
        Assert.Throws<InvalidDataException>(() => GuideData.FromWrapper(wrapper));
    }

    [Fact]
    public void Serialized_contract_preserves_canonical_fields_and_requires_context_dictionary()
    {
        var json = JsonConvert.SerializeObject(Wrapper());
        var data = GuideData.Parse(json);
        var row = Assert.Single(data.ZoneLineDestinationContexts).Value;
        Assert.Equal(ReturnLine, row.ZoneLineStableKey);
        Assert.Equal("stored_return", row.Kind);
        Assert.Equal(EncounterStateKeys.ReturnZone, row.DestinationStateKey);
        Assert.Equal(EncounterStateKeys.ReturnLanding, row.LandingStateKey);
        Assert.Equal("script:home:return-controller", row.SourceKey);
        var payload = Newtonsoft.Json.Linq.JObject.Parse(json);
        payload.Remove("_zone_line_destination_contexts");
        Assert.Throws<JsonSerializationException>(() => GuideData.Parse(payload.ToString()));
    }
}
