using Newtonsoft.Json;

namespace MapTileCapture.Protocol;

/// <summary>
/// Specification for a single chunk to capture within a zone.
/// </summary>
public sealed class ChunkSpec
{
    [JsonProperty("index")]
    public int Index { get; set; }

    [JsonProperty("centerX")]
    public float CenterX { get; set; }

    [JsonProperty("centerZ")]
    public float CenterZ { get; set; }

    [JsonProperty("worldWidth")]
    public float WorldWidth { get; set; }

    [JsonProperty("worldHeight")]
    public float WorldHeight { get; set; }

    [JsonProperty("pixelWidth")]
    public int PixelWidth { get; set; }

    [JsonProperty("pixelHeight")]
    public int PixelHeight { get; set; }

    [JsonProperty("outputPath")]
    public string OutputPath { get; set; } = "";
}

/// <summary>
/// Rule for excluding specific renderers from a capture by name or position.
/// All specified predicates must match (AND semantics). At least one predicate
/// must be non-null for the rule to match anything.
/// </summary>
public sealed class ExclusionRule
{
    /// <summary>Renderer's GameObject name must equal this value exactly (ordinal).</summary>
    public string? NameExact { get; set; }

    /// <summary>Renderer's GameObject name must contain this substring (case-insensitive).</summary>
    public string? NameContains { get; set; }

    /// <summary>Renderer's world Y position must be strictly above this value.</summary>
    public float? PositionAbove { get; set; }
}
