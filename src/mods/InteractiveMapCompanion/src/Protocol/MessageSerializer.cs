using Newtonsoft.Json;
using Newtonsoft.Json.Serialization;

namespace InteractiveMapCompanion.Protocol;

/// <summary>
/// JSON serialization for WebSocket protocol messages.
/// Uses camelCase naming convention for JavaScript compatibility.
/// </summary>
public static class MessageSerializer
{
    private static readonly JsonSerializerSettings Settings = new()
    {
        ContractResolver = new DefaultContractResolver
        {
            NamingStrategy = new CamelCaseNamingStrategy(),
        },
        NullValueHandling = NullValueHandling.Ignore,
        Formatting = Formatting.None,
    };

    public static string Serialize<T>(T message) => JsonConvert.SerializeObject(message, Settings);

    public static T? Deserialize<T>(string json) =>
        JsonConvert.DeserializeObject<T>(json, Settings);
}
