namespace AdventureGuide.Navigation;

internal static class SharedSpawnMarkerPolicy
{
    internal static int? AbsencePointId(MarkerType type, int? spawnPointId) =>
        type == MarkerType.DeadSpawn || type == MarkerType.NightSpawn ? spawnPointId : null;
}

internal sealed class SharedSpawnMarkerNames
{
    private readonly Dictionary<string, string> _names = new(
        System.StringComparer.OrdinalIgnoreCase
    );

    internal SharedSpawnMarkerNames(string characterKey, string displayName) =>
        Add(characterKey, displayName);

    internal void Add(string characterKey, string displayName)
    {
        if (!_names.ContainsKey(characterKey))
            _names.Add(characterKey, displayName);
    }

    internal string DisplayName => string.Join(" / ", _names.Values);
}
