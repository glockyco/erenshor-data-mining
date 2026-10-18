using Newtonsoft.Json;

namespace AdventureGuide.Data;

public sealed class OfferingActivation
{
    [JsonProperty("script")]
    public string Script { get; set; } = "";

    [JsonProperty("scene")]
    public string Scene { get; set; } = "";

    [JsonProperty("display_name")]
    public string? DisplayName { get; set; }

    [JsonProperty("site")]
    public ActivationSite? Site { get; set; }

    [JsonProperty("offerings")]
    public List<Offering> Offerings { get; set; } = new();
}

public sealed class Offering
{
    [JsonProperty("item_stable_key")]
    public string ItemStableKey { get; set; } = "";

    [JsonProperty("item_name")]
    public string ItemName { get; set; } = "";

    [JsonProperty("spawns")]
    public List<OfferingSpawn> Spawns { get; set; } = new();

    [JsonProperty("reward")]
    public string? Reward { get; set; }

    [JsonProperty("random")]
    public bool Random { get; set; }

    [JsonIgnore]
    internal GateAtom Requirement { get; set; } = null!;

    [JsonIgnore]
    internal string Warning { get; set; } = "";
}

public sealed class OfferingSpawn
{
    [JsonProperty("character")]
    public string Character { get; set; } = "";

    [JsonProperty("quantity")]
    public int Quantity { get; set; }

    [JsonIgnore]
    internal string DefeatInstruction { get; set; } = "";
}

public sealed class ActivationReference
{
    [JsonProperty("key")]
    public string Key { get; set; } = "";

    [JsonProperty("offering")]
    public int Offering { get; set; }

    [JsonProperty("role")]
    public string Role { get; set; } = "";

    [JsonIgnore]
    internal string Instruction { get; set; } = "";

    [JsonIgnore]
    internal string WarningInstruction { get; set; } = "";
}

public class ActivationPosition
{
    [JsonProperty("x")]
    public float X { get; set; }

    [JsonProperty("y")]
    public float Y { get; set; }

    [JsonProperty("z")]
    public float Z { get; set; }
}

public sealed class ActivationSite : ActivationPosition
{
    [JsonProperty("bounds")]
    public ActivationBounds Bounds { get; set; } = null!;
}

public sealed class ActivationBounds
{
    [JsonProperty("center")]
    public ActivationPosition Center { get; set; } = null!;

    [JsonProperty("extents")]
    public ActivationPosition Extents { get; set; } = null!;
}

internal sealed partial class GuideWrapper
{
    [JsonProperty("_activations")]
    public Dictionary<string, OfferingActivation>? Activations { get; set; }
}

public sealed partial class GuideData
{
    public IReadOnlyDictionary<string, OfferingActivation> Activations { get; private set; } =
        new Dictionary<string, OfferingActivation>();
    internal IReadOnlyList<string> ActivationCharacters { get; private set; } =
        Array.Empty<string>();
    private readonly Dictionary<SpawnPoint, string> _activationCharacterKeys = new();
    private readonly Dictionary<string, HashSet<(int X, int Y, int Z)>> _offeringPositions = new(
        StringComparer.OrdinalIgnoreCase
    );

    internal string ActivationCharacter(SpawnPoint spawn) => _activationCharacterKeys[spawn];

    private void LoadActivations(GuideWrapper wrapper)
    {
        Activations = wrapper.Activations ?? new Dictionary<string, OfferingActivation>();
        var bound = new HashSet<(string Key, int Offering, string Role, string Character)>();
        var names = new Dictionary<string, string>(StringComparer.Ordinal);
        void ReadNames(List<ItemSource>? sources)
        {
            if (sources == null)
                return;
            foreach (var source in sources)
            {
                if (source.SourceKey != null && source.Name != null)
                    names[source.SourceKey] = source.Name;
                ReadNames(source.Children);
            }
        }
        foreach (var quest in All)
        {
            if (quest.RequiredItems != null)
                foreach (var item in quest.RequiredItems)
                    ReadNames(item.Sources);
            if (quest.Steps != null)
                foreach (var step in quest.Steps)
                {
                    if (
                        step.TargetType == "character"
                        && step.TargetKey != null
                        && step.TargetName != null
                    )
                        names[step.TargetKey] = step.TargetName;
                    ReadNames(step.Sources);
                }
        }
        foreach (var item in GateItems.Values)
            ReadNames(item.Sources);
        string Name(string key) =>
            names.TryGetValue(key, out var name) ? name
            : key.StartsWith("character:", StringComparison.Ordinal) ? key.Substring(10)
            : key;
        foreach (var (key, activation) in Activations)
        {
            if (
                string.IsNullOrWhiteSpace(key)
                || string.IsNullOrWhiteSpace(activation.Script)
                || string.IsNullOrWhiteSpace(activation.Scene)
                || activation.Offerings.Count == 0
            )
                throw new InvalidDataException($"Invalid activation {key}");
            if (
                activation.Site is { } site
                && (
                    !Finite(site)
                    || site.Bounds == null
                    || !Finite(site.Bounds.Center)
                    || !Finite(site.Bounds.Extents)
                    || site.Bounds.Extents.X < 0
                    || site.Bounds.Extents.Y < 0
                    || site.Bounds.Extents.Z < 0
                )
            )
                throw new InvalidDataException($"Invalid activation site {key}");
            foreach (var offering in activation.Offerings)
            {
                if (
                    !GateItems.TryGetValue(offering.ItemStableKey, out var item)
                    || string.IsNullOrWhiteSpace(item.GameId)
                    || string.IsNullOrWhiteSpace(offering.ItemName)
                    || offering.Spawns.Count == 0
                )
                    throw new InvalidDataException(
                        $"Activation {key} names missing offering gate item {offering.ItemStableKey}"
                    );
                offering.Requirement = new GateAtom
                {
                    Kind = GateAtomKind.ItemHeld,
                    Ref = offering.ItemStableKey,
                };
                offering.Warning =
                    $"Carry only {offering.ItemName}; another carried offering can be used first.";
                foreach (var spawn in offering.Spawns)
                {
                    if (string.IsNullOrWhiteSpace(spawn.Character) || spawn.Quantity <= 0)
                        throw new InvalidDataException($"Invalid activation spawn {key}");
                    spawn.DefeatInstruction = "Defeat " + Name(spawn.Character) + ".";
                }
            }
        }
        foreach (var (character, spawns) in CharacterSpawns)
        foreach (var spawn in spawns)
        {
            if (spawn.Activations == null)
                continue;
            if (spawn.Activations.Count == 0)
                throw new InvalidDataException("Empty placement activations");
            _activationCharacterKeys.Add(spawn, character);
            foreach (var reference in spawn.Activations)
            {
                if (
                    !Activations.TryGetValue(reference.Key, out var activation)
                    || reference.Offering < 0
                    || reference.Offering >= activation.Offerings.Count
                    || !string.Equals(
                        spawn.Scene,
                        activation.Scene,
                        StringComparison.OrdinalIgnoreCase
                    )
                )
                    throw new InvalidDataException(
                        $"Invalid placement activation {reference.Key}/{reference.Offering}"
                    );
                var offering = activation.Offerings[reference.Offering];
                if (
                    reference.Role == "reward"
                        ? offering.Reward != character
                        : reference.Role != "spawn"
                            || !offering.Spawns.Exists(member => member.Character == character)
                )
                    throw new InvalidDataException($"Activation role mismatch for {character}");
                bound.Add((reference.Key, reference.Offering, reference.Role, character));
                reference.Instruction =
                    activation.DisplayName != null
                        ? $"Bring {offering.ItemName} to {activation.DisplayName}."
                        : $"Bring {offering.ItemName} to where {Name(character)} appears.";
                if (offering.Random)
                    reference.Instruction += " A random opponent appears.";
                reference.WarningInstruction = reference.Instruction + "\n" + offering.Warning;
            }
        }
        var characters = new HashSet<string>(StringComparer.Ordinal);
        foreach (var (key, activation) in Activations)
            for (int index = 0; index < activation.Offerings.Count; index++)
            {
                var offering = activation.Offerings[index];
                foreach (var member in offering.Spawns)
                {
                    if (!bound.Contains((key, index, "spawn", member.Character)))
                        throw new InvalidDataException(
                            $"Unbound activation spawn {key}/{index}/{member.Character}"
                        );
                    characters.Add(member.Character);
                }
                if (offering.Reward is { } reward)
                {
                    if (!bound.Contains((key, index, "reward", reward)))
                        throw new InvalidDataException(
                            $"Unbound activation reward {key}/{index}/{reward}"
                        );
                    characters.Add(reward);
                }
            }
        ActivationCharacters = characters.ToArray();
        void Prepare(List<ItemSource>? sources)
        {
            if (sources == null)
                return;
            foreach (var source in sources)
            {
                var instructions = new List<string>();
                void Add(SpawnPoint spawn)
                {
                    if (spawn.Activations == null)
                        return;
                    foreach (var reference in spawn.Activations)
                        if (!instructions.Contains(reference.Instruction))
                            instructions.Add(reference.Instruction);
                }
                if (source.CanonicalSpawn is { } canonical)
                {
                    Add(canonical);
                    if (canonical.Activations != null && source.SourceKey != null)
                        _activationCharacterKeys[canonical] = source.SourceKey;
                }
                else if (
                    source.SourceKey != null
                    && CharacterSpawns.TryGetValue(source.SourceKey, out var spawns)
                )
                    foreach (var spawn in spawns)
                        Add(spawn);
                if (instructions.Count > 0)
                    source.ActivationInstruction = string.Join("\n", instructions);
                Prepare(source.Children);
            }
        }
        foreach (var quest in All)
        {
            if (quest.RequiredItems != null)
                foreach (var item in quest.RequiredItems)
                    Prepare(item.Sources);
            if (quest.Steps != null)
                foreach (var step in quest.Steps)
                    Prepare(step.Sources);
        }
        foreach (var item in GateItems.Values)
            Prepare(item.Sources);
        foreach (var spawns in CharacterSpawns.Values)
        foreach (var spawn in spawns)
        {
            if (spawn.Activations == null)
                continue;
            if (!_offeringPositions.TryGetValue(spawn.Scene, out var positions))
                _offeringPositions.Add(spawn.Scene, positions = new HashSet<(int, int, int)>());
            positions.Add(PositionKey(spawn.X, spawn.Y, spawn.Z));
        }
        foreach (var spawns in CharacterSpawns.Values)
        foreach (var spawn in spawns)
            if (
                spawn.Activations == null
                && _offeringPositions.TryGetValue(spawn.Scene, out var positions)
            )
                positions.Remove(PositionKey(spawn.X, spawn.Y, spawn.Z));
    }

    internal bool IsOfferingOnlyPosition(string scene, float x, float y, float z) =>
        _offeringPositions.TryGetValue(scene, out var positions)
        && positions.Contains(PositionKey(x, y, z));

    private static (int, int, int) PositionKey(float x, float y, float z) =>
        ((int)Math.Round(x * 100f), (int)Math.Round(y * 100f), (int)Math.Round(z * 100f));

    private static bool Finite(ActivationPosition? position) =>
        position != null && IsFinite(position.X) && IsFinite(position.Y) && IsFinite(position.Z);
}
