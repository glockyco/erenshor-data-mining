using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using Newtonsoft.Json.Serialization;

namespace MapTileCapture.Protocol;

/// <summary>
/// JSON serialization for the MapTileCapture WebSocket protocol.
/// Uses camelCase naming for Python interop compatibility.
/// </summary>
public static class MessageSerializer
{
    private static readonly JsonSerializerSettings Settings = new()
    {
        ContractResolver = new CamelCasePropertyNamesContractResolver(),
        NullValueHandling = NullValueHandling.Include,
        Formatting = Formatting.None,
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
            var obj = JObject.Parse(json);
            var type = obj["type"]?.ToString();

            return type switch
            {
                "capture_zone" => JsonConvert.DeserializeObject<CaptureZoneMessage>(json, Settings),
                "cancel_capture" => JsonConvert.DeserializeObject<CancelCaptureMessage>(json, Settings),
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
        JsonConvert.SerializeObject(message, Settings);
}
