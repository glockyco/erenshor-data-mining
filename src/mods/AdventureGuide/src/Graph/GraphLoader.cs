using System.Diagnostics;
using System.Reflection;
using BepInEx.Logging;
using Newtonsoft.Json;

namespace AdventureGuide.Graph;

/// <summary>
/// Loads the entity graph from the embedded <c>entity-graph.json</c> resource.
/// Uses streaming <see cref="JsonTextReader"/> to avoid allocating the entire
/// JSON string, deserializing each node/edge individually.
/// </summary>
public static class GraphLoader
{
    private const string ResourceName = "AdventureGuide.entity-graph.json";
    private const int ExpectedVersion = 6;

    public static EntityGraph Load(ManualLogSource log)
    {
        var sw = Stopwatch.StartNew();

        var assembly = Assembly.GetExecutingAssembly();
        using var stream = assembly.GetManifestResourceStream(ResourceName);
        if (stream == null)
        {
            log.LogError($"Embedded resource '{ResourceName}' not found");
            return new EntityGraph(Array.Empty<Node>(), Array.Empty<Edge>());
        }

        try
        {
            return ParseGraph(stream, log, sw);
        }
        catch (Exception ex)
        {
            log.LogError($"Failed to load entity graph: {ex.Message}");
            return new EntityGraph(Array.Empty<Node>(), Array.Empty<Edge>());
        }
    }

    private static EntityGraph ParseGraph(Stream stream, ManualLogSource log, Stopwatch sw)
    {
        var serializer = JsonSerializer.CreateDefault();
        using var textReader = new StreamReader(stream);
        using var reader = new JsonTextReader(textReader);

        int version = 0;
        int nodeCount = 0;
        int edgeCount = 0;
        Node[]? nodes = null;
        Edge[]? edges = null;

        // Read the top-level object
        reader.Read(); // StartObject
        while (reader.Read() && reader.TokenType == JsonToken.PropertyName)
        {
            var prop = (string)reader.Value!;
            switch (prop)
            {
                case "_version":
                    version = reader.ReadAsInt32() ?? 0;
                    if (version != ExpectedVersion)
                        log.LogWarning($"Entity graph version {version}, expected {ExpectedVersion}");
                    break;

                case "_node_count":
                    nodeCount = reader.ReadAsInt32() ?? 0;
                    break;

                case "_edge_count":
                    edgeCount = reader.ReadAsInt32() ?? 0;
                    break;

                case "_nodes":
                    nodes = ReadArray<Node>(reader, serializer, nodeCount);
                    // Intern node keys for reduced memory and fast reference equality
                    for (int i = 0; i < nodes.Length; i++)
                        nodes[i].Key = string.Intern(nodes[i].Key);
                    break;

                case "_edges":
                    edges = ReadArray<Edge>(reader, serializer, edgeCount);
                    // Intern edge source/target to share strings with node keys
                    for (int i = 0; i < edges.Length; i++)
                    {
                        edges[i].Source = string.Intern(edges[i].Source);
                        edges[i].Target = string.Intern(edges[i].Target);
                    }
                    break;

                default:
                    reader.Read();
                    reader.Skip();
                    break;
            }
        }

        nodes ??= Array.Empty<Node>();
        edges ??= Array.Empty<Edge>();

        var graph = new EntityGraph(nodes, edges);
        sw.Stop();
        log.LogInfo($"Entity graph loaded: {graph.NodeCount} nodes, {graph.EdgeCount} edges in {sw.ElapsedMilliseconds}ms");
        return graph;
    }

    /// <summary>
    /// Reads a JSON array by deserializing each element individually.
    /// Pre-sizes the list from the count hint to avoid resizing.
    /// </summary>
    private static T[] ReadArray<T>(JsonTextReader reader, JsonSerializer serializer, int sizeHint)
    {
        reader.Read(); // StartArray
        if (reader.TokenType != JsonToken.StartArray)
            return Array.Empty<T>();

        var list = sizeHint > 0 ? new List<T>(sizeHint) : new List<T>();
        while (reader.Read() && reader.TokenType != JsonToken.EndArray)
        {
            var item = serializer.Deserialize<T>(reader);
            if (item != null)
                list.Add(item);
        }
        return list.ToArray();
    }
}
