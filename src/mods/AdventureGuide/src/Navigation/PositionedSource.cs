using System.Globalization;

namespace AdventureGuide.Navigation;

/// <summary>The guide's scene-local mining, water, pickup and planning-table key contract.</summary>
public readonly struct PositionedSource
{
    public string Kind { get; }
    public string Scene { get; }
    public float X { get; }
    public float Y { get; }
    public float Z { get; }

    /// <summary>
    /// A water key names the center of a water volume, not a fishing spot:
    /// Salted Strand's volume spans 16 km and is centered off the map. The
    /// player fishes anywhere along the zone's water, so the source has a
    /// zone but no destination. Mining nodes and ground pickups are objects
    /// at their position.
    /// </summary>
    public bool IsZoneWide => Kind == "water";

    private PositionedSource(string kind, string scene, float x, float y, float z)
    {
        Kind = kind;
        Scene = scene;
        X = x;
        Y = y;
        Z = z;
    }

    public static bool TryParse(string? key, out PositionedSource source)
    {
        source = default;
        if (key == null)
            return false;
        int kindEnd = key.IndexOf(':');
        if (kindEnd < 0)
            return false;
        var kind = key.AsSpan(0, kindEnd);
        if (
            !kind.SequenceEqual("mining".AsSpan())
            && !kind.SequenceEqual("water".AsSpan())
            && !kind.SequenceEqual("itembag".AsSpan())
            && !kind.SequenceEqual("planningtable".AsSpan())
        )
            return false;
        int sceneEnd = key.IndexOf(':', kindEnd + 1);
        if (sceneEnd <= kindEnd + 1)
            return false;
        int xEnd = key.IndexOf(':', sceneEnd + 1);
        int yEnd = xEnd < 0 ? -1 : key.IndexOf(':', xEnd + 1);
        if (xEnd < 0 || yEnd < 0)
            return false;
        if (
            !TryCoordinate(key.AsSpan(sceneEnd + 1, xEnd - sceneEnd - 1), out float x)
            || !TryCoordinate(key.AsSpan(xEnd + 1, yEnd - xEnd - 1), out float y)
            || !TryCoordinate(key.AsSpan(yEnd + 1), out float z)
        )
            return false;
        source = new PositionedSource(
            kind.ToString(),
            key.Substring(kindEnd + 1, sceneEnd - kindEnd - 1),
            x,
            y,
            z
        );
        return true;
    }

    private static bool TryCoordinate(ReadOnlySpan<char> value, out float result) =>
        float.TryParse(value, NumberStyles.Float, CultureInfo.InvariantCulture, out result)
        && !float.IsNaN(result)
        && !float.IsInfinity(result);
}
