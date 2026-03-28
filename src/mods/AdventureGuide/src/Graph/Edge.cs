using System.ComponentModel;
using Newtonsoft.Json;
using Newtonsoft.Json.Converters;

namespace AdventureGuide.Graph;

public sealed class Edge
{
    [JsonProperty("s")] public string Source { get; set; } = "";
    [JsonProperty("t")] public string Target { get; set; } = "";
    [JsonProperty("type"), JsonConverter(typeof(StringEnumConverter))] public EdgeType Type { get; set; }

    [JsonProperty("group")] public string? Group { get; set; }
    [JsonProperty("ordinal")] public int? Ordinal { get; set; }
    [JsonProperty("negated"), DefaultValue(false)] public bool Negated { get; set; }
    [JsonProperty("quantity")] public int? Quantity { get; set; }
    [JsonProperty("keyword")] public string? Keyword { get; set; }
    [JsonProperty("note")] public string? Note { get; set; }
    [JsonProperty("chance")] public float? Chance { get; set; }
    [JsonProperty("amount")] public int? Amount { get; set; }
    [JsonProperty("slot")] public int? Slot { get; set; }

    public override string ToString() => $"{Source} --{Type}--> {Target}";
}
