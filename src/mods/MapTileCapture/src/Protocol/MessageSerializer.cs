using System;
using System.Text.Json;

namespace MapTileCapture.Protocol;

/// <summary>
/// JSON serialization for the MapTileCapture WebSocket protocol.
/// Uses camelCase naming for Python interop compatibility.
/// </summary>
public static class MessageSerializer
{
    private static readonly JsonSerializerOptions Options = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        WriteIndented = false,
        // Serialize null values so Python receives explicit null for
        // fields like northBearing rather than a missing key.
        DefaultIgnoreCondition = System.Text.Json.Serialization.JsonIgnoreCondition.Never,
    };

    /// <summary>
    /// Deserialize an inbound JSON message into its typed representation.
    /// The envelope "type" field is read first to determine the concrete type.
    /// </summary>
    /// <returns>
    /// A <see cref="CaptureZoneMessage"/> or <see cref="CancelCaptureMessage"/>,
    /// or null if the message type is unrecognized or the JSON is malformed.
    /// </returns>
    public static object? ParseInbound(string json)
    {
        if (string.IsNullOrEmpty(json))
            return null;

        try
        {
            var envelope = JsonSerializer.Deserialize<MessageEnvelope>(json, Options);
            if (envelope == null)
                return null;

            return envelope.Type switch
            {
                "capture_zone" => JsonSerializer.Deserialize<CaptureZoneMessage>(json, Options),
                "cancel_capture" => JsonSerializer.Deserialize<CancelCaptureMessage>(json, Options),
                _ => null,
            };
        }
        catch (JsonException)
        {
            return null;
        }
    }

    /// <summary>
    /// Serialize an outbound message to JSON.
    /// </summary>
    public static string Serialize<T>(T message) =>
        JsonSerializer.Serialize(message, Options);
}
