using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace MapTileCapture.Protocol;

// ── Envelope (routing only) ─────────────────────────────────────────

/// <summary>
/// Thin envelope deserialized first to determine message type before
/// full deserialization. Only the "type" field is read.
/// </summary>
public sealed class MessageEnvelope
{
    [JsonProperty("type")]
    public string Type { get; set; } = "";
}

// ── Shared types ────────────────────────────────────────────────────

/// <summary>
/// Axis-aligned bounding rectangle in world coordinates.
/// </summary>
public sealed class Bounds
{
    [JsonProperty("minX")]
    public float MinX { get; set; }

    [JsonProperty("minZ")]
    public float MinZ { get; set; }

    [JsonProperty("maxX")]
    public float MaxX { get; set; }

    [JsonProperty("maxZ")]
    public float MaxZ { get; set; }
}

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
/// Rule for suppressing specific renderers during capture.
/// <c>Value</c> is a <see cref="JToken"/> because it is polymorphic:
/// a string for nameExact/nameContains rules, a float for positionAbove rules.
/// </summary>
public sealed class ExclusionRule
{
    [JsonProperty("ruleType")]
    public string RuleType { get; set; } = "";

    /// <summary>
    /// String for name-based rules, float for position-based rules.
    /// Kept as JToken to defer type resolution to the consumer.
    /// </summary>
    [JsonProperty("value")]
    public JToken? Value { get; set; }
}

// ── Inbound messages (Python → Mod) ─────────────────────────────────

/// <summary>
/// Request to capture all chunks for a single zone/variant combination.
/// </summary>
public sealed class CaptureZoneMessage
{
    [JsonProperty("type")]
    public string Type { get; set; } = "capture_zone";

    [JsonProperty("zone")]
    public string Zone { get; set; } = "";

    [JsonProperty("sceneName")]
    public string SceneName { get; set; } = "";

    [JsonProperty("variant")]
    public string Variant { get; set; } = "";

    [JsonProperty("hideRoofs")]
    public bool HideRoofs { get; set; }

    [JsonProperty("sceneLoadTimeoutSecs")]
    public float SceneLoadTimeoutSecs { get; set; } = 30f;

    [JsonProperty("stabilityFrames")]
    public int StabilityFrames { get; set; } = 10;

    [JsonProperty("exclusionRules")]
    public ExclusionRule[] ExclusionRules { get; set; } = System.Array.Empty<ExclusionRule>();

    [JsonProperty("chunks")]
    public ChunkSpec[] Chunks { get; set; } = System.Array.Empty<ChunkSpec>();
}

/// <summary>
/// Request to cancel any in-progress capture.
/// </summary>
public sealed class CancelCaptureMessage
{
    [JsonProperty("type")]
    public string Type { get; set; } = "cancel_capture";
}

// ── Outbound messages (Mod → Python) ────────────────────────────────

/// <summary>
/// Sent after each chunk screenshot is written to disk.
/// </summary>
public sealed class ChunkCompleteMessage
{
    [JsonProperty("type")]
    public string Type { get; } = "chunk_complete";

    [JsonProperty("zone")]
    public string Zone { get; set; } = "";

    [JsonProperty("variant")]
    public string Variant { get; set; } = "";

    [JsonProperty("chunkIndex")]
    public int ChunkIndex { get; set; }

    [JsonProperty("path")]
    public string Path { get; set; } = "";

    [JsonProperty("measuredBounds")]
    public Bounds? MeasuredBounds { get; set; }
}

/// <summary>
/// Sent after all chunks for a zone/variant have been captured.
/// </summary>
public sealed class CaptureZoneCompleteMessage
{
    [JsonProperty("type")]
    public string Type { get; } = "capture_zone_complete";

    [JsonProperty("zone")]
    public string Zone { get; set; } = "";

    [JsonProperty("variant")]
    public string Variant { get; set; } = "";

    [JsonProperty("roofObjectCount")]
    public int RoofObjectCount { get; set; }

    /// <summary>
    /// North bearing in degrees, or null if not determined.
    /// </summary>
    [JsonProperty("northBearing")]
    public float? NorthBearing { get; set; }

    [JsonProperty("zoneBounds")]
    public Bounds? ZoneBounds { get; set; }
}

/// <summary>
/// Sent when a capture fails for a zone/variant.
/// </summary>
public sealed class CaptureErrorMessage
{
    [JsonProperty("type")]
    public string Type { get; } = "capture_error";

    [JsonProperty("zone")]
    public string Zone { get; set; } = "";

    [JsonProperty("variant")]
    public string Variant { get; set; } = "";

    [JsonProperty("reason")]
    public string Reason { get; set; } = "";
}
