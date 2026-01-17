using System.Text.Json;
using System.Text.Json.Serialization;

namespace InteractiveMapCompanion.Protocol;

/// <summary>
/// JSON serialization for WebSocket protocol messages.
/// Uses camelCase naming convention for JavaScript compatibility.
/// </summary>
public static class MessageSerializer
{
    private static readonly JsonSerializerOptions Options = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
        WriteIndented = false
    };

    public static string Serialize<T>(T message) =>
        JsonSerializer.Serialize(message, Options);

    public static T? Deserialize<T>(string json) =>
        JsonSerializer.Deserialize<T>(json, Options);
}
