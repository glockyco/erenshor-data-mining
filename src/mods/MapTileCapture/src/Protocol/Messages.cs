using Newtonsoft.Json;

namespace MapTileCapture.Protocol;

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
/// Rule for excluding specific renderers from a capture by name or position.
/// All specified predicates must match (AND semantics). At least one predicate
/// must be non-null for the rule to match anything.
/// </summary>
public sealed class ExclusionRule
{
    /// <summary>Renderer's GameObject name must equal this value exactly (ordinal).</summary>
    public string? NameExact { get; set; }

    /// <summary>Renderer's GameObject name must contain this substring (case-insensitive).</summary>
    public string? NameContains { get; set; }

    /// <summary>Renderer's world Y position must be strictly above this value.</summary>
    public float? PositionAbove { get; set; }
}

/// <summary>
/// Where a portrait capture finds its subject. Either <see cref="ResourcesPath"/>
/// names a prefab that <c>Resources.Load</c> loads without a scene, or
/// <see cref="Scene"/> and <see cref="ObjectName"/> name a character of that
/// scene: the one nearest <see cref="Position"/> when the scene places it, or
/// else the prefab that the loaded scene references. A placed character that
/// has started answers to <see cref="NpcName"/>, because <c>NPC.Start</c>
/// renames it. The player lands at <see cref="Landing"/> while the scene is loaded.
/// </summary>
public sealed class PortraitSource
{
    [JsonProperty("resourcesPath")]
    public string? ResourcesPath { get; set; }

    [JsonProperty("scene")]
    public string? Scene { get; set; }

    [JsonProperty("objectName")]
    public string? ObjectName { get; set; }

    [JsonProperty("npcName")]
    public string? NpcName { get; set; }

    [JsonProperty("position")]
    public float[]? Position { get; set; }

    [JsonProperty("landing")]
    public float[]? Landing { get; set; }

    /// <summary>
    /// The item whose model the capture shows by itself, instead of a character.
    /// A furnishing also names the <see cref="Scene"/> that holds it and a
    /// <see cref="Landing"/>; the other kinds come from the player's body.
    /// </summary>
    [JsonProperty("item")]
    public ItemModelSource? Item { get; set; }
}

/// <summary>
/// An item model: a weapon or shield, the parts of a worn item, a mask, a
/// furniture set's furnishing, or a cosmetic object. <see cref="Part"/> is the
/// item's <c>EquipmentToActivate</c>, or for a cosmetic object "belt lamp" or
/// "lens", and <see cref="Body"/> names the body whose parts show a weapon, a
/// worn item, or a mask.
/// </summary>
public sealed class ItemModelSource
{
    [JsonProperty("id")]
    public string Id { get; set; } = "";

    [JsonProperty("kind")]
    public string Kind { get; set; } = "";

    [JsonProperty("body")]
    public string? Body { get; set; }

    [JsonProperty("slot")]
    public string Slot { get; set; } = "";

    [JsonProperty("part")]
    public string Part { get; set; } = "";
}

/// <summary>A request to capture one subject as a portrait PNG.</summary>
public sealed class CapturePortraitRequest
{
    [JsonProperty("subject")]
    public string Subject { get; set; } = "";

    [JsonProperty("stableKey")]
    public string StableKey { get; set; } = "";

    [JsonProperty("preset")]
    public string Preset { get; set; } = "";

    [JsonProperty("source")]
    public PortraitSource? Source { get; set; }

    [JsonProperty("outputPath")]
    public string OutputPath { get; set; } = "";

    [JsonProperty("sceneLoadTimeoutSecs")]
    public float SceneLoadTimeoutSecs { get; set; }

    [JsonProperty("stabilityFrames")]
    public int StabilityFrames { get; set; }

    /// <summary>Why the mod cannot run the request, or null when it can.</summary>
    public string? Problem()
    {
        if (string.IsNullOrWhiteSpace(Subject) || string.IsNullOrWhiteSpace(StableKey))
            return "The request names no subject or no stable key.";
        if (string.IsNullOrWhiteSpace(OutputPath))
            return "The request names no output path.";
        if (Source == null)
            return "The request names no source.";
        if (Source.Item != null)
            return ItemProblem(Source, Source.Item);
        if (Preset != PortraitPreset.Name)
            return $"The mod captures characters with preset {PortraitPreset.Name}, not {Preset}.";

        bool fromResources = !string.IsNullOrWhiteSpace(Source.ResourcesPath);
        bool fromScene = !string.IsNullOrWhiteSpace(Source.Scene);
        if (fromResources == fromScene)
            return "The source must name either a resources path or a scene.";
        if (fromResources)
        {
            return
                Source.ObjectName == null
                && Source.NpcName == null
                && Source.Position == null
                && Source.Landing == null
                ? null
                : "A resources source takes no object name, NPC name, position, or landing.";
        }
        if (string.IsNullOrWhiteSpace(Source.ObjectName))
            return "A scene source must name its object.";
        if (Source.Landing is not { Length: 3 })
            return "A scene source must give a landing of three coordinates.";
        if (Source.Position is not null and not { Length: 3 })
            return "A position must have three coordinates.";
        return null;
    }

    private string? ItemProblem(PortraitSource source, ItemModelSource item)
    {
        if (Preset != PortraitPreset.ItemName)
            return $"The mod captures items with preset {PortraitPreset.ItemName}, not {Preset}.";
        if (string.IsNullOrWhiteSpace(item.Id) || string.IsNullOrWhiteSpace(item.Part))
            return "An item source must name the item's ID and part.";
        if (
            source.ResourcesPath != null
            || source.ObjectName != null
            || source.NpcName != null
            || source.Position != null
        )
            return "An item source takes no resources path, object name, NPC name, or position.";
        switch (item.Kind)
        {
            case "furnishing":
                if (string.IsNullOrWhiteSpace(source.Scene) || source.Landing is not { Length: 3 })
                    return "A furnishing names its scene and a landing of three coordinates.";
                return null;
            case "weapon":
            case "worn":
            case "mask":
                if (source.Scene != null || source.Landing != null)
                    return "A weapon, worn item, or mask comes from the player's body and names no scene.";
                if (item.Kind != "mask" && item.Body is not ("male" or "female"))
                    return "A weapon or worn item names the male or the female body.";
                return null;
            case "cosmetic":
                if (source.Scene != null || source.Landing != null)
                    return "A cosmetic object comes from the player and names no scene.";
                if (item.Part is not ("belt lamp" or "lens"))
                    return $"No cosmetic object is called {item.Part}.";
                return null;
            default:
                return $"Unknown item kind {item.Kind}.";
        }
    }
}
