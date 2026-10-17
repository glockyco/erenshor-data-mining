using Newtonsoft.Json;

namespace AdventureGuide.Data;

public sealed class ZoneLineDestinationContext
{
    [JsonProperty("zone_line_stable_key"), JsonRequired]
    public string ZoneLineStableKey { get; set; } = "";

    [JsonProperty("kind"), JsonRequired]
    public string Kind { get; set; } = "";

    [JsonProperty("destination_state_key"), JsonRequired]
    public string DestinationStateKey { get; set; } = "";

    [JsonProperty("landing_state_key"), JsonRequired]
    public string LandingStateKey { get; set; } = "";

    [JsonProperty("source_key"), JsonRequired]
    public string SourceKey { get; set; } = "";
}

internal sealed partial class GuideWrapper
{
    [JsonProperty("_zone_line_destination_contexts"), JsonRequired]
    public Dictionary<string, ZoneLineDestinationContext>? ZoneLineDestinationContexts { get; set; }
}

public sealed partial class GuideData
{
    public IReadOnlyDictionary<string, ZoneLineDestinationContext> ZoneLineDestinationContexts
    {
        get;
        private set;
    } = new Dictionary<string, ZoneLineDestinationContext>();

    private void LoadDestinationContexts(GuideWrapper wrapper)
    {
        ZoneLineDestinationContexts =
            wrapper.ZoneLineDestinationContexts
            ?? new Dictionary<string, ZoneLineDestinationContext>();
    }

    private static void ValidateDestinationContexts(GuideWrapper wrapper)
    {
        if (wrapper.ZoneLineDestinationContexts == null)
            return;
        var lines = new Dictionary<string, ZoneLineEntry>(StringComparer.Ordinal);
        if (wrapper.ZoneLines != null)
            foreach (var line in wrapper.ZoneLines)
                if (
                    !string.IsNullOrWhiteSpace(line.StableKey)
                    && !lines.TryAdd(line.StableKey, line)
                )
                    throw new InvalidDataException(
                        $"Duplicate zone line stable key: {line.StableKey}"
                    );
        foreach (var (key, context) in wrapper.ZoneLineDestinationContexts)
        {
            if (
                context == null
                || string.IsNullOrWhiteSpace(key)
                || !string.Equals(key, context.ZoneLineStableKey, StringComparison.Ordinal)
                || !lines.TryGetValue(key, out var line)
            )
                throw new InvalidDataException(
                    $"Unknown or malformed destination context line: {key}"
                );
            if (
                context.Kind != "stored_return"
                || context.DestinationStateKey != EncounterStateKeys.ReturnZone
                || context.LandingStateKey != EncounterStateKeys.ReturnLanding
                || string.IsNullOrWhiteSpace(context.SourceKey)
                || wrapper.ZoneLookup == null
                || !wrapper.ZoneLookup.Keys.Any(scene =>
                    string.Equals(scene, line.Scene, StringComparison.OrdinalIgnoreCase)
                )
            )
                throw new InvalidDataException($"Unsupported destination context binding: {key}");
        }
    }
}
