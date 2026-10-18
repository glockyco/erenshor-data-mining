using System.Text.Json;
using System.Text.Json.Serialization;
using ICSharpCode.Decompiler.CSharp;
using ICSharpCode.Decompiler.CSharp.Syntax;
using ICSharpCode.Decompiler.Semantics;

namespace CodeFacts;

internal sealed record BehaviourEntry(
    [property: JsonPropertyName("classification")] string Classification,
    [property: JsonPropertyName("apis")] List<string> Apis,
    [property: JsonPropertyName("component")] string? Component = null,
    [property: JsonPropertyName("reason")] string? Reason = null,
    [property: JsonPropertyName("tasks")] List<string>? Tasks = null
);

internal sealed record BehaviourCatalog(
    [property: JsonPropertyName("schema")] int Schema,
    [property: JsonPropertyName("types")] Dictionary<string, BehaviourEntry> Types
);

internal static class BehaviourCoverage
{
    // Methods denote calls. Read fields exclude a plain assignment target.
    // Write fields include compound assignments and increment/decrement.
    private static readonly Dictionary<string, bool> Apis = new(StringComparer.Ordinal)
    {
        ["GameData.IsQuestDone"] = false,
        ["GameData.CompletedQuests"] = false,
        ["GameData.HasQuest"] = false,
        ["Inventory.HasItem"] = false,
        ["Inventory.HasCosmetic"] = false,
        ["GameData.AccountClaimedReliquary"] = false,
        ["AtmosphereColors.isRaining"] = false,
        ["SceneChange.ChangeScene"] = true,
        ["SceneChange.ChangeSceneSafe"] = true,
        ["GameData.FinishQuest"] = true,
        ["GameData.AssignQuest"] = true,
        ["Character.Invulnerable"] = true,
        ["AtmosphereColors.WeightGoal"] = true,
        ["AtmosphereColors.SinceRain"] = true,
    };

    public static SortedDictionary<string, SortedSet<string>> Inventory(CSharpDecompiler decompiler)
    {
        var inventory = new SortedDictionary<string, SortedSet<string>>(StringComparer.Ordinal);
        foreach (var type in decompiler.TypeSystem.MainModule.TypeDefinitions)
        {
            if (type.DeclaringTypeDefinition is not null || type.Name == "<Module>")
                continue;
            var tree = decompiler.DecompileType(type.FullTypeName);
            foreach (var node in tree.Descendants)
            {
                if (
                    node is not Expression
                    || node.Annotation<ResolveResult>() is not MemberResolveResult resolved
                )
                    continue;
                var member = resolved.Member;
                string api = $"{member.DeclaringType.FullName}.{member.Name}";
                if (!Apis.TryGetValue(api, out bool write))
                    continue;
                bool method = member is ICSharpCode.Decompiler.TypeSystem.IMethod;
                if (method && node is not InvocationExpression)
                    continue;
                if (!method)
                {
                    bool assigned =
                        node.Parent is AssignmentExpression assignment && assignment.Left == node;
                    bool incremented =
                        node.Parent is UnaryOperatorExpression unary
                        && unary.Operator
                            is UnaryOperatorType.Increment
                                or UnaryOperatorType.Decrement
                                or UnaryOperatorType.PostIncrement
                                or UnaryOperatorType.PostDecrement;
                    if (write && !assigned && !incremented)
                        continue;
                    if (
                        !write
                        && node.Parent
                            is AssignmentExpression
                            {
                                Operator: AssignmentOperatorType.Assign
                            } plain
                        && plain.Left == node
                    )
                        continue;
                }
                var declaration = node.Ancestors.OfType<TypeDeclaration>().FirstOrDefault();
                string owner = declaration?.Annotation<ResolveResult>()
                    is TypeResolveResult ownerType
                    ? ownerType.Type.FullName
                    : type.FullName;
                if (!inventory.TryGetValue(owner, out var uses))
                    inventory[owner] = uses = new(StringComparer.Ordinal);
                uses.Add(api);
            }
        }
        return inventory;
    }

    public static BehaviourCatalog Load(string path)
    {
        var catalog =
            JsonSerializer.Deserialize<BehaviourCatalog>(File.ReadAllText(path))
            ?? throw new InvalidDataException($"empty behaviour catalog: {path}");
        if (catalog.Schema != 1)
            throw new InvalidDataException(
                $"unsupported behaviour catalog schema {catalog.Schema}"
            );
        return catalog;
    }

    public static IEnumerable<string> Check(
        IReadOnlyDictionary<string, SortedSet<string>> inventory,
        BehaviourCatalog catalog,
        ISet<string> assemblyTypes
    )
    {
        foreach (var (type, actual) in inventory)
        {
            if (!catalog.Types.TryGetValue(type, out var entry))
            {
                yield return $"{type}: unclassified progression behaviour ({string.Join(", ", actual)})";
                continue;
            }
            if (!actual.SetEquals(entry.Apis) || entry.Apis.Count != actual.Count)
                yield return $"{type}: changed API set, catalog [{string.Join(", ", entry.Apis)}], assembly [{string.Join(", ", actual)}]";
            string? missing = entry.Classification switch
            {
                "adapter" or "core" => string.IsNullOrWhiteSpace(entry.Component)
                    ? "component"
                    : null,
                "excluded" => string.IsNullOrWhiteSpace(entry.Reason) ? "reason" : null,
                "pending" => entry.Tasks is null
                || entry.Tasks.Count == 0
                || entry.Tasks.Any(string.IsNullOrWhiteSpace)
                    ? "tasks"
                    : null,
                _ => "valid classification",
            };
            if (missing is not null)
                yield return $"{type}: {entry.Classification} entry requires {missing}";
        }
        foreach (string type in catalog.Types.Keys.Order(StringComparer.Ordinal))
        {
            if (!assemblyTypes.Contains(type))
                yield return $"{type}: stale catalog entry, type absent from assembly";
            else if (!inventory.ContainsKey(type))
                yield return $"{type}: stale catalog entry, no listed progression API use";
        }
    }
}
