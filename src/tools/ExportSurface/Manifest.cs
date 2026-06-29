using System.Text.Json;
using System.Text.Json.Serialization;

namespace ExportSurface;

internal sealed record FieldEntry(
    [property: JsonPropertyName("type")] string Type,
    [property: JsonPropertyName("status")] string Status,
    [property: JsonPropertyName("by")] string? By,
    [property: JsonPropertyName("reason")] string? Reason);

internal sealed record Manifest(
    [property: JsonPropertyName("tracks_build")] string TracksBuild,
    [property: JsonPropertyName("types")] List<string> Types,
    [property: JsonPropertyName("fields")] Dictionary<string, Dictionary<string, FieldEntry>> Fields)
{
    public static Manifest Load(string path) =>
        JsonSerializer.Deserialize<Manifest>(File.ReadAllText(path))
        ?? throw new InvalidDataException($"empty manifest: {path}");
}
