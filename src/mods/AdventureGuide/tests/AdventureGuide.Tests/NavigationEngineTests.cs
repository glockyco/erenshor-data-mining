using System.Reflection;
using AdventureGuide.Graph;
using AdventureGuide.Markers;
using AdventureGuide.Navigation;
using AdventureGuide.Position;
using AdventureGuide.Resolution;
using AdventureGuide.State;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class NavigationEngineTests
{
    [Fact]
    public void Track_FallsBackToSelectedTargetPosition_WhenLiveTrackingDisappears()
    {
        var engine = CreateEngine();
        object playerPosition = CreateVector3(0f, 0f, 0f);

        engine.OnSceneChanged("ZoneA");
        InvokeSetTarget(engine, MakeTarget(scene: "ZoneA", x: 10f, isBlockedPath: false));
        SetEffectiveTarget(engine, CreateVector3(99f, 0f, 0f));

        InvokeTrack(engine, playerPosition);

        AssertVector3(engine, "EffectiveTarget", 10f, 0f, 0f);
        Assert.Equal(10f, engine.Distance);
    }

    [Fact]
    public void ComputeNavScore_IgnoresBlockedPathAcrossQuests()
    {
        var blockedSameZone = new SelectedNavTarget
        {
            Target = MakeTarget(scene: "ZoneA", x: 5f, isBlockedPath: true),
            IsSameZone = true,
            IsBlockedPath = true,
        };
        var directCrossZone = new SelectedNavTarget
        {
            Target = MakeTarget(scene: "ZoneB", x: 500f, isBlockedPath: false),
            IsSameZone = false,
            HopCount = 1,
            IsBlockedPath = false,
        };

        float blockedScore = NavigationScore.Compute(blockedSameZone, 0f, 0f, 0f);
        float directScore = NavigationScore.Compute(directCrossZone, 0f, 0f, 0f);

        Assert.True(blockedScore < directScore);
    }

    [Fact]
    public void ComputeNavScore_BlockedPathDoesNotAffectSameZoneDistanceOrdering()
    {
        var blockedNear = new SelectedNavTarget
        {
            Target = MakeTarget(scene: "ZoneA", x: 10f, isBlockedPath: true),
            IsSameZone = true,
            IsBlockedPath = true,
        };
        var directFar = new SelectedNavTarget
        {
            Target = MakeTarget(scene: "ZoneA", x: 100f, isBlockedPath: false),
            IsSameZone = true,
            IsBlockedPath = false,
        };

        float blockedScore = NavigationScore.Compute(blockedNear, 0f, 0f, 0f);
        float directScore = NavigationScore.Compute(directFar, 0f, 0f, 0f);

        Assert.True(blockedScore < directScore);
    }

    private static NavigationEngine CreateEngine()
    {
        var guide = new CompiledGuideBuilder().Build();
        var tracker = new QuestStateTracker(guide);
        var unlocks = new UnlockEvaluator(guide, new GameState(guide), tracker);
        var liveState = new LiveStateTracker(guide, unlocks);
        var router = new ZoneRouter(guide, unlocks);
        var selector = new NavigationTargetSelector(router, guide, liveState);
        return new NavigationEngine(new NavigationSet(), guide, selector, router, liveState, unlocks);
    }

    private static object CreateVector3(float x, float y, float z)
    {
        var trackMethod = typeof(NavigationEngine).GetMethod("Track", BindingFlags.Instance | BindingFlags.NonPublic)!;
        var vectorType = trackMethod.GetParameters()[0].ParameterType;
        return Activator.CreateInstance(vectorType, x, y, z)!;
    }

    private static void AssertVector3(NavigationEngine engine, string propertyName, float x, float y, float z)
    {
        object boxed = typeof(NavigationEngine)
            .GetProperty(propertyName, BindingFlags.Instance | BindingFlags.Public)!
            .GetValue(engine)!;
        var type = boxed.GetType();
        Assert.Equal(x, (float)type.GetField("x")!.GetValue(boxed)!);
        Assert.Equal(y, (float)type.GetField("y")!.GetValue(boxed)!);
        Assert.Equal(z, (float)type.GetField("z")!.GetValue(boxed)!);
    }

    private static void InvokeSetTarget(NavigationEngine engine, ResolvedQuestTarget target)
    {
        typeof(NavigationEngine)
            .GetMethod("SetTarget", BindingFlags.Instance | BindingFlags.NonPublic)!
            .Invoke(engine, new object[] { target });
    }

    private static void InvokeTrack(NavigationEngine engine, object playerPosition)
    {
        typeof(NavigationEngine)
            .GetMethod("Track", BindingFlags.Instance | BindingFlags.NonPublic)!
            .Invoke(engine, new[] { playerPosition });
    }

    private static void SetEffectiveTarget(NavigationEngine engine, object value)
    {
        typeof(NavigationEngine)
            .GetProperty("EffectiveTarget", BindingFlags.Instance | BindingFlags.Public)!
            .GetSetMethod(nonPublic: true)!
            .Invoke(engine, new[] { value });
    }

    private static ResolvedQuestTarget MakeTarget(string scene, float x, bool isBlockedPath)
    {
        var node = new Node
        {
            Key = "node:" + x,
            Type = NodeType.Character,
            DisplayName = "Target",
        };
        var ctx = new ResolvedNodeContext(node.Key, node);
        var semantic = new ResolvedActionSemantic(
            NavigationGoalKind.StartQuest,
            NavigationTargetKind.Character,
            ResolvedActionKind.Talk,
            null,
            null,
            keywordText: null,
            payloadText: null,
            targetIdentityText: node.DisplayName,
            contextText: null,
            rationaleText: null,
            zoneText: null,
            availabilityText: null,
            QuestMarkerKind.Objective,
            markerPriority: 0
        );
        var explanation = new NavigationExplanation(
            NavigationGoalKind.StartQuest,
            NavigationTargetKind.Character,
            ctx,
            ctx,
            node.DisplayName,
            node.DisplayName,
            zoneText: null,
            secondaryText: null,
            tertiaryText: null
        );

        return new ResolvedQuestTarget(
            node.Key,
            scene,
            sourceKey: node.Key,
            ctx,
            ctx,
            semantic,
            explanation,
            x,
            y: 0f,
            z: 0f,
            isActionable: true,
            isBlockedPath: isBlockedPath
        );
    }
}
