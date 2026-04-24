using AdventureGuide.Frontier;
using AdventureGuide.Graph;
using AdventureGuide.Incremental;
using AdventureGuide.Markers;
using AdventureGuide.Markers.Queries;
using AdventureGuide.Navigation.Queries;
using AdventureGuide.Resolution;
using AdventureGuide.State;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests.Markers;

public sealed class MarkerProjectorTests
{
    [Fact]
    public void Project_CollapsesSharedSourceObjectiveMarkers()
    {
        var fixture = MarkerProjectorFixture.CreateTwoActiveQuestsSameSource();

        fixture.Projector.Project();

        var objectiveEntries = fixture
            .Projector.Markers.Where(e => e.Type == MarkerType.Objective)
            .ToList();

        var entry = Assert.Single(objectiveEntries);
        Assert.Equal("spawn:leaf-1", entry.SourceNodeKey);
        Assert.Equal(
            new[] { "quest:a", "quest:b" },
            fixture
                .Projector.GetContributingQuestKeys(entry.PositionNodeKey)!
                .OrderBy(x => x, StringComparer.Ordinal)
                .ToArray()
        );
    }

    [Fact]
    public void Project_UsesDeadSpawnLifecycle_ForKillTargetsWhenSnapshotTurnsDead()
    {
        var fixture = MarkerProjectorFixture.CreateKillQuest();

        fixture.LiveState.SnapshotsByPositionNodeKey["spawn:leaf-1"] = LiveSourceSnapshot.Dead(
            "spawn:leaf-1",
            "char:leaf",
            livePosition: (10f, 20f, 30f),
            anchoredLivePosition: (10f, 20f, 30f),
            respawnSeconds: 30f
        );

        fixture.Projector.Project();

        var entry = Assert.Single(
            fixture.Projector.Markers,
            e => e.SourceNodeKey == "spawn:leaf-1"
        );
        Assert.Equal(MarkerType.DeadSpawn, entry.Type);
        Assert.DoesNotContain(
            fixture.Projector.Markers,
            e => e.SourceNodeKey == "spawn:leaf-1" && e.Type == MarkerType.Objective
        );
    }

    [Fact]
    public void Project_UsesSingleDeadSpawnLifecycleMarker_ForSharedSourceAcrossQuestKinds()
    {
        var fixture = MarkerProjectorFixture.CreateTwoActiveQuestsSameSourceDifferentKinds();

        fixture.LiveState.SnapshotsByPositionNodeKey["spawn:leaf-1"] = LiveSourceSnapshot.Dead(
            "spawn:leaf-1",
            "char:leaf",
            livePosition: (10f, 20f, 30f),
            anchoredLivePosition: (10f, 20f, 30f),
            respawnSeconds: 30f
        );

        fixture.Projector.Project();

        var entries = fixture
            .Projector.Markers.Where(e => e.SourceNodeKey == "spawn:leaf-1")
            .ToList();

        var entry = Assert.Single(entries);
        Assert.Equal(MarkerType.DeadSpawn, entry.Type);
    }

    [Fact]
    public void Project_RendersSpawnCorpseAndChestLootMarkersTogether()
    {
        var fixture = MarkerProjectorFixture.CreateKillQuestWithLootTargets();
        fixture.LiveState.SnapshotsByPositionNodeKey["spawn:leaf-1"] = LiveSourceSnapshot.Dead(
            "spawn:leaf-1",
            "char:leaf",
            livePosition: (14f, 24.8f, 34f),
            anchoredLivePosition: (14f, 24.8f, 34f),
            respawnSeconds: 30f
        );

        fixture.Projector.Project();

        var markers = fixture.Projector.Markers.ToList();
        var dead = Assert.Single(markers, e => e.Type == MarkerType.DeadSpawn);
        Assert.Equal("spawn:leaf-1", dead.SourceNodeKey);
        Assert.Equal(1f, dead.X);
        Assert.Equal(4.5f, dead.Y);
        Assert.Equal(3f, dead.Z);

        var objectives = markers.Where(e => e.Type == MarkerType.Objective).ToList();
        Assert.Equal(2, objectives.Count);
        Assert.Contains(
            objectives,
            e => e.SourceNodeKey == "spawn:leaf-1" && e.X == 14f && e.Z == 34f
        );
        Assert.Contains(
            objectives,
            e => e.SourceNodeKey == "char:leaf" && e.X == 30f && e.Z == 40f
        );
    }

    [Fact]
    public void Project_RendersDisabledCharacterAsQuestLockedMarker()
    {
        var fixture = MarkerProjectorFixture.CreateKillQuest();
        fixture.LiveState.SnapshotsByPositionNodeKey["spawn:leaf-1"] = LiveSourceSnapshot.Disabled(
            "spawn:leaf-1",
            "char:leaf"
        );

        fixture.Projector.Project();

        var entry = Assert.Single(
            fixture.Projector.Markers,
            e => e.SourceNodeKey == "spawn:leaf-1"
        );
        Assert.Equal(MarkerType.QuestLocked, entry.Type);
        Assert.Equal("char:leaf\nDisabled", entry.SubText);
    }

    [Fact]
    public void Project_UsesSingleDisabledMarker_ForSharedSourceAcrossQuestKinds()
    {
        var fixture = MarkerProjectorFixture.CreateTwoActiveQuestsSameSourceDifferentKinds();
        fixture.LiveState.SnapshotsByPositionNodeKey["spawn:leaf-1"] = LiveSourceSnapshot.Disabled(
            "spawn:leaf-1",
            "char:leaf"
        );

        fixture.Projector.Project();

        var entries = fixture
            .Projector.Markers.Where(e => e.SourceNodeKey == "spawn:leaf-1")
            .ToList();

        var entry = Assert.Single(entries);
        Assert.Equal(MarkerType.QuestLocked, entry.Type);
    }

    internal sealed class MarkerProjectorFixture
    {
        private MarkerProjectorFixture(
            MarkerProjector projector,
            FakeMarkerLiveStateProvider liveState
        )
        {
            Projector = projector;
            LiveState = liveState;
        }

        public MarkerProjector Projector { get; }
        public FakeMarkerLiveStateProvider LiveState { get; }

        public static MarkerProjectorFixture CreateActiveQuest()
        {
            var guide = new CompiledGuideBuilder()
                .AddQuest("quest:a", dbName: "QUESTA")
                .AddCharacter("char:leaf", scene: "Town", x: 1f, y: 2f, z: 3f)
                .AddSpawnPoint("spawn:leaf-1", scene: "Town", x: 1f, y: 2f, z: 3f)
                .Build();

            var engine = new Engine<FactKey>();
            var sourceStates = new Dictionary<string, SpawnCategory>(StringComparer.Ordinal)
            {
                ["spawn:leaf-1"] = SpawnCategory.Alive,
                ["char:leaf"] = SpawnCategory.Alive,
            };

            var reader = new GuideReader(
                engine,
                new FakeInventory(),
                new FakeQuestState(
                    currentScene: "Town",
                    actionable: new[] { "QUESTA" },
                    implicitAvail: Array.Empty<string>(),
                    completed: Array.Empty<string>()
                ),
                new FakeTrackerState(Array.Empty<string>()),
                new FakeNavigationSet(Array.Empty<string>()),
                new FakeSourceState(sourceStates)
            );

            guide.TryGetNodeId("char:leaf", out int leafNodeId);
            guide.TryGetNodeId("spawn:leaf-1", out int spawnNodeId);

            var semantic = new ResolvedActionSemantic(
                NavigationGoalKind.Generic,
                NavigationTargetKind.Character,
                ResolvedActionKind.Talk,
                goalNodeKey: null,
                goalQuantity: null,
                keywordText: null,
                payloadText: null,
                targetIdentityText: "char:leaf",
                contextText: null,
                rationaleText: null,
                zoneText: "Town",
                availabilityText: null,
                preferredMarkerKind: QuestMarkerKind.Objective,
                markerPriority: 0
            );

            var resolvedTarget = new ResolvedTarget(
                targetNodeId: leafNodeId,
                positionNodeId: spawnNodeId,
                role: ResolvedTargetRole.Objective,
                semantic: semantic,
                x: 1f,
                y: 2f,
                z: 3f,
                scene: "Town",
                isLive: false,
                isActionable: true,
                questIndex: 0,
                requiredForQuestIndex: -1
            );

            var navigableQuery = engine.DefineQuery<Unit, NavigableQuestSet>(
                "NavigableQuestsStub",
                (ctx, _) =>
                {
                    ctx.RecordFact(new FactKey(FactKind.NavSet, "*"));
                    ctx.RecordFact(new FactKey(FactKind.TrackerSet, "*"));
                    ctx.RecordFact(new FactKey(FactKind.QuestActive, "*"));
                    return new NavigableQuestSet(new[] { "quest:a" });
                }
            );

            var resolutionRecord = new QuestResolutionRecord(
                questKey: "quest:a",
                currentScene: "Town",
                frontier: Array.Empty<FrontierEntry>(),
                compiledTargets: new[] { resolvedTarget },
                navigationTargetsFactory: () => Array.Empty<ResolvedQuestTarget>(),
                blockingZoneLineByScene: new Dictionary<string, int>(),
                detailStateFactory: () =>
                    new QuestDetailState(Array.Empty<QuestPhase>(), Array.Empty<int>())
            );
            var questResolutionQuery = engine.DefineQuery<(string, string), QuestResolutionRecord>(
                "QuestResolutionStub",
                (ctx, key) =>
                {
                    ctx.RecordFact(new FactKey(FactKind.QuestActive, key.Item1));
                    return resolutionRecord;
                }
            );

            var query = new MarkerCandidatesQuery(
                engine,
                guide,
                reader,
                navigableQuery,
                questResolutionQuery
            );

            var liveState = new FakeMarkerLiveStateProvider();
            var projector = new MarkerProjector(reader, query, liveState, guide);
            return new MarkerProjectorFixture(projector, liveState);
        }

        public static MarkerProjectorFixture CreateKillQuest()
        {
            var guide = new CompiledGuideBuilder()
                .AddQuest("quest:a", dbName: "QUESTA")
                .AddCharacter("char:leaf", scene: "Town", x: 1f, y: 2f, z: 3f)
                .AddSpawnPoint("spawn:leaf-1", scene: "Town", x: 1f, y: 2f, z: 3f)
                .Build();

            var engine = new Engine<FactKey>();
            var sourceStates = new Dictionary<string, SpawnCategory>(StringComparer.Ordinal)
            {
                ["spawn:leaf-1"] = SpawnCategory.Alive,
                ["char:leaf"] = SpawnCategory.Alive,
            };

            var reader = new GuideReader(
                engine,
                new FakeInventory(),
                new FakeQuestState(
                    currentScene: "Town",
                    actionable: new[] { "QUESTA" },
                    implicitAvail: Array.Empty<string>(),
                    completed: Array.Empty<string>()
                ),
                new FakeTrackerState(Array.Empty<string>()),
                new FakeNavigationSet(Array.Empty<string>()),
                new FakeSourceState(sourceStates)
            );

            guide.TryGetNodeId("char:leaf", out int leafNodeId);
            guide.TryGetNodeId("spawn:leaf-1", out int spawnNodeId);

            var semantic = new ResolvedActionSemantic(
                NavigationGoalKind.Generic,
                NavigationTargetKind.Character,
                ResolvedActionKind.Kill,
                goalNodeKey: null,
                goalQuantity: null,
                keywordText: null,
                payloadText: null,
                targetIdentityText: "char:leaf",
                contextText: null,
                rationaleText: null,
                zoneText: "Town",
                availabilityText: null,
                preferredMarkerKind: QuestMarkerKind.Objective,
                markerPriority: 0
            );

            var resolvedTarget = new ResolvedTarget(
                targetNodeId: leafNodeId,
                positionNodeId: spawnNodeId,
                role: ResolvedTargetRole.Objective,
                semantic: semantic,
                x: 1f,
                y: 2f,
                z: 3f,
                scene: "Town",
                isLive: false,
                isActionable: true,
                questIndex: 0,
                requiredForQuestIndex: -1
            );

            var navigableQuery = engine.DefineQuery<Unit, NavigableQuestSet>(
                "NavigableQuestsStub",
                (ctx, _) =>
                {
                    ctx.RecordFact(new FactKey(FactKind.NavSet, "*"));
                    ctx.RecordFact(new FactKey(FactKind.TrackerSet, "*"));
                    ctx.RecordFact(new FactKey(FactKind.QuestActive, "*"));
                    return new NavigableQuestSet(new[] { "quest:a" });
                }
            );

            var resolutionRecord = new QuestResolutionRecord(
                questKey: "quest:a",
                currentScene: "Town",
                frontier: Array.Empty<FrontierEntry>(),
                compiledTargets: new[] { resolvedTarget },
                navigationTargetsFactory: () => Array.Empty<ResolvedQuestTarget>(),
                blockingZoneLineByScene: new Dictionary<string, int>(),
                detailStateFactory: () =>
                    new QuestDetailState(Array.Empty<QuestPhase>(), Array.Empty<int>())
            );
            var questResolutionQuery = engine.DefineQuery<(string, string), QuestResolutionRecord>(
                "QuestResolutionStub",
                (ctx, key) =>
                {
                    ctx.RecordFact(new FactKey(FactKind.QuestActive, key.Item1));
                    return resolutionRecord;
                }
            );

            var query = new MarkerCandidatesQuery(
                engine,
                guide,
                reader,
                navigableQuery,
                questResolutionQuery
            );

            var liveState = new FakeMarkerLiveStateProvider();
            var projector = new MarkerProjector(reader, query, liveState, guide);
            return new MarkerProjectorFixture(projector, liveState);
        }

        public static MarkerProjectorFixture CreateKillQuestWithLootTargets()
        {
            var guide = new CompiledGuideBuilder()
                .AddQuest("quest:a", dbName: "QUESTA")
                .AddCharacter("char:leaf", scene: "Town", x: 1f, y: 2f, z: 3f)
                .AddSpawnPoint("spawn:leaf-1", scene: "Town", x: 1f, y: 2f, z: 3f)
                .Build();

            var engine = new Engine<FactKey>();
            var sourceStates = new Dictionary<string, SpawnCategory>(StringComparer.Ordinal)
            {
                ["spawn:leaf-1"] = SpawnCategory.Alive,
                ["char:leaf"] = SpawnCategory.Alive,
            };

            var reader = new GuideReader(
                engine,
                new FakeInventory(),
                new FakeQuestState(
                    currentScene: "Town",
                    actionable: new[] { "QUESTA" },
                    implicitAvail: Array.Empty<string>(),
                    completed: Array.Empty<string>()
                ),
                new FakeTrackerState(Array.Empty<string>()),
                new FakeNavigationSet(Array.Empty<string>()),
                new FakeSourceState(sourceStates)
            );

            guide.TryGetNodeId("char:leaf", out int leafNodeId);
            guide.TryGetNodeId("spawn:leaf-1", out int spawnNodeId);

            ResolvedActionSemantic BuildSemantic(
                ResolvedActionKind actionKind,
                string? payload = null
            ) =>
                new(
                    NavigationGoalKind.CollectItem,
                    NavigationTargetKind.Character,
                    actionKind,
                    goalNodeKey: null,
                    goalQuantity: null,
                    keywordText: null,
                    payloadText: payload,
                    targetIdentityText: "char:leaf",
                    contextText: null,
                    rationaleText: payload == null ? null : "Drops " + payload,
                    zoneText: "Town",
                    availabilityText: null,
                    preferredMarkerKind: QuestMarkerKind.Objective,
                    markerPriority: 0
                );

            var resolvedTargets = new[]
            {
                new ResolvedTarget(
                    targetNodeId: leafNodeId,
                    positionNodeId: spawnNodeId,
                    role: ResolvedTargetRole.Objective,
                    semantic: BuildSemantic(ResolvedActionKind.Kill),
                    x: 1f,
                    y: 2f,
                    z: 3f,
                    scene: "Town",
                    isLive: false,
                    isActionable: true,
                    questIndex: 0,
                    requiredForQuestIndex: -1
                ),
                new ResolvedTarget(
                    targetNodeId: leafNodeId,
                    positionNodeId: spawnNodeId,
                    role: ResolvedTargetRole.Objective,
                    semantic: BuildSemantic(ResolvedActionKind.LootCorpse, "Leaf"),
                    x: 14f,
                    y: 24.8f,
                    z: 34f,
                    scene: "Town",
                    isLive: true,
                    isActionable: true,
                    questIndex: 0,
                    requiredForQuestIndex: -1,
                    isGuaranteedLoot: true
                ),
                new ResolvedTarget(
                    targetNodeId: leafNodeId,
                    positionNodeId: leafNodeId,
                    role: ResolvedTargetRole.Objective,
                    semantic: BuildSemantic(ResolvedActionKind.LootChest, "Leaf"),
                    x: 30f,
                    y: 0f,
                    z: 40f,
                    scene: "Town",
                    isLive: true,
                    isActionable: true,
                    questIndex: 0,
                    requiredForQuestIndex: -1,
                    isGuaranteedLoot: true
                ),
            };

            var navigableQuery = engine.DefineQuery<Unit, NavigableQuestSet>(
                "NavigableQuestsStub",
                (ctx, _) =>
                {
                    ctx.RecordFact(new FactKey(FactKind.NavSet, "*"));
                    ctx.RecordFact(new FactKey(FactKind.TrackerSet, "*"));
                    ctx.RecordFact(new FactKey(FactKind.QuestActive, "*"));
                    return new NavigableQuestSet(new[] { "quest:a" });
                }
            );

            var resolutionRecord = new QuestResolutionRecord(
                questKey: "quest:a",
                currentScene: "Town",
                frontier: Array.Empty<FrontierEntry>(),
                compiledTargets: resolvedTargets,
                navigationTargetsFactory: () => Array.Empty<ResolvedQuestTarget>(),
                blockingZoneLineByScene: new Dictionary<string, int>(),
                detailStateFactory: () =>
                    new QuestDetailState(Array.Empty<QuestPhase>(), Array.Empty<int>())
            );
            var questResolutionQuery = engine.DefineQuery<(string, string), QuestResolutionRecord>(
                "QuestResolutionStub",
                (ctx, key) =>
                {
                    ctx.RecordFact(new FactKey(FactKind.QuestActive, key.Item1));
                    return resolutionRecord;
                }
            );

            var query = new MarkerCandidatesQuery(
                engine,
                guide,
                reader,
                navigableQuery,
                questResolutionQuery
            );
            var liveState = new FakeMarkerLiveStateProvider();
            var projector = new MarkerProjector(reader, query, liveState, guide);
            return new MarkerProjectorFixture(projector, liveState);
        }

        public static MarkerProjectorFixture CreateTwoActiveQuestsSameSource() =>
            CreateTwoActiveQuestsSameSource(
                new[]
                {
                    (
                        "quest:a",
                        QuestMarkerKind.Objective,
                        ResolvedActionKind.Talk,
                        ResolvedTargetRole.Objective
                    ),
                    (
                        "quest:b",
                        QuestMarkerKind.Objective,
                        ResolvedActionKind.Talk,
                        ResolvedTargetRole.Objective
                    ),
                }
            );

        public static MarkerProjectorFixture CreateTwoActiveQuestsSameSourceDifferentKinds() =>
            CreateTwoActiveQuestsSameSource(
                new[]
                {
                    (
                        "quest:a",
                        QuestMarkerKind.Objective,
                        ResolvedActionKind.Talk,
                        ResolvedTargetRole.Objective
                    ),
                    (
                        "quest:b",
                        QuestMarkerKind.TurnInReady,
                        ResolvedActionKind.Give,
                        ResolvedTargetRole.TurnIn
                    ),
                }
            );

        private static MarkerProjectorFixture CreateTwoActiveQuestsSameSource(
            IReadOnlyList<(
                string QuestKey,
                QuestMarkerKind MarkerKind,
                ResolvedActionKind ActionKind,
                ResolvedTargetRole Role
            )> quests
        )
        {
            var guide = new CompiledGuideBuilder()
                .AddQuest("quest:a", dbName: "QUESTA")
                .AddQuest("quest:b", dbName: "QUESTB")
                .AddCharacter("char:leaf", scene: "Town", x: 1f, y: 2f, z: 3f)
                .AddSpawnPoint("spawn:leaf-1", scene: "Town", x: 1f, y: 2f, z: 3f)
                .Build();

            var engine = new Engine<FactKey>();
            var sourceStates = new Dictionary<string, SpawnCategory>(StringComparer.Ordinal)
            {
                ["spawn:leaf-1"] = SpawnCategory.Alive,
                ["char:leaf"] = SpawnCategory.Alive,
            };

            var reader = new GuideReader(
                engine,
                new FakeInventory(),
                new FakeQuestState(
                    currentScene: "Town",
                    actionable: new[] { "QUESTA", "QUESTB" },
                    implicitAvail: Array.Empty<string>(),
                    completed: Array.Empty<string>()
                ),
                new FakeTrackerState(Array.Empty<string>()),
                new FakeNavigationSet(new[] { "quest:a", "quest:b" }),
                new FakeSourceState(sourceStates)
            );

            guide.TryGetNodeId("char:leaf", out int leafNodeId);
            guide.TryGetNodeId("spawn:leaf-1", out int spawnNodeId);

            ResolvedActionSemantic BuildSemantic(
                QuestMarkerKind markerKind,
                ResolvedActionKind actionKind
            ) =>
                new(
                    NavigationGoalKind.Generic,
                    NavigationTargetKind.Character,
                    actionKind,
                    goalNodeKey: null,
                    goalQuantity: null,
                    keywordText: null,
                    payloadText: null,
                    targetIdentityText: "char:leaf",
                    contextText: null,
                    rationaleText: null,
                    zoneText: "Town",
                    availabilityText: null,
                    preferredMarkerKind: markerKind,
                    markerPriority: 0
                );

            QuestResolutionRecord BuildRecord(
                string questKey,
                QuestMarkerKind markerKind,
                ResolvedActionKind actionKind,
                ResolvedTargetRole role
            ) =>
                new(
                    questKey: questKey,
                    currentScene: "Town",
                    frontier: Array.Empty<FrontierEntry>(),
                    compiledTargets: new[]
                    {
                        new ResolvedTarget(
                            targetNodeId: leafNodeId,
                            positionNodeId: spawnNodeId,
                            role: role,
                            semantic: BuildSemantic(markerKind, actionKind),
                            x: 1f,
                            y: 2f,
                            z: 3f,
                            scene: "Town",
                            isLive: false,
                            isActionable: true,
                            questIndex: 0,
                            requiredForQuestIndex: -1
                        ),
                    },
                    navigationTargetsFactory: () => Array.Empty<ResolvedQuestTarget>(),
                    blockingZoneLineByScene: new Dictionary<string, int>(),
                    detailStateFactory: () =>
                        new QuestDetailState(Array.Empty<QuestPhase>(), Array.Empty<int>())
                );

            var records = quests.ToDictionary(
                quest => quest.QuestKey,
                quest =>
                    BuildRecord(quest.QuestKey, quest.MarkerKind, quest.ActionKind, quest.Role),
                StringComparer.Ordinal
            );

            var navigableQuery = engine.DefineQuery<Unit, NavigableQuestSet>(
                "NavigableQuestsStub",
                (ctx, _) =>
                {
                    ctx.RecordFact(new FactKey(FactKind.NavSet, "*"));
                    ctx.RecordFact(new FactKey(FactKind.TrackerSet, "*"));
                    ctx.RecordFact(new FactKey(FactKind.QuestActive, "*"));
                    return new NavigableQuestSet(quests.Select(quest => quest.QuestKey).ToArray());
                }
            );

            var questResolutionQuery = engine.DefineQuery<(string, string), QuestResolutionRecord>(
                "QuestResolutionStub",
                (ctx, key) =>
                {
                    ctx.RecordFact(new FactKey(FactKind.QuestActive, key.Item1));
                    return records[key.Item1];
                }
            );

            var query = new MarkerCandidatesQuery(
                engine,
                guide,
                reader,
                navigableQuery,
                questResolutionQuery
            );

            var liveState = new FakeMarkerLiveStateProvider();
            var projector = new MarkerProjector(reader, query, liveState, guide);
            return new MarkerProjectorFixture(projector, liveState);
        }
    }

    internal sealed class FakeMarkerLiveStateProvider : ILiveSourceSnapshotProvider
    {
        public Dictionary<string, LiveSourceSnapshot> SnapshotsByPositionNodeKey { get; } =
            new(StringComparer.Ordinal);

        public SpawnInfo GetSpawnState(Node spawnNode) => default;

        public SpawnInfo GetCharacterState(Node characterNode) => default;

        public MiningInfo GetMiningState(Node miningNode) => default;

        public NodeState GetItemBagState(Node itemBagNode) => NodeState.Unknown;

        public LiveSourceSnapshot GetLiveSourceSnapshot(
            string? sourceNodeKey,
            Node positionNode,
            Node targetNode
        ) =>
            SnapshotsByPositionNodeKey.TryGetValue(positionNode.Key, out var snapshot)
                ? snapshot
                : LiveSourceSnapshot.Unknown(sourceNodeKey, targetNode.Key);
    }

    private sealed class FakeInventory : IInventoryFactSource
    {
        public int GetCount(string itemId) => 0;
    }

    private sealed class FakeQuestState : IQuestStateFactSource
    {
        private readonly HashSet<string> _actionable;
        private readonly HashSet<string> _implicitAvail;
        private readonly HashSet<string> _completed;

        public FakeQuestState(
            string currentScene,
            IEnumerable<string> actionable,
            IEnumerable<string> implicitAvail,
            IEnumerable<string> completed
        )
        {
            CurrentScene = currentScene;
            _actionable = new HashSet<string>(actionable, StringComparer.OrdinalIgnoreCase);
            _implicitAvail = new HashSet<string>(implicitAvail, StringComparer.OrdinalIgnoreCase);
            _completed = new HashSet<string>(completed, StringComparer.OrdinalIgnoreCase);
        }

        public string CurrentScene { get; }

        public bool IsActive(string dbName) => _actionable.Contains(dbName);

        public bool IsCompleted(string dbName) => _completed.Contains(dbName);

        public IEnumerable<string> GetActionableQuestDbNames() => _actionable;

        public IEnumerable<string> GetImplicitlyAvailableQuestDbNames() => _implicitAvail;
    }

    private sealed class FakeTrackerState : ITrackerStateFactSource
    {
        public FakeTrackerState(IReadOnlyList<string> trackedQuests) =>
            TrackedQuests = trackedQuests;

        public IReadOnlyList<string> TrackedQuests { get; }
    }

    private sealed class FakeNavigationSet : INavigationSetFactSource
    {
        public FakeNavigationSet(IReadOnlyCollection<string> keys) => Keys = keys;

        public IReadOnlyCollection<string> Keys { get; }
    }

    private sealed class FakeSourceState : ISourceStateFactSource
    {
        private readonly Dictionary<string, SpawnCategory> _states;

        public FakeSourceState(Dictionary<string, SpawnCategory> states) => _states = states;

        public SpawnCategory GetCategory(Node node) =>
            _states.TryGetValue(node.Key, out var cat) ? cat : SpawnCategory.NotApplicable;

        public IReadOnlyCollection<string> GetSourceFactKeys(Node node) => new[] { node.Key };
    }
}
