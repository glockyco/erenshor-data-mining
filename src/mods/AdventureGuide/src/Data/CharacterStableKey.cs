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
}
