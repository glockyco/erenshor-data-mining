using Newtonsoft.Json;

namespace AdventureGuide.Data;

[JsonConverter(typeof(GateAtomKindConverter))]
public enum GateAtomKind
{
    QuestDone = 1,
    QuestNotDone,
    ItemHeld,
    KeyHeld,
    RoomFurnished,
    EncounterWon,
    PlanningSlotItem,
    AccountState,
}

internal sealed class GateAtomKindConverter : JsonConverter
{
    public override bool CanConvert(Type objectType) => objectType == typeof(GateAtomKind);

    public override object ReadJson(
        JsonReader reader,
        Type objectType,
        object? existingValue,
        JsonSerializer serializer
    ) =>
        reader.Value switch
        {
            "quest_done" => GateAtomKind.QuestDone,
            "quest_not_done" => GateAtomKind.QuestNotDone,
            "item_held" => GateAtomKind.ItemHeld,
            "key_held" => GateAtomKind.KeyHeld,
            "room_furnished" => GateAtomKind.RoomFurnished,
            "planning_slot_item" => GateAtomKind.PlanningSlotItem,
            "encounter_won" => GateAtomKind.EncounterWon,
            "account_state" => GateAtomKind.AccountState,
            _ => throw new InvalidDataException($"Unknown gate atom kind {reader.Value}"),
        };

    public override void WriteJson(JsonWriter writer, object? value, JsonSerializer serializer)
    {
        string name = value switch
        {
            GateAtomKind.QuestDone => "quest_done",
            GateAtomKind.QuestNotDone => "quest_not_done",
            GateAtomKind.ItemHeld => "item_held",
            GateAtomKind.KeyHeld => "key_held",
            GateAtomKind.RoomFurnished => "room_furnished",
            GateAtomKind.PlanningSlotItem => "planning_slot_item",
            GateAtomKind.EncounterWon => "encounter_won",
            GateAtomKind.AccountState => "account_state",
            _ => throw new InvalidDataException($"Unknown gate atom kind {value}"),
        };
        writer.WriteValue(name);
    }
}

public sealed class GateAtom
{
    [JsonProperty("kind")]
    public GateAtomKind Kind { get; set; }

    [JsonProperty("ref")]
    public string Ref { get; set; } = "";

    [JsonProperty("quantity")]
    public int Quantity { get; set; } = 1;

    [JsonProperty("slot")]
    public string? Slot { get; set; }

    [JsonProperty("instruction")]
    public string? Instruction { get; set; }

    [JsonProperty("actor")]
    public string? Actor { get; set; }

    [JsonProperty("value")]
    public string? Value { get; set; }

    [JsonProperty("phase")]
    public string? Phase { get; set; }

    [JsonProperty("scope")]
    public string? Scope { get; set; }

    [JsonIgnore]
    public string? GameId { get; internal set; }
}

public sealed class GateItem
{
    [JsonProperty("name")]
    public string Name { get; set; } = "";

    [JsonProperty("game_id")]
    public string GameId { get; set; } = "";

    [JsonProperty("sources")]
    public List<ItemSource>? Sources { get; set; }

    [JsonProperty("door_zones")]
    public List<string>? DoorZones { get; set; }
}
