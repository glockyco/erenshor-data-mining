using AdventureGuide.Diagnostics;
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
}
