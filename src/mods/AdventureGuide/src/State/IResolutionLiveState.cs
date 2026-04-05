using AdventureGuide.Graph;

namespace AdventureGuide.State;

/// <summary>
/// Minimal live-world surface required by the resolution layer.
///
/// This interface stays free of Unity types so resolution logic can be tested
/// without loading Assembly-CSharp or UnityEngine runtime assemblies.
/// </summary>
public interface IResolutionLiveState
{
    bool CorpseContainsItem(Node spawnNode, string itemStableKey);
    IEnumerable<LiveChestPosition> GetRotChestPositionsWithItem(string itemStableKey);
}

public readonly struct LiveChestPosition
{
    public readonly float X;
    public readonly float Y;
    public readonly float Z;
    public readonly string Scene;

    public LiveChestPosition(float x, float y, float z, string scene)
    {
        X = x;
        Y = y;
        Z = z;
        Scene = scene ?? string.Empty;
    }
}
