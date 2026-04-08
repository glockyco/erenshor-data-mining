namespace AdventureGuide.Resolution;

public readonly struct WorldPosition
{
    public WorldPosition(float x, float y, float z)
    {
        X = x;
        Y = y;
        Z = z;
    }

    public float X { get; }
    public float Y { get; }
    public float Z { get; }
}

/// <summary>
/// Testable abstraction over live scene position lookup.
///
/// The runtime adapter can read Unity objects behind this interface while the
/// pure resolver tests use simple stubs and never touch Unity types.
/// </summary>
public interface ILivePositionProvider
{
    WorldPosition? GetLivePosition(int spawnNodeId);

    bool IsAlive(int spawnNodeId);
}
