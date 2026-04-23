using AdventureGuide.Frontier;
using AdventureGuide.Graph;
using AdventureGuide.Incremental;
using AdventureGuide.Navigation;
using AdventureGuide.Navigation.Queries;
using AdventureGuide.Resolution;
using AdventureGuide.Resolution.Queries;
using AdventureGuide.State;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests.Navigation.Queries;

public sealed class NavigationTargetSnapshotsQueryTests
{
    [Fact]
    public void Read_ReturnsEmptySceneSnapshot_WhenNoSelectorTargetsExist()
    {
        var fixture = NavigationTargetSnapshotsFixture.Create();
        fixture.TargetKeys = Array.Empty<string>();

        var result = fixture.Engine.Read(fixture.Query.Query, "Town");

        Assert.Equal("Town", result.Scene);
        Assert.Empty(result.Snapshots);
        Assert.False(result.TryGet("quest:a", out _));
    }

    [Fact]
    public void Read_PreservesPerKeySnapshotReference_WhenMembershipChanges()
    {
        var fixture = NavigationTargetSnapshotsFixture.Create();
        fixture.TargetKeys = new[] { "quest:a" };
        var first = fixture.Engine.Read(fixture.Query.Query, "Town");
        var firstSnapshot = Assert.Single(first.Snapshots);

        fixture.TargetKeys = new[] { "quest:a", "quest:b" };
        fixture.Engine.InvalidateFacts(new[] { new FactKey(FactKind.NavSet, "*") });
        var second = fixture.Engine.Read(fixture.Query.Query, "Town");

        Assert.NotSame(first, second);
        Assert.Equal(new[] { "quest:a", "quest:b" }, second.Snapshots.Select(s => s.NodeKey).ToArray());
        Assert.True(second.TryGet("quest:a", out var preserved));
        Assert.True(second.TryGet("quest:b", out var added));
        Assert.Same(firstSnapshot, preserved);
        Assert.Same(fixture.Resolutions["quest:b"].NavigationTargets, added.Targets);
    }

    [Fact]
    public void Read_PreservesExactRequestedScene_WhenSceneKeysDifferOnlyByCase()
    {
        var fixture = NavigationTargetSnapshotsFixture.Create();
        fixture.TargetKeys = new[] { "quest:a" };

        var first = fixture.Engine.Read(fixture.Query.Query, "Town");
        var second = fixture.Engine.Read(fixture.Query.Query, "town");

        var firstSnapshot = Assert.Single(first.Snapshots);
        var secondSnapshot = Assert.Single(second.Snapshots);
        Assert.Equal("Town", first.Scene);
        Assert.Equal("Town", firstSnapshot.Scene);
        Assert.Equal("town", second.Scene);
        Assert.Equal("town", secondSnapshot.Scene);
        Assert.NotSame(firstSnapshot, secondSnapshot);
        Assert.Same(firstSnapshot.Targets, secondSnapshot.Targets);
    }

    [Fact]
    public void Read_RemovesStaleEntriesFromUntouchedSceneBuckets_WhenMembershipShrinks()
    {
        var fixture = NavigationTargetSnapshotsFixture.Create();
        fixture.TargetKeys = new[] { "quest:a" };

        fixture.Engine.Read(fixture.Query.Query, "Town");
        fixture.Engine.Read(fixture.Query.Query, "Forest");

        fixture.TargetKeys = new[] { "quest:b" };
        fixture.Engine.InvalidateFacts(new[] { new FactKey(FactKind.NavSet, "*") });
        fixture.Engine.Read(fixture.Query.Query, "Town");

        var cache = fixture.GetSnapshotCacheByScene();
        Assert.True(cache.TryGetValue("Town", out var townCache));
        Assert.Equal(new[] { "quest:b" }, townCache.Keys.OrderBy(key => key).ToArray());
        Assert.False(cache.ContainsKey("Forest"));
    }

    [Fact]
    public void Read_Backdates_WhenChildQuestResolutionRecordsRemainUnchanged()
    {
        var fixture = NavigationTargetSnapshotsFixture.Create();
        fixture.TargetKeys = new[] { "quest:a" };
        var first = fixture.Engine.Read(fixture.Query.Query, "Town");
        int parentComputeCount = fixture.ParentComputeCount;
        int childComputeCount = fixture.ChildComputeCount;

        fixture.Engine.InvalidateFacts(new[] { new FactKey(FactKind.QuestActive, "quest:a") });
        var second = fixture.Engine.Read(fixture.Query.Query, "Town");

        Assert.True(fixture.ChildComputeCount > childComputeCount);
        Assert.Equal(parentComputeCount, fixture.ParentComputeCount);
        Assert.Same(first, second);
        Assert.Same(first.Snapshots[0], second.Snapshots[0]);
    }

    [Fact]
    public void Read_SharesCompiledTargetsBatchSessionAcrossQuestEntries()
    {
        var fixture = NavigationTargetSnapshotsFixture.Create();
        fixture.TargetKeys = new[] { "quest:a", "quest:b" };

        fixture.Engine.Read(fixture.Query.Query, "Town");

        Assert.Equal(2, fixture.CompiledTargetSessionsByQuest.Count);
        Assert.NotNull(fixture.CompiledTargetSessionsByQuest["quest:a"]);
        Assert.Same(
            fixture.CompiledTargetSessionsByQuest["quest:a"],
            fixture.CompiledTargetSessionsByQuest["quest:b"]);
        Assert.Null(CompiledTargetsQuery.CurrentSharedResolutionSession);
    }

    [Fact]
    public void Read_ResolvesExplicitNonQuestNavTargets()
    {
        var fixture = NavigationTargetSnapshotsFixture.Create();
        fixture.TargetKeys = new[] { "item:coin" };

        var result = fixture.Engine.Read(fixture.Query.Query, "Town");

        var snapshot = Assert.Single(result.Snapshots);
        Assert.Equal("item:coin", snapshot.NodeKey);
        var target = Assert.Single(snapshot.Targets);
        Assert.Equal("char:collector", target.TargetNodeKey);
        Assert.Equal("spawn:collector", target.SourceKey);
    }

    private sealed class NavigationTargetSnapshotsFixture
    {
        private NavigationTargetSnapshotsFixture(
            Engine<FactKey> engine,
            NavigationTargetSnapshotsQuery query,
            Dictionary<string, QuestResolutionRecord> resolutions,
            Dictionary<string, SourceResolver.ResolutionSession?> compiledTargetSessionsByQuest)
        {
            Engine = engine;
            Query = query;
            Resolutions = resolutions;
            CompiledTargetSessionsByQuest = compiledTargetSessionsByQuest;
            TargetKeys = Array.Empty<string>();
        }

        public Engine<FactKey> Engine { get; }
        public NavigationTargetSnapshotsQuery Query { get; }
        public Dictionary<string, QuestResolutionRecord> Resolutions { get; }
        public Dictionary<string, SourceResolver.ResolutionSession?> CompiledTargetSessionsByQuest { get; }
        public IReadOnlyList<string> TargetKeys { get; set; }
        public int ParentComputeCount { get; private set; }
        public int ChildComputeCount { get; private set; }

        public static NavigationTargetSnapshotsFixture Create()
        {
            const string scene = "Town";
            var guide = new CompiledGuideBuilder()
                .AddQuest("quest:a", dbName: "QUESTA")
                .AddQuest("quest:b", dbName: "QUESTB")
                .AddCharacter("char:collector")
                .AddSpawnPoint("spawn:collector", scene: scene, x: 1f, y: 2f, z: 3f)
                .AddEdge("char:collector", "spawn:collector", EdgeType.HasSpawn)
                .AddItem("item:coin")
                .AddItemSource("item:coin", "char:collector")
                .Build();
            var engine = new Engine<FactKey>();
            var resolutions = new Dictionary<string, QuestResolutionRecord>(StringComparer.Ordinal)
            {
                ["quest:a"] = CreateRecord("quest:a", scene),
                ["quest:b"] = CreateRecord("quest:b", scene)
            };
            var compiledTargetSessionsByQuest = new Dictionary<string, SourceResolver.ResolutionSession?>(StringComparer.Ordinal);
            var resolver = BuildResolver(guide, engine);

            NavigationTargetSnapshotsFixture? fixture = null;
            var targetSetQuery = engine.DefineQuery<Unit, SelectorTargetSet>(
                "SelectorTargetSetStub",
                (ctx, _) =>
                {
                    ctx.RecordFact(new FactKey(FactKind.NavSet, "*"));
                    return new SelectorTargetSet(fixture!.TargetKeys);
                });
            var resolutionQuery = engine.DefineQuery<(string QuestKey, string Scene), QuestResolutionRecord>(
                "QuestResolutionStub",
                (ctx, key) =>
                {
                    fixture!.ChildComputeCount++;
                    fixture.CompiledTargetSessionsByQuest[key.QuestKey] = CompiledTargetsQuery.CurrentSharedResolutionSession;
                    ctx.RecordFact(new FactKey(FactKind.QuestActive, key.QuestKey));
                    return fixture.Resolutions[key.QuestKey];
                });
            var query = new NavigationTargetSnapshotsQuery(
                engine,
                guide,
                resolver,
                targetSetQuery,
                resolutionQuery,
                () => fixture!.ParentComputeCount++);
            fixture = new NavigationTargetSnapshotsFixture(
                engine,
                query,
                resolutions,
                compiledTargetSessionsByQuest);
            return fixture;
        }

        public Dictionary<string, Dictionary<string, NavigationTargetSnapshot>> GetSnapshotCacheByScene()
        {
            var field = typeof(NavigationTargetSnapshotsQuery).GetField(
                "_snapshotCacheByScene",
                System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic);
            Assert.NotNull(field);
            return Assert.IsType<Dictionary<string, Dictionary<string, NavigationTargetSnapshot>>>(
                field!.GetValue(Query));
        }

        private static NavigationTargetResolver BuildResolver(AdventureGuide.CompiledGuide.CompiledGuide guide, Engine<FactKey> engine)
        {
            var phases = new QuestPhaseTracker(guide);
            phases.Initialize(
                Array.Empty<string>(),
                Array.Empty<string>(),
                new Dictionary<string, int>(),
                Array.Empty<string>());
            var frontier = new EffectiveFrontier(guide, phases);
            var unlocks = new UnlockPredicateEvaluator(guide, phases);
            var positionRegistry = TestPositionResolvers.Create(guide);
            var sourceResolver = new SourceResolver(
                guide,
                phases,
                unlocks,
                new StubLivePositionProvider(),
                positionRegistry);
            var reader = ResolutionTestFactory.BuildService(
                guide,
                frontier,
                sourceResolver,
                phases,
                zoneRouter: null,
                engine: engine,
                positionRegistry: positionRegistry,
                trackerState: new TrackerState(),
                navSet: new NavigationSet());
            return new NavigationTargetResolver(
                guide,
                reader,
                null,
                positionRegistry,
                ResolutionTestFactory.BuildProjector(guide, null));
        }

        private static QuestResolutionRecord CreateRecord(string questKey, string scene)
        {
            return new QuestResolutionRecord(
                questKey,
                scene,
                Array.Empty<FrontierEntry>(),
                Array.Empty<ResolvedTarget>(),
                () => Array.Empty<ResolvedQuestTarget>(),
                new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase),
                () => new QuestDetailState(Array.Empty<QuestPhase>(), Array.Empty<int>()));
        }
    }
}
