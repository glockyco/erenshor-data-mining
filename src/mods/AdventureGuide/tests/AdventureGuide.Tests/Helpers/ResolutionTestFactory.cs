using AdventureGuide.Diagnostics;
using AdventureGuide.Frontier;
using AdventureGuide.Graph;
using AdventureGuide.Incremental;
using AdventureGuide.Navigation;
using AdventureGuide.Position;
using AdventureGuide.Resolution;
using AdventureGuide.Resolution.Queries;
using AdventureGuide.State;
using AdventureGuide.UI.Tree;
using CompiledGuideModel = AdventureGuide.CompiledGuide.CompiledGuide;

namespace AdventureGuide.Tests.Helpers;

internal static class ResolutionTestFactory
{
    public static QuestTargetProjector BuildProjector(
        CompiledGuideModel guide,
        ZoneRouter? zoneRouter = null)
    {
        return new QuestTargetProjector(guide, zoneRouter);
    }

    public static GuideReader BuildService(
        CompiledGuideModel guide,
        EffectiveFrontier frontier,
        SourceResolver sourceResolver,
        QuestPhaseTracker phases,
        ZoneRouter? zoneRouter = null,
        Engine<FactKey>? engine = null,
        PositionResolverRegistry? positionRegistry = null,
        TrackerState? trackerState = null,
        NavigationSet? navSet = null)
    {
        var questState = phases.State;

        var state = trackerState ?? new TrackerState();
        var navigationSet = navSet ?? new NavigationSet();
        var engineValue = engine ?? new Engine<FactKey>();
        var reader = new GuideReader(engineValue, questState, questState, state, navigationSet);
        var projector = BuildProjector(guide, zoneRouter);
        var compiledTargets = new CompiledTargetsQuery(
            engineValue,
            guide,
            frontier,
            new QuestTargetResolver(guide, frontier, sourceResolver, zoneRouter),
            reader);
        var blockingZones = new BlockingZonesQuery(engineValue, guide, zoneRouter);
        var resolutionQuery = new QuestResolutionQuery(
            engineValue,
            guide,
            phases,
            compiledTargets,
            blockingZones,
            projector);
        reader.SetQuestResolutionQuery(resolutionQuery);
        return reader;
    }

    public static (GuideReader Reader, SpecTreeProjector Projector) BuildSpecTreeProjector(
        CompiledGuideModel guide,
        QuestPhaseTracker phases,
        ZoneRouter? zoneRouter = null,
        Func<string>? currentSceneProvider = null,
        DiagnosticsCore? diagnostics = null,
        PositionResolverRegistry? positionRegistry = null)
    {
        var registry = positionRegistry ?? TestPositionResolvers.Create(guide);
        var sourceResolver = new SourceResolver(
            guide,
            phases,
            new UnlockPredicateEvaluator(guide, phases),
            new StubLivePositionProvider(),
            registry,
            zoneRouter);
        var frontier = new EffectiveFrontier(guide, phases);
        var reader = BuildService(
            guide,
            frontier,
            sourceResolver,
            phases,
            zoneRouter,
            positionRegistry: registry,
            trackerState: new TrackerState(),
            navSet: new NavigationSet());
        return (
            reader,
            new SpecTreeProjector(
                guide,
                reader,
                currentSceneProvider: currentSceneProvider,
                diagnostics: diagnostics));
    }

    public static NavigationTargetResolver BuildNavigationResolver(
        CompiledGuideModel guide,
        EffectiveFrontier frontier,
        SourceResolver sourceResolver,
        QuestPhaseTracker phases,
        ZoneRouter? zoneRouter = null,
        DiagnosticsCore? diagnostics = null,
        PositionResolverRegistry? positionRegistry = null,
        TrackerState? trackerState = null,
        NavigationSet? navSet = null,
        Engine<FactKey>? engine = null)
    {
        var registry = positionRegistry ?? TestPositionResolvers.Create(guide);
        var reader = BuildService(
            guide,
            frontier,
            sourceResolver,
            phases,
            zoneRouter,
            engine,
            registry,
            trackerState,
            navSet);
        return new NavigationTargetResolver(
            guide,
            reader,
            zoneRouter,
            registry,
            BuildProjector(guide, zoneRouter),
            diagnostics);
    }

    public static (GuideReader Reader, InvalidationHarness Harness) BuildInvalidationHarness()
    {
        const string scene = "Forest";
        var guide = new CompiledGuideBuilder()
            .AddItem("item:water-flask")
            .AddCharacter("char:well", scene: scene, x: 10f, y: 20f, z: 30f)
            .AddItemSource(
                "item:water-flask",
                "char:well",
                edgeType: (byte)EdgeType.GivesItem,
                sourceType: (byte)NodeType.Character)
            .AddQuest(
                "quest:fetch-water",
                dbName: "FETCHWATER",
                requiredItems: new[] { ("item:water-flask", 1) })
            .AddItem("item:wolf-pelt")
            .AddCharacter("char:wolf", scene: scene, x: 40f, y: 50f, z: 60f)
            .AddItemSource(
                "item:wolf-pelt",
                "char:wolf",
                edgeType: (byte)EdgeType.DropsItem,
                sourceType: (byte)NodeType.Character)
            .AddQuest(
                "quest:slay-wolves",
                dbName: "SLAYWOLVES",
                requiredItems: new[] { ("item:wolf-pelt", 1) })
            .Build();
        var state = new QuestStateTracker(guide);
        state.LoadState(
            currentZone: scene,
            activeQuests: Array.Empty<string>(),
            completedQuests: new[] { "FETCHWATER", "SLAYWOLVES" },
            inventoryCounts: new Dictionary<string, int>(),
            keyringItemKeys: Array.Empty<string>());
        var phases = new QuestPhaseTracker(guide, state);
        var frontier = new EffectiveFrontier(guide, phases);
        var positionRegistry = TestPositionResolvers.Create(guide);
        var sourceResolver = new SourceResolver(
            guide,
            phases,
            new UnlockPredicateEvaluator(guide, phases),
            new StubLivePositionProvider(),
            positionRegistry);
        var engine = new Engine<FactKey>();
        var reader = BuildService(
            guide,
            frontier,
            sourceResolver,
            phases,
            zoneRouter: null,
            engine: engine,
            positionRegistry: positionRegistry,
            trackerState: new TrackerState(),
            navSet: new NavigationSet());
        var harness = new InvalidationHarness(scene, guide, phases, engine);
        return (reader, harness);
    }

    internal sealed class InvalidationHarness
    {
        public InvalidationHarness(
            string scene,
            CompiledGuideModel guide,
            QuestPhaseTracker phases,
            Engine<FactKey> engine)
        {
            Scene = scene;
            Guide = guide;
            Phases = phases;
            Engine = engine;
        }

        public string Scene { get; }
        public CompiledGuideModel Guide { get; }
        public QuestPhaseTracker Phases { get; }
        public Engine<FactKey> Engine { get; }

        public void Emit(ChangeSet changeSet) => Engine.InvalidateFacts(changeSet.ChangedFacts);
    }
}
