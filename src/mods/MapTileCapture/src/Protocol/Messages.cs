using System.Text.Json.Serialization;

namespace MapTileCapture.Protocol;

// ── Envelope (routing only) ─────────────────────────────────────────

/// <summary>
/// Thin envelope deserialized first to determine message type before
/// full deserialization. Only the "type" field is read.
/// </summary>
public sealed class MessageEnvelope
{
    [JsonPropertyName("type")]
    public string Type { get; set; } = "";
}

// ── Shared types ────────────────────────────────────────────────────

/// <summary>
/// Axis-aligned bounding rectangle in world coordinates.
/// </summary>
public sealed class Bounds
{
    [JsonPropertyName("minX")]
    public float MinX { get; set; }

    [JsonPropertyName("minZ")]
    public float MinZ { get; set; }

    [JsonPropertyName("maxX")]
    public float MaxX { get; set; }

    [JsonPropertyName("maxZ")]
    public float MaxZ { get; set; }
}

/// <summary>
/// Specification for a single chunk to capture within a zone.
/// </summary>
public sealed class ChunkSpec
{
    [JsonPropertyName("index")]
    public int Index { get; set; }

    [JsonPropertyName("centerX")]
    public float CenterX { get; set; }

    [JsonPropertyName("centerZ")]
    public float CenterZ { get; set; }

    [JsonPropertyName("worldWidth")]
    public float WorldWidth { get; set; }

    [JsonPropertyName("worldHeight")]
    public float WorldHeight { get; set; }

    [JsonPropertyName("pixelWidth")]
    public int PixelWidth { get; set; }

    [JsonPropertyName("pixelHeight")]
    public int PixelHeight { get; set; }

    [JsonPropertyName("outputPath")]
    public string OutputPath { get; set; } = "";
}

/// <summary>
/// Rule for suppressing specific renderers during capture.
/// <c>Value</c> is a <see cref="System.Text.Json.JsonElement"/> because
/// it is polymorphic: a string for nameExact/nameContains rules, a float
/// for positionAbove rules.
/// </summary>
public sealed class ExclusionRule
{
    [JsonPropertyName("ruleType")]
    public string RuleType { get; set; } = "";

    /// <summary>
    /// String for name-based rules, float for position-based rules.
    /// Kept as JsonElement to defer type resolution to the consumer.
    /// </summary>
    [JsonPropertyName("value")]
    public System.Text.Json.JsonElement Value { get; set; }
}

// ── Inbound messages (Python → Mod) ─────────────────────────────────

/// <summary>
/// Request to capture all chunks for a single zone/variant combination.
/// </summary>
public sealed class CaptureZoneMessage
{
    [JsonPropertyName("type")]
    public string Type { get; set; } = "capture_zone";

    [JsonPropertyName("zone")]
    public string Zone { get; set; } = "";

    [JsonPropertyName("sceneName")]
    public string SceneName { get; set; } = "";

    [JsonPropertyName("variant")]
    public string Variant { get; set; } = "";

    [JsonPropertyName("hideRoofs")]
    public bool HideRoofs { get; set; }

    [JsonPropertyName("sceneLoadTimeoutSecs")]
    public float SceneLoadTimeoutSecs { get; set; } = 30f;

    [JsonPropertyName("stabilityFrames")]
    public int StabilityFrames { get; set; } = 10;

    [JsonPropertyName("exclusionRules")]
    public ExclusionRule[] ExclusionRules { get; set; } = System.Array.Empty<ExclusionRule>();

    [JsonPropertyName("chunks")]
    public ChunkSpec[] Chunks { get; set; } = System.Array.Empty<ChunkSpec>();
}

/// <summary>
/// Request to cancel any in-progress capture.
/// </summary>
public sealed class CancelCaptureMessage
{
    [JsonPropertyName("type")]
    public string Type { get; set; } = "cancel_capture";
}

// ── Outbound messages (Mod → Python) ────────────────────────────────

/// <summary>
/// Sent after each chunk screenshot is written to disk.
/// </summary>
public sealed class ChunkCompleteMessage
{
    [JsonPropertyName("type")]
    public string Type { get; } = "chunk_complete";

    [JsonPropertyName("zone")]
    public string Zone { get; set; } = "";

    [JsonPropertyName("variant")]
    public string Variant { get; set; } = "";

    [JsonPropertyName("chunkIndex")]
    public int ChunkIndex { get; set; }

    [JsonPropertyName("path")]
    public string Path { get; set; } = "";

    [JsonPropertyName("measuredBounds")]
    public Bounds? MeasuredBounds { get; set; }
}

/// <summary>
/// Sent after all chunks for a zone/variant have been captured.
/// </summary>
public sealed class CaptureZoneCompleteMessage
{
    [JsonPropertyName("type")]
    public string Type { get; } = "capture_zone_complete";

    [JsonPropertyName("zone")]
    public string Zone { get; set; } = "";

    [JsonPropertyName("variant")]
    public string Variant { get; set; } = "";

    [JsonPropertyName("roofObjectCount")]
    public int RoofObjectCount { get; set; }

    /// <summary>
    /// North bearing in degrees, or null if not determined.
    /// </summary>
    [JsonPropertyName("northBearing")]
    public float? NorthBearing { get; set; }

    [JsonPropertyName("zoneBounds")]
    public Bounds? ZoneBounds { get; set; }
}

/// <summary>
/// Sent when a capture fails for a zone/variant.
/// </summary>
public sealed class CaptureErrorMessage
{
    [JsonPropertyName("type")]
    public string Type { get; } = "capture_error";

    [JsonPropertyName("zone")]
    public string Zone { get; set; } = "";

    [JsonPropertyName("variant")]
    public string Variant { get; set; } = "";

    [JsonPropertyName("reason")]
    public string Reason { get; set; } = "";
}
