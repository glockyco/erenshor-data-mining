using AdventureGuide.Graph;
using AdventureGuide.Plan;
using AdventureGuide.Resolution;
using AdventureGuide.State;
using AdventureGuide.UI.Tree;
using CompiledGuideModel = AdventureGuide.CompiledGuide.CompiledGuide;

namespace AdventureGuide.Tests.Helpers;

internal sealed class SpecTreeProjectorHarness
{
    private SpecTreeProjectorHarness(
        CompiledGuideModel guide,
        QuestStateTracker tracker,
        QuestPhaseTracker phases,
        EffectiveFrontier frontier,
        SourceResolver sourceResolver,
        QuestResolutionService resolutionService,
        SpecTreeProjector projector
    )
    {
        Guide = guide;
        Tracker = tracker;
        Phases = phases;
        Frontier = frontier;
        SourceResolver = sourceResolver;
        ResolutionService = resolutionService;
        Projector = projector;
    }

    public CompiledGuideModel Guide { get; }
    public QuestStateTracker Tracker { get; }
    public QuestPhaseTracker Phases { get; }
    public EffectiveFrontier Frontier { get; }
    public SourceResolver SourceResolver { get; }
    public QuestResolutionService ResolutionService { get; }
    public SpecTreeProjector Projector { get; }

    public static SpecTreeProjectorHarness Build()
    {
        const string scene = "SceneA";
        var guide = new CompiledGuideBuilder()
            .AddQuest("quest:fetch-water", dbName: "FetchWater")
            .AddCharacter("char:well", scene: scene, x: 10f, y: 20f, z: 30f)
            .AddItem("item:water-flask")
            .AddItemSource(
                "item:water-flask",
                "char:well",
                edgeType: (byte)EdgeType.GivesItem,
                sourceType: (byte)NodeType.Character
            )
            .AddQuest(
                "quest:root",
                dbName: "RootQuest",
                prereqs: new[] { "quest:fetch-water" },
                requiredItems: new[] { ("item:water-flask", 1) }
            )
            .Build();

        var dependencies = new GuideDependencyEngine();
        var tracker = new QuestStateTracker(guide, dependencies);
        tracker.LoadState(
            currentZone: scene,
            activeQuests: Array.Empty<string>(),
            completedQuests: Array.Empty<string>(),
            inventoryCounts: new Dictionary<string, int>(StringComparer.Ordinal),
            keyringItemKeys: Array.Empty<string>()
        );
        var phases = new QuestPhaseTracker(guide, tracker);
        var frontier = new EffectiveFrontier(guide, phases);
        var sourceResolver = new SourceResolver(
            guide,
            phases,
            new UnlockPredicateEvaluator(guide, phases),
            new StubLivePositionProvider(),
            TestPositionResolvers.Create(guide)
        );
        var resolutionService = ResolutionTestFactory.BuildService(
            guide,
            frontier,
            sourceResolver,
            zoneRouter: null,
            dependencies: dependencies,
            versionProvider: () => phases.Version,
            positionRegistry: TestPositionResolvers.Create(guide)
        );
        var projector = new SpecTreeProjector(
            guide,
            resolutionService,
            currentSceneProvider: () => scene
        );

        return new SpecTreeProjectorHarness(
            guide,
            tracker,
            phases,
            frontier,
            sourceResolver,
            resolutionService,
            projector
        );
    }

    public int QuestIndex(string dbName)
    {
        var quest = Guide.GetQuestByDbName(dbName) ?? throw new InvalidOperationException(dbName);
        if (!Guide.TryGetNodeId(quest.Key, out int questNodeId))
            throw new InvalidOperationException(quest.Key);

        return Guide.FindQuestIndex(questNodeId);
    }
}
