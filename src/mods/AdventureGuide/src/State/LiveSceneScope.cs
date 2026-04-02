using AdventureGuide.Graph;

namespace AdventureGuide.State;

internal static class LiveSceneScope
{
    internal static bool CanUseLiveSceneState(string? nodeScene, string currentScene) =>
        !string.IsNullOrEmpty(nodeScene)
        && string.Equals(nodeScene, currentScene, StringComparison.OrdinalIgnoreCase);

    internal static bool CharacterHasCurrentScenePresence(
        EntityGraph graph,
        Node characterNode,
        string currentScene)
    {
        if (CanUseLiveSceneState(characterNode.Scene, currentScene))
            return true;

        var spawnEdges = graph.OutEdges(characterNode.Key, EdgeType.HasSpawn);
        for (int i = 0; i < spawnEdges.Count; i++)
        {
            var spawnNode = graph.GetNode(spawnEdges[i].Target);
            if (spawnNode != null && CanUseLiveSceneState(spawnNode.Scene, currentScene))
                return true;
        }

        return false;
    }

    internal static string ResolveSpawnLookupName(Node spawnNode, Node? parentCharacter)
    {
        if (!string.IsNullOrWhiteSpace(parentCharacter?.DisplayName))
            return parentCharacter.DisplayName;

        return spawnNode.DisplayName;
    }
}
