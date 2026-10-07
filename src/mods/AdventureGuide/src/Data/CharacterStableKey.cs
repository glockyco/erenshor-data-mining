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
    /// The scene object name in the key of a character placed in a scene,
    /// character:{object}:{scene}:{x}:{y}:{z} with an optional variant
    /// suffix. NPC.Start renames such objects to NPCName, so the object name
    /// identifies them where the display name may not ("Catnip (1)" is shown
    /// as "Catnip (Enemy)" but named "Catnip").
    /// </summary>
    public static bool TryGetPlacedObjectName(string key, out string objectName)
    {
        objectName = "";
        const string prefix = "character:";
        var normalized = Normalize(key);
        if (!normalized.StartsWith(prefix, StringComparison.Ordinal))
            return false;

        int end = normalized.Length;
        for (int segment = 0; segment < 4; segment++)
        {
            int colon = normalized.LastIndexOf(':', end - 1);
            if (colon < prefix.Length)
                return false;
            // The three coordinates are written with two decimals.
            if (segment < 3 && !IsCoordinate(normalized.AsSpan(colon + 1, end - colon - 1)))
                return false;
            end = colon;
        }
        if (end == prefix.Length)
            return false;
        objectName = normalized.Substring(prefix.Length, end - prefix.Length);
        return true;
    }

    private static bool IsCoordinate(ReadOnlySpan<char> value) =>
        value.IndexOf('.') >= 0
        && float.TryParse(
            value,
            System.Globalization.NumberStyles.Float,
            System.Globalization.CultureInfo.InvariantCulture,
            out _
        );
}
