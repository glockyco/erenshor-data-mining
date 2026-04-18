using AdventureGuide.Diagnostics;
using AdventureGuide.Graph;
using AdventureGuide.Plan;
using AdventureGuide.Position;
using AdventureGuide.Resolution;
using AdventureGuide.State;
using CompiledGuideModel = AdventureGuide.CompiledGuide.CompiledGuide;

namespace AdventureGuide.Tests.Helpers;

internal static class ResolutionTestFactory
{
    public static QuestTargetProjector BuildProjector(
        CompiledGuideModel guide,
        PositionResolverRegistry? positionRegistry = null,
        ZoneRouter? zoneRouter = null
    )
    {
        var registry = positionRegistry ?? TestPositionResolvers.Create(guide);
        return new QuestTargetProjector(guide, zoneRouter, registry);
    }

    public static QuestResolutionService BuildService(
        CompiledGuideModel guide,
        EffectiveFrontier frontier,
        SourceResolver sourceResolver,
        ZoneRouter? zoneRouter = null,
        GuideDependencyEngine? dependencies = null,
        Func<int>? versionProvider = null,
        PositionResolverRegistry? positionRegistry = null
    )
    {
        var projector = BuildProjector(guide, positionRegistry, zoneRouter);
        return new QuestResolutionService(
            guide,
            frontier,
            sourceResolver,
            zoneRouter,
            projector,
            dependencies,
            versionProvider
        );
    }

    public static NavigationTargetResolver BuildNavigationResolver(
        CompiledGuideModel guide,
        EffectiveFrontier frontier,
        SourceResolver sourceResolver,
        ZoneRouter? zoneRouter = null,
        Func<int>? versionProvider = null,
        DiagnosticsCore? diagnostics = null,
        PositionResolverRegistry? positionRegistry = null,
        GuideDependencyEngine? dependencies = null
    )
    {
        var registry = positionRegistry ?? TestPositionResolvers.Create(guide);
        var projector = BuildProjector(guide, registry, zoneRouter);
        var service = new QuestResolutionService(
            guide,
            frontier,
            sourceResolver,
            zoneRouter,
            projector,
            dependencies,
            versionProvider
        );
        return new NavigationTargetResolver(
            guide,
            service,
            zoneRouter,
            registry,
            projector,
            diagnostics
        );
    }

    public static (QuestResolutionService Service, InvalidationHarness Harness) BuildInvalidationHarness()
    {
        const string scene = "Forest";
        int version = 1;
        var guide = new CompiledGuideBuilder()
            .AddItem("item:water-flask")
            .AddCharacter("char:well", scene: scene, x: 10f, y: 20f, z: 30f)
            .AddItemSource(
                "item:water-flask",
                "char:well",
                edgeType: (byte)EdgeType.GivesItem,
                sourceType: (byte)NodeType.Character
            )
            .AddQuest(
                "quest:fetch-water",
                dbName: "FETCHWATER",
                requiredItems: new[] { ("item:water-flask", 1) }
            )
            .AddItem("item:wolf-pelt")
            .AddCharacter("char:wolf", scene: scene, x: 40f, y: 50f, z: 60f)
            .AddItemSource(
                "item:wolf-pelt",
                "char:wolf",
                edgeType: (byte)EdgeType.DropsItem,
                sourceType: (byte)NodeType.Character
            )
            .AddQuest(
                "quest:slay-wolves",
                dbName: "SLAYWOLVES",
                requiredItems: new[] { ("item:wolf-pelt", 1) }
            )
            .Build();
        var dependencies = new GuideDependencyEngine();
        var phases = new QuestPhaseTracker(guide, dependencies);
        phases.Initialize(
            Array.Empty<string>(),
            new[] { "FETCHWATER", "SLAYWOLVES" },
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        var frontier = new EffectiveFrontier(guide, phases);
        var positionRegistry = TestPositionResolvers.Create(guide);
        var sourceResolver = new SourceResolver(
            guide,
            phases,
            new UnlockPredicateEvaluator(guide, phases),
            new StubLivePositionProvider(),
            positionRegistry
        );
        var service = BuildService(
            guide,
            frontier,
            sourceResolver,
            zoneRouter: null,
            dependencies: dependencies,
            versionProvider: () => version,
            positionRegistry: positionRegistry
        );
        var harness = new InvalidationHarness(
            scene,
            emit: changeSet => service.InvalidateFacts(changeSet.ChangedFacts),
            bumpVersionWithoutFacts: () => version++
        );
        return (service, harness);
    }

    internal sealed class InvalidationHarness
    {
        private readonly Action<GuideChangeSet> _emit;
        private readonly Action _bumpVersionWithoutFacts;

        public InvalidationHarness(
            string scene,
            Action<GuideChangeSet> emit,
            Action bumpVersionWithoutFacts
        )
        {
            Scene = scene;
            _emit = emit;
            _bumpVersionWithoutFacts = bumpVersionWithoutFacts;
        }

        public string Scene { get; }

        public void Emit(GuideChangeSet changeSet) => _emit(changeSet);

        public void BumpVersionWithoutFacts() => _bumpVersionWithoutFacts();
    }
}
