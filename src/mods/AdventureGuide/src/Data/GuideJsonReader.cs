using System.Globalization;
using Newtonsoft.Json;

namespace AdventureGuide.Data;

internal sealed class GuideJsonReader : JsonReader
{
    private readonly JsonTextReader _reader;
    private List<string>? _strings;
    private bool _rootPropertySeen;
    private bool _referenceMetadata;

    internal GuideJsonReader(TextReader reader)
    {
        _reader = new JsonTextReader(reader) { DateParseHandling = DateParseHandling.None };
    }

    public override bool Read()
    {
        while (_reader.Read())
        {
            if (_reader.TokenType == JsonToken.Comment)
                continue;
            if (_reader.TokenType == JsonToken.PropertyName && _reader.Depth == 1)
            {
                if ((string?)_reader.Value == "_strings")
                {
                    if (_rootPropertySeen || _strings != null)
                        throw new JsonSerializationException(
                            "The guide string pool must come first"
                        );
                    ReadPool();
                    continue;
                }
                _rootPropertySeen = true;
            }
            object? value = _reader.Value;
            if (_reader.TokenType == JsonToken.PropertyName)
            {
                value = Expand((string)value!);
                _referenceMetadata = (string)value is "$id" or "$ref";
            }
            else
            {
                if (_reader.TokenType == JsonToken.String && !_referenceMetadata)
                    value = Expand((string)value!);
                _referenceMetadata = false;
            }
            SetToken(_reader.TokenType, value);
            return true;
        }
        SetToken(JsonToken.None);
        return false;
    }

    private void ReadPool()
    {
        if (!_reader.Read() || _reader.TokenType != JsonToken.StartArray)
            throw new JsonSerializationException("The guide string pool must be an array");
        _strings = new List<string>();
        while (_reader.Read())
        {
            if (_reader.TokenType == JsonToken.EndArray)
                return;
            if (_reader.TokenType != JsonToken.String)
                throw new JsonSerializationException("The guide string pool must contain strings");
            _strings.Add((string)_reader.Value!);
        }
        throw new JsonSerializationException("Unterminated guide string pool");
    }

    private string Expand(string value)
    {
        if (!value.StartsWith("~", StringComparison.Ordinal))
            return value;
        if (
            _strings == null
            || !int.TryParse(
                value.AsSpan(1),
                NumberStyles.None,
                CultureInfo.InvariantCulture,
                out int index
            )
            || index >= _strings.Count
        )
            throw new JsonSerializationException($"Invalid guide string reference: {value}");
        return _strings[index];
    }

    public override void Close()
    {
        _reader.Close();
        base.Close();
    }
}

internal sealed class GuideRowConverter : JsonConverter
{
    // Mask bits follow the sorted wire field names, not DTO declaration order.
    private static readonly RowField<SpawnPoint>[] SpawnFields =
    {
        new("activations", (v, r, s) => v.Activations = ReadList<ActivationReference>(r, s)),
        new("condition", (v, r, s) => v.Condition = ReadNullableInt(r)),
        new("entries", (v, r, s) => v.Entries = ReadList<int>(r, s)),
        new("is_directly_placed", (v, r, s) => v.IsDirectlyPlaced = ReadBoolean(r)),
        new("night_spawn", (v, r, s) => v.NightSpawn = ReadBoolean(r)),
        new("scene", (v, r, s) => v.Scene = ReadText(r)),
        new("source_script", (v, r, s) => v.SourceScript = ReadString(r)),
        new("stable_key", (v, r, s) => v.StableKey = ReadText(r)),
        new("x", (v, r, s) => v.X = ReadFloat(r)),
        new("y", (v, r, s) => v.Y = ReadFloat(r)),
        new("z", (v, r, s) => v.Z = ReadFloat(r)),
    };

    private static readonly RowField<SourceLocation>[] LocationFields =
    {
        new(
            "conditions",
            (v, r, s) =>
                v.Conditions = ReadList<SourceCondition>(r, s) ?? throw InvalidValue("conditions")
        ),
        new(
            "entry_zone_line_keys",
            (v, r, s) =>
                v.EntryZoneLineKeys =
                    ReadList<string>(r, s) ?? throw InvalidValue("entry_zone_line_keys")
        ),
        new("marker_stable_key", (v, r, s) => v.MarkerStableKey = ReadString(r)),
        new("place_key", (v, r, s) => v.PlaceKey = ReadText(r)),
        new("player_level_max", (v, r, s) => v.PlayerLevelMax = ReadNullableInt(r)),
        new("player_level_min", (v, r, s) => v.PlayerLevelMin = ReadNullableInt(r)),
        new("relation", (v, r, s) => v.Relation = ReadText(r)),
        new("scene", (v, r, s) => v.Scene = ReadString(r)),
        new("source_copy_stable_key", (v, r, s) => v.SourceCopyStableKey = ReadString(r)),
        new("x", (v, r, s) => v.X = ReadNullableFloat(r)),
        new("y", (v, r, s) => v.Y = ReadNullableFloat(r)),
        new("z", (v, r, s) => v.Z = ReadNullableFloat(r)),
        new("zone", (v, r, s) => v.Zone = ReadString(r)),
        new("zone_stable_key", (v, r, s) => v.ZoneStableKey = ReadString(r)),
    };

    public override bool CanWrite => false;

    public override bool CanConvert(Type objectType) =>
        objectType == typeof(SpawnPoint) || objectType == typeof(SourceLocation);

    public override object ReadJson(
        JsonReader reader,
        Type objectType,
        object? existingValue,
        JsonSerializer serializer
    )
    {
        if (objectType == typeof(SpawnPoint))
            return ReadRow(reader, serializer, new SpawnPoint(), SpawnFields);
        return ReadRow(reader, serializer, new SourceLocation(), LocationFields);
    }

    private static T ReadRow<T>(
        JsonReader reader,
        JsonSerializer serializer,
        T value,
        RowField<T>[] fields
    )
        where T : class
    {
        if (reader.TokenType == JsonToken.StartObject)
        {
            serializer.Populate(reader, value);
            return value;
        }
        if (
            reader.TokenType != JsonToken.StartArray
            || !reader.Read()
            || reader.TokenType != JsonToken.Integer
        )
            throw new JsonSerializationException("A guide row must start with an integer mask");
        int mask = ReadInt(reader);
        if (mask < 0 || mask >= 1 << fields.Length)
            throw new JsonSerializationException("Unknown guide row mask bits");
        for (int index = 0; index < fields.Length; index++)
        {
            if ((mask & (1 << index)) == 0)
                continue;
            if (!reader.Read())
                throw new JsonSerializationException(
                    $"Missing guide row value: {fields[index].Name}"
                );
            fields[index].Read(value, reader, serializer);
        }
        if (!reader.Read() || reader.TokenType != JsonToken.EndArray)
            throw new JsonSerializationException("Guide row value count does not match its mask");
        return value;
    }

    private static int ReadInt(JsonReader reader)
    {
        if (reader.TokenType != JsonToken.Integer)
            throw InvalidValue("integer");
        try
        {
            return Convert.ToInt32(reader.Value, CultureInfo.InvariantCulture);
        }
        catch (Exception error)
            when (error is OverflowException or InvalidCastException or FormatException)
        {
            throw new JsonSerializationException("Invalid guide row integer", error);
        }
    }

    private static int? ReadNullableInt(JsonReader reader) =>
        reader.TokenType == JsonToken.Null ? null : ReadInt(reader);

    private static float ReadFloat(JsonReader reader)
    {
        if (reader.TokenType is not (JsonToken.Integer or JsonToken.Float))
            throw InvalidValue("number");
        float value;
        try
        {
            value = Convert.ToSingle(reader.Value, CultureInfo.InvariantCulture);
        }
        catch (Exception error)
            when (error is OverflowException or InvalidCastException or FormatException)
        {
            throw new JsonSerializationException("Invalid guide row number", error);
        }
        if (float.IsNaN(value) || float.IsInfinity(value))
            throw InvalidValue("finite number");
        return value;
    }

    private static float? ReadNullableFloat(JsonReader reader) =>
        reader.TokenType == JsonToken.Null ? null : ReadFloat(reader);

    private static bool ReadBoolean(JsonReader reader) =>
        reader.TokenType == JsonToken.Boolean ? (bool)reader.Value! : throw InvalidValue("boolean");

    private static string ReadText(JsonReader reader) =>
        reader.TokenType == JsonToken.String ? (string)reader.Value! : throw InvalidValue("string");

    private static string? ReadString(JsonReader reader) =>
        reader.TokenType == JsonToken.Null ? null : ReadText(reader);

    private static List<T>? ReadList<T>(JsonReader reader, JsonSerializer serializer)
    {
        if (
            reader.TokenType
            is not (JsonToken.StartArray or JsonToken.StartObject or JsonToken.Null)
        )
            throw InvalidValue("list");
        return serializer.Deserialize<List<T>>(reader);
    }

    private static JsonSerializationException InvalidValue(string field) =>
        new($"Invalid guide row value: {field}");

    public override void WriteJson(JsonWriter writer, object? value, JsonSerializer serializer) =>
        throw new NotSupportedException();

    private readonly struct RowField<T>
    {
        internal string Name { get; }
        internal Action<T, JsonReader, JsonSerializer> Read { get; }

        internal RowField(string name, Action<T, JsonReader, JsonSerializer> read)
        {
            Name = name;
            Read = read;
        }
    }
}
