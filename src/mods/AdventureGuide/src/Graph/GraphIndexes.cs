using AdventureGuide.Markers;

namespace AdventureGuide.Graph;

/// <summary>
/// Immutable structural indexes derived from <see cref="EntityGraph"/>.
///
/// Built once at startup and used to map runtime deltas to affected quests and
/// to materialize scene-local marker blueprints without re-walking the full
/// graph on every change.
/// </summary>
public sealed class GraphIndexes
{
    private static readonly IReadOnlyCollection<string> EmptyKeySet = Array.Empty<string>();
    private static readonly IReadOnlyList<QuestGiverBlueprint> EmptyGiverBlueprints = Array.Empty<QuestGiverBlueprint>();
    private static readonly IReadOnlyList<QuestCompletionBlueprint> EmptyCompletionBlueprints = Array.Empty<QuestCompletionBlueprint>();
    private static readonly IReadOnlyList<StaticSourceBlueprint> EmptyStaticBlueprints = Array.Empty<StaticSourceBlueprint>();

    private readonly Dictionary<string, IReadOnlyCollection<string>> _questsByItemKey;
    private readonly Dictionary<string, IReadOnlyCollection<string>> _questsByQuestKey;
    private readonly Dictionary<string, IReadOnlyList<QuestGiverBlueprint>> _questGiversByScene;
    private readonly Dictionary<string, IReadOnlyList<QuestCompletionBlueprint>> _questCompletionsByScene;
    private readonly Dictionary<string, IReadOnlyList<StaticSourceBlueprint>> _staticSourcesByScene;
    private readonly Dictionary<string, IReadOnlyCollection<string>> _scenesByQuestKey;

    public GraphIndexes(EntityGraph graph)
    {
        if (graph == null)
            throw new ArgumentNullException(nameof(graph));

        _questsByItemKey = BuildQuestItemDependencies(graph);
        _questsByQuestKey = BuildQuestQuestDependencies(graph);
        _questGiversByScene = BuildQuestGiverBlueprints(graph);
        _questCompletionsByScene = BuildQuestCompletionBlueprints(graph);
        _staticSourcesByScene = BuildStaticSourceBlueprints(graph);
        _scenesByQuestKey = BuildQuestScenes(graph, _questGiversByScene, _questCompletionsByScene);
    }

    public IReadOnlyCollection<string> GetQuestsDependingOnItem(string itemKey) =>
        _questsByItemKey.TryGetValue(itemKey, out var quests) ? quests : EmptyKeySet;

    public IReadOnlyCollection<string> GetQuestsDependingOnQuest(string questKey) =>
        _questsByQuestKey.TryGetValue(questKey, out var quests) ? quests : EmptyKeySet;

    public IReadOnlyList<QuestGiverBlueprint> GetQuestGiversInScene(string scene) =>
        _questGiversByScene.TryGetValue(scene, out var blueprints) ? blueprints : EmptyGiverBlueprints;

    public IReadOnlyList<QuestCompletionBlueprint> GetQuestCompletionsInScene(string scene) =>
        _questCompletionsByScene.TryGetValue(scene, out var blueprints) ? blueprints : EmptyCompletionBlueprints;

    public IReadOnlyList<StaticSourceBlueprint> GetStaticSourcesInScene(string scene) =>
        _staticSourcesByScene.TryGetValue(scene, out var blueprints) ? blueprints : EmptyStaticBlueprints;

    public IReadOnlyCollection<string> GetScenesTouchedByQuest(string questKey) =>
        _scenesByQuestKey.TryGetValue(questKey, out var scenes) ? scenes : EmptyKeySet;

    private static Dictionary<string, IReadOnlyCollection<string>> BuildQuestItemDependencies(EntityGraph graph)
    {
        var map = new Dictionary<string, HashSet<string>>(StringComparer.Ordinal);

        foreach (var quest in graph.NodesOfType(NodeType.Quest))
        {
            AddQuestItemDependencies(graph, quest.Key, EdgeType.RequiresItem, map);
            AddQuestItemDependencies(graph, quest.Key, EdgeType.RequiresMaterial, map);
        }

        return FreezeSetMap(map);
    }

    private static void AddQuestItemDependencies(
        EntityGraph graph,
        string questKey,
        EdgeType edgeType,
        Dictionary<string, HashSet<string>> map)
    {
        var edges = graph.OutEdges(questKey, edgeType);
        for (int i = 0; i < edges.Count; i++)
        {
            var itemKey = edges[i].Target;
            if (!map.TryGetValue(itemKey, out var quests))
            {
                quests = new HashSet<string>(StringComparer.Ordinal);
                map[itemKey] = quests;
            }

            quests.Add(questKey);
        }
    }

    private static Dictionary<string, IReadOnlyCollection<string>> BuildQuestQuestDependencies(EntityGraph graph)
    {
        var map = new Dictionary<string, HashSet<string>>(StringComparer.Ordinal);

        foreach (var quest in graph.NodesOfType(NodeType.Quest))
        {
            var edges = graph.OutEdges(quest.Key, EdgeType.RequiresQuest);
            for (int i = 0; i < edges.Count; i++)
            {
                var prerequisiteQuestKey = edges[i].Target;
                if (!map.TryGetValue(prerequisiteQuestKey, out var dependents))
                {
                    dependents = new HashSet<string>(StringComparer.Ordinal);
                    map[prerequisiteQuestKey] = dependents;
                }

                dependents.Add(quest.Key);
            }
        }

        return FreezeSetMap(map);
    }

    private static Dictionary<string, IReadOnlyList<QuestGiverBlueprint>> BuildQuestGiverBlueprints(EntityGraph graph)
    {
        var byScene = new Dictionary<string, List<QuestGiverBlueprint>>(StringComparer.OrdinalIgnoreCase);

        foreach (var quest in graph.NodesOfType(NodeType.Quest))
        {
            if (quest.DbName == null)
                continue;

            var prerequisiteQuestDbNames = CollectRequiredQuestDbNames(graph, quest.Key);
            var edges = graph.OutEdges(quest.Key, EdgeType.AssignedBy);
            for (int i = 0; i < edges.Count; i++)
            {
                var edge = edges[i];
                var characterNode = graph.GetNode(edge.Target);
                if (characterNode == null)
                    continue;

                foreach (var sceneTarget in EnumerateSceneTargets(graph, characterNode))
                {
                    AddToSceneMap(byScene, sceneTarget.Scene, new QuestGiverBlueprint(
                        quest.Key,
                        quest.DbName,
                        quest.DisplayName,
                        characterNode.Key,
                        sceneTarget.PositionNodeKey,
                        sceneTarget.Scene,
                        BuildInteraction(edge),
                        quest.Repeatable,
                        prerequisiteQuestDbNames));
                }
            }
        }

        return FreezeListMap(byScene);
    }

    private static Dictionary<string, IReadOnlyList<QuestCompletionBlueprint>> BuildQuestCompletionBlueprints(EntityGraph graph)
    {
        var byScene = new Dictionary<string, List<QuestCompletionBlueprint>>(StringComparer.OrdinalIgnoreCase);

        foreach (var quest in graph.NodesOfType(NodeType.Quest))
        {
            if (quest.DbName == null)
                continue;

            var edges = graph.OutEdges(quest.Key, EdgeType.CompletedBy);
            for (int i = 0; i < edges.Count; i++)
            {
                var edge = edges[i];
                var targetNode = graph.GetNode(edge.Target);
                if (targetNode == null)
                    continue;

                foreach (var sceneTarget in EnumerateSceneTargets(graph, targetNode))
                {
                    AddToSceneMap(byScene, sceneTarget.Scene, new QuestCompletionBlueprint(
                        quest.Key,
                        quest.DbName,
                        quest.DisplayName,
                        targetNode.Key,
                        sceneTarget.PositionNodeKey,
                        sceneTarget.Scene,
                        BuildInteraction(edge),
                        quest.Repeatable));
                }
            }
        }

        return FreezeListMap(byScene);
    }

    private static Dictionary<string, IReadOnlyList<StaticSourceBlueprint>> BuildStaticSourceBlueprints(EntityGraph graph)
    {
        var byScene = new Dictionary<string, List<StaticSourceBlueprint>>(StringComparer.OrdinalIgnoreCase);

        foreach (var node in graph.AllNodes)
        {
            if (string.IsNullOrEmpty(node.Scene) || !HasStaticMarkerPosition(node))
                continue;

            if (node.Type is not (NodeType.MiningNode or NodeType.Water or NodeType.Forge or NodeType.ItemBag or NodeType.ZoneLine or NodeType.WorldObject))
                continue;

            AddToSceneMap(byScene, node.Scene, new StaticSourceBlueprint(node.Key, node.Scene, node.Type));
        }

        return FreezeListMap(byScene);
    }

    private static Dictionary<string, IReadOnlyCollection<string>> BuildQuestScenes(
        EntityGraph graph,
        Dictionary<string, IReadOnlyList<QuestGiverBlueprint>> giversByScene,
        Dictionary<string, IReadOnlyList<QuestCompletionBlueprint>> completionsByScene)
    {
        var map = new Dictionary<string, HashSet<string>>(StringComparer.Ordinal);

        foreach (var quest in graph.NodesOfType(NodeType.Quest))
        {
            var scenes = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            if (!string.IsNullOrEmpty(quest.Scene))
                scenes.Add(quest.Scene);

            CollectQuestScenesFromEdges(graph, quest.Key, EdgeType.AssignedBy, scenes);
            CollectQuestScenesFromEdges(graph, quest.Key, EdgeType.CompletedBy, scenes);
            CollectQuestScenesFromEdges(graph, quest.Key, EdgeType.StepTalk, scenes);
            CollectQuestScenesFromEdges(graph, quest.Key, EdgeType.StepKill, scenes);
            CollectQuestScenesFromEdges(graph, quest.Key, EdgeType.StepTravel, scenes);
            CollectQuestScenesFromEdges(graph, quest.Key, EdgeType.StepShout, scenes);
            CollectQuestScenesFromEdges(graph, quest.Key, EdgeType.StepRead, scenes);

            foreach (var pair in giversByScene)
            {
                for (int i = 0; i < pair.Value.Count; i++)
                {
                    if (pair.Value[i].QuestKey == quest.Key)
                        scenes.Add(pair.Key);
                }
            }

            foreach (var pair in completionsByScene)
            {
                for (int i = 0; i < pair.Value.Count; i++)
                {
                    if (pair.Value[i].QuestKey == quest.Key)
                        scenes.Add(pair.Key);
                }
            }

            if (scenes.Count > 0)
                map[quest.Key] = new HashSet<string>(scenes, StringComparer.OrdinalIgnoreCase);
        }

        return FreezeSetMap(map);
    }

    private static void CollectQuestScenesFromEdges(EntityGraph graph, string questKey, EdgeType edgeType, HashSet<string> scenes)
    {
        var edges = graph.OutEdges(questKey, edgeType);
        for (int i = 0; i < edges.Count; i++)
        {
            var targetNode = graph.GetNode(edges[i].Target);
            if (targetNode == null)
                continue;

            foreach (var sceneTarget in EnumerateSceneTargets(graph, targetNode))
                scenes.Add(sceneTarget.Scene);
        }
    }

    private static IReadOnlyList<string> CollectRequiredQuestDbNames(EntityGraph graph, string questKey)
    {
        var required = new List<string>();
        var edges = graph.OutEdges(questKey, EdgeType.RequiresQuest);
        for (int i = 0; i < edges.Count; i++)
        {
            var prerequisite = graph.GetNode(edges[i].Target);
            if (!string.IsNullOrEmpty(prerequisite?.DbName))
                required.Add(prerequisite.DbName);
        }

        return required;
    }

    private static IEnumerable<SceneTarget> EnumerateSceneTargets(EntityGraph graph, Node node)
    {
        if (!string.IsNullOrEmpty(node.Scene))
            yield return new SceneTarget(node.Key, node.Scene!);

        if (node.Type != NodeType.Character)
            yield break;

        var spawnEdges = graph.OutEdges(node.Key, EdgeType.HasSpawn);
        for (int i = 0; i < spawnEdges.Count; i++)
        {
            var spawnNode = graph.GetNode(spawnEdges[i].Target);
            if (!string.IsNullOrEmpty(spawnNode?.Scene))
                yield return new SceneTarget(spawnNode.Key, spawnNode.Scene!);
        }
    }

    private static MarkerInteraction BuildInteraction(Edge edge)
    {
        if (!string.IsNullOrEmpty(edge.Keyword))
            return new MarkerInteraction(MarkerInteractionKind.SayKeyword, edge.Keyword);

        return new MarkerInteraction(MarkerInteractionKind.TalkTo, null);
    }

    private static bool HasStaticMarkerPosition(Node node) =>
        node.X.HasValue && node.Y.HasValue && node.Z.HasValue;

    private static void AddToSceneMap<T>(Dictionary<string, List<T>> map, string scene, T value)
    {
        if (!map.TryGetValue(scene, out var list))
        {
            list = new List<T>();
            map[scene] = list;
        }

        list.Add(value);
    }

    private static Dictionary<string, IReadOnlyCollection<string>> FreezeSetMap(Dictionary<string, HashSet<string>> source)
    {
        var frozen = new Dictionary<string, IReadOnlyCollection<string>>(source.Count, source.Comparer);
        foreach (var (key, values) in source)
            frozen[key] = values.ToArray();
        return frozen;
    }

    private static Dictionary<string, IReadOnlyList<T>> FreezeListMap<T>(Dictionary<string, List<T>> source)
    {
        var frozen = new Dictionary<string, IReadOnlyList<T>>(source.Count, source.Comparer);
        foreach (var (key, values) in source)
            frozen[key] = values;
        return frozen;
    }

    private readonly struct SceneTarget
    {
        public readonly string PositionNodeKey;
        public readonly string Scene;

        public SceneTarget(string positionNodeKey, string scene)
        {
            PositionNodeKey = positionNodeKey;
            Scene = scene;
        }
    }
}
