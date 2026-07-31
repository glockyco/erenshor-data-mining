using System.Text.Json;
using System.Text.Json.Serialization;

namespace CodeFacts;

internal sealed record FactSpec(
    [property: JsonPropertyName("id")] string Id,
    [property: JsonPropertyName("mode")] string Mode,
    [property: JsonPropertyName("type")] string Type,
    [property: JsonPropertyName("method")] string Method,
    [property: JsonPropertyName("matcher")] string Matcher,
    [property: JsonPropertyName("args")] Dictionary<string, string> Args,
    [property: JsonPropertyName("keys")] List<string>? Keys,
    [property: JsonPropertyName("variants")] List<string>? Variants
);

internal sealed record SpecsFile(
    [property: JsonPropertyName("schema")] int Schema,
    [property: JsonPropertyName("facts")] List<FactSpec> Facts
);

internal sealed record FactResult(
    [property: JsonPropertyName("id")] string Id,
    [property: JsonPropertyName("mode")] string Mode,
    [property: JsonPropertyName("values")] Dictionary<string, string>? Values,
    [property: JsonPropertyName("ok")] bool? AssertOk
);

internal sealed class RunResult
{
    [JsonPropertyName("schema")]
    public int Schema { get; init; } = 1;

    [JsonPropertyName("assembly")]
    public required string Assembly { get; init; }

    [JsonPropertyName("facts")]
    public List<FactResult> Facts { get; } = new();

    [JsonPropertyName("errors")]
    public List<string> Errors { get; } = new();

    [JsonIgnore]
    public bool Ok => Errors.Count == 0 && Facts.All(f => f.AssertOk != false);

    private static readonly JsonSerializerOptions WriteOptions = new() { WriteIndented = true };

    public string ToJson() => JsonSerializer.Serialize(this, WriteOptions);

    public static SpecsFile LoadSpecs(string path)
    {
        var specs =
            JsonSerializer.Deserialize<SpecsFile>(File.ReadAllText(path))
            ?? throw new InvalidDataException($"empty specs file: {path}");
        if (specs.Schema != 1)
            throw new InvalidDataException($"unsupported specs schema {specs.Schema}");
        return specs;
    }
}
