using BepInEx.Logging;
using Newtonsoft.Json;
using System.Reflection;
using System.Text;

namespace AdventureGuide.CompiledGuide;

public static class CompiledGuideLoader
{
    private const string ResourceName = "AdventureGuide.guide.json";

    public static CompiledGuide Load(ManualLogSource log)
    {
        var assembly = Assembly.GetExecutingAssembly();
        using Stream stream = assembly.GetManifestResourceStream(ResourceName)
            ?? throw new InvalidOperationException($"Embedded resource '{ResourceName}' not found.");
        using var reader = new StreamReader(stream, Encoding.UTF8);
        string json = reader.ReadToEnd();
        var guide = ParseJson(json);
        log.LogInfo($"Loaded compiled guide: {guide.NodeCount} nodes, {guide.EdgeCount} edges, {guide.QuestCount} quests, {guide.ItemCount} items");
        return guide;
    }

    internal static CompiledGuide ParseJson(string json)
    {
        var data = JsonConvert.DeserializeObject<CompiledGuideData>(json)
            ?? throw new InvalidDataException("Failed to deserialize compiled guide JSON.");
        return new CompiledGuide(data);
    }
}
