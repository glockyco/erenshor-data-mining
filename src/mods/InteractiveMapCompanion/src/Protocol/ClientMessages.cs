using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace InteractiveMapCompanion.Protocol;

/// <summary>
/// Reads the messages a trusted map on this PC sends to the mod.
/// </summary>
public static class ClientMessages
{
    /// <summary>
    /// Reads <c>{"type":"setSharing","enabled":true|false}</c>. Returns false for any
    /// other message, including one whose <c>enabled</c> is not a JSON boolean.
    /// </summary>
    public static bool TryReadSetSharing(string json, out bool enabled)
    {
        enabled = false;
        JObject message;
        try
        {
            message = JObject.Parse(json);
        }
        catch (JsonException)
        {
            return false;
        }

        if (
            message["type"] is not JValue { Type: JTokenType.String } type
            || (string?)type != "setSharing"
            || message["enabled"] is not JValue { Type: JTokenType.Boolean } value
        )
            return false;

        enabled = (bool)value;
        return true;
    }
}
