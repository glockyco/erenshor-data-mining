using AdventureGuide.CompiledGuide;
using AdventureGuide.Plan;

namespace AdventureGuide.Resolution;

public readonly struct ResolvedTarget
{
    public ResolvedTarget(int nodeId, float x, float y, float z, string? scene, int questIndex)
    {
        NodeId = nodeId;
        X = x;
        Y = y;
        Z = z;
        Scene = scene;
        QuestIndex = questIndex;
    }

    public int NodeId { get; }
    public float X { get; }
    public float Y { get; }
    public float Z { get; }
    public string? Scene { get; }
    public int QuestIndex { get; }
}

public sealed class SourceResolver
{
    private readonly CompiledGuide.CompiledGuide _guide;
    private readonly QuestPhaseTracker _phases;
    private readonly UnlockPredicateEvaluator _unlocks;
    private readonly ILivePositionProvider _livePositions;

    public SourceResolver(
        CompiledGuide.CompiledGuide guide,
        QuestPhaseTracker phases,
        UnlockPredicateEvaluator unlocks,
        ILivePositionProvider livePositions)
    {
        _guide = guide;
        _phases = phases;
        _unlocks = unlocks;
        _livePositions = livePositions;
    }

    public IReadOnlyList<ResolvedTarget> ResolveTargets(FrontierEntry entry, string currentScene)
    {
        var results = new List<ResolvedTarget>();

        switch (entry.Phase)
        {
            case QuestPhase.ReadyToAccept:
                foreach (int giverId in _guide.GiverIds(entry.QuestIndex))
                {
                    EmitNodePosition(giverId, entry.QuestIndex, results);
                }
                break;

            case QuestPhase.Accepted:
                bool emittedItemSource = false;
                foreach (var requirement in _guide.RequiredItems(entry.QuestIndex))
                {
                    int itemIndex = FindItemIndex(requirement.ItemId);
                    int count = itemIndex >= 0 ? _phases.GetItemCount(itemIndex) : 0;
                    if (count >= requirement.Quantity || itemIndex < 0)
                    {
                        continue;
                    }

                    emittedItemSource = true;
                    foreach (var source in _guide.GetItemSources(itemIndex))
                    {
                        if (_unlocks.Evaluate(source.SourceId) == UnlockResult.Blocked)
                        {
                            continue;
                        }

                        if (source.Positions.Length == 0)
                        {
                            EmitNodePosition(source.SourceId, entry.QuestIndex, results);
                            continue;
                        }

                        foreach (var position in source.Positions)
                        {
                            WorldPosition? live = _livePositions.GetLivePosition(position.SpawnId);
                            results.Add(new ResolvedTarget(
                                source.SourceId,
                                live?.X ?? position.X,
                                live?.Y ?? position.Y,
                                live?.Z ?? position.Z,
                                source.Scene,
                                entry.QuestIndex));
                        }
                    }
                }

                if (!emittedItemSource)
                {
                    foreach (int completerId in _guide.CompleterIds(entry.QuestIndex))
                    {
                        EmitNodePosition(completerId, entry.QuestIndex, results);
                    }
                }
                break;
        }

        _ = currentScene;
        return results;
    }

    private void EmitNodePosition(int nodeId, int questIndex, List<ResolvedTarget> results)
    {
        if (_unlocks.Evaluate(nodeId) == UnlockResult.Blocked)
        {
            return;
        }

        var node = _guide.GetNode(nodeId);
        results.Add(new ResolvedTarget(nodeId, node.X, node.Y, node.Z, _guide.GetScene(nodeId), questIndex));
    }

    private int FindItemIndex(int itemNodeId)
    {
        for (int itemIndex = 0; itemIndex < _guide.ItemCount; itemIndex++)
        {
            if (_guide.ItemNodeId(itemIndex) == itemNodeId)
            {
                return itemIndex;
            }
        }

        return -1;
    }
}
