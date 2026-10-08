namespace AdventureGuide.State;

internal enum TreasureHuntChange
{
    None,
    Started,
    Updated,
    Ended,
}

/// <summary>The live hunt has a destination before it has a known dig position.</summary>
internal sealed class TreasureHuntState
{
    public const string SourceId = "treasure:dig-site";
    public const string DisplayName = "Treasure dig site";
    public string Scene { get; private set; } = "";
    public float X { get; private set; }
    public float Y { get; private set; }
    public float Z { get; private set; }
    public bool Active => Scene.Length != 0;
    public bool HasLocation => Active && (X != 0 || Y != 0 || Z != 0);

    public TreasureHuntChange Observe(string? scene, float x, float y, float z)
    {
        scene ??= "";
        if (scene.Length == 0)
            x = y = z = 0;
        if (scene == Scene && x == X && y == Y && z == Z)
            return TreasureHuntChange.None;
        bool wasActive = Active;
        bool newHunt = scene.Length != 0 && scene != Scene;
        Scene = scene;
        X = x;
        Y = y;
        Z = z;
        return !Active ? TreasureHuntChange.Ended
            : !wasActive || newHunt ? TreasureHuntChange.Started
            : TreasureHuntChange.Updated;
    }
}
