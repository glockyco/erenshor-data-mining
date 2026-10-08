namespace AdventureGuide.Data;

internal static class CharacterStableKey
{
    /// <summary>
    /// Collapse export variant keys such as character:foo:1 onto the runtime
    /// prefab identity character:foo. Keys without a numeric variant suffix
    /// pass through unchanged.
    /// </summary>
    public static string Normalize(string key)
    {
        int lastColon = key.LastIndexOf(':');
        if (lastColon <= 0)
            return key;

        var suffix = key.AsSpan(lastColon + 1);
        if (suffix.Length == 0)
            return key;
        foreach (char character in suffix)
        {
            if (character is < '0' or > '9')
                return key;
        }

        var baseKey = key.Substring(0, lastColon);
        return baseKey.IndexOf(':') >= 0 ? baseKey : key;
    }

    /// <summary>
    /// Stable key for a character prefab or scene object name, in the export
    /// pipeline's character:{name} format: trimmed and lowercased.
    /// </summary>
    public static string FromObjectName(string objectName) =>
        "character:" + objectName.Trim().ToLowerInvariant();

    /// <summary>
    /// Parse the key of a character placed in a scene,
    /// character:{object}:{scene}:{x}:{y}:{z} with an optional variant suffix.
    /// NPC.Start renames such objects to NPCName, so the object name identifies
    /// them where the display name may not ("Catnip (1)" is shown as "Catnip
    /// (Enemy)" but named "Catnip"). Variant scenes copy objects to the same
    /// position (Shivering Step's Kio stands where Stowaway's does), so the
    /// scene is part of the identity. Prefab keys, character:{object}, do not
    /// parse.
    /// </summary>
    public static bool TryParsePlaced(string key, out PlacedCharacterKey placed)
    {
        placed = default;
        const string prefix = "character:";
        var normalized = Normalize(key);
        if (!normalized.StartsWith(prefix, StringComparison.Ordinal))
            return false;

        // From the end: z, y, x (written with two decimals), then the scene.
        Span<float> coordinates = stackalloc float[3];
        int end = normalized.Length;
        for (int segment = 0; segment < 3; segment++)
        {
            int colon = normalized.LastIndexOf(':', end - 1);
            if (
                colon < prefix.Length
                || !TryCoordinate(
                    normalized.AsSpan(colon + 1, end - colon - 1),
                    out coordinates[2 - segment]
                )
            )
                return false;
            end = colon;
        }
        int sceneStart = normalized.LastIndexOf(':', end - 1);
        if (sceneStart <= prefix.Length || sceneStart + 1 == end)
            return false;
        placed = new PlacedCharacterKey(
            normalized.Substring(prefix.Length, sceneStart - prefix.Length),
            normalized.Substring(sceneStart + 1, end - sceneStart - 1),
            coordinates[0],
            coordinates[1],
            coordinates[2]
        );
        return true;
    }

    private static bool TryCoordinate(ReadOnlySpan<char> value, out float coordinate)
    {
        coordinate = 0f;
        return value.IndexOf('.') >= 0
            && float.TryParse(
                value,
                System.Globalization.NumberStyles.Float,
                System.Globalization.CultureInfo.InvariantCulture,
                out coordinate
            );
    }
}

/// <summary>The parts of a scene-placed character's exported key.</summary>
internal readonly struct PlacedCharacterKey
{
    public PlacedCharacterKey(string objectName, string scene, float x, float y, float z)
    {
        ObjectName = objectName;
        Scene = scene;
        X = x;
        Y = y;
        Z = z;
    }

    /// <summary>The scene object's name, lowercased like the key.</summary>
    public string ObjectName { get; }

    /// <summary>The scene name, lowercased like the key.</summary>
    public string Scene { get; }

    public float X { get; }
    public float Y { get; }
    public float Z { get; }
}
