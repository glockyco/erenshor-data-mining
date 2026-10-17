using ICSharpCode.Decompiler;
using ICSharpCode.Decompiler.CSharp;
using ICSharpCode.Decompiler.CSharp.Syntax;
using ICSharpCode.Decompiler.Metadata;
using ICSharpCode.Decompiler.TypeSystem;
using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;
using Microsoft.CodeAnalysis.CSharp.Syntax;
using Xunit;

namespace CodeFacts.Tests;

internal static class NativeAstFixture
{
    private static readonly MetadataReference[] References = RuntimeReferences();
    private static readonly CSharpCompilationOptions Options = new(
        OutputKind.DynamicallyLinkedLibrary,
        optimizationLevel: OptimizationLevel.Debug
    );

    private static readonly SwitchSectionSyntax[] SwitchContext = (
        (SwitchStatementSyntax)
            SyntaxFactory.ParseStatement(
                """
                switch (operation) {
                    case "__fixture_first": OtherLog.LogAdd("first context"); break;
                    case "__fixture_second": OtherLog.LogAdd("second context"); break;
                }
                """
            )
    ).Sections.ToArray();

    public static MethodDeclaration FromBody(string body)
    {
        string framework =
            AppContext.TargetFrameworkName
            ?? throw new InvalidOperationException(
                "The fixture host has no target framework identity"
            );
        string attribute =
            "[assembly: System.Runtime.Versioning.TargetFramework(\"" + framework + "\")]\n";
        var syntax = CSharpSyntaxTree.ParseText(
            "using System.Collections.Generic;\n" + attribute + ContextStart + body + ContextEnd
        );
        var root = syntax.GetRoot();
        var switches = root.DescendantNodes().OfType<SwitchStatementSyntax>().ToArray();
        if (switches.Length != 0)
        {
            // Unrelated cases and a following statement preserve the native switch form through lowering.
            root = root.ReplaceNodes(
                switches,
                (_, rewritten) => rewritten.AddSections(SwitchContext)
            );
            var execute = root.DescendantNodes()
                .OfType<MethodDeclarationSyntax>()
                .Single(method => method.Identifier.ValueText == "Execute");
            root = root.ReplaceNode(
                execute,
                execute.WithBody(
                    execute.Body!.AddStatements(
                        SyntaxFactory.ParseStatement("OtherLog.LogAdd(\"after operation\");")
                    )
                )
            );
        }
        var compilation = CSharpCompilation.Create(
            "NativeFixture",
            syntaxTrees: [syntax.WithRootAndOptions(root, syntax.Options)],
            references: References,
            options: Options
        );
        string path = Path.Combine(Path.GetTempPath(), $"native-ast-{Guid.NewGuid():N}.dll");
        try
        {
            using (var output = File.Create(path))
            {
                var emitted = compilation.Emit(output);
                Assert.True(
                    emitted.Success,
                    emitted.Success ? null : string.Join(Environment.NewLine, emitted.Diagnostics)
                );
            }
            var resolver = new UniversalAssemblyResolver(
                path,
                throwOnError: false,
                targetFramework: framework
            );
            var decompiler = new CSharpDecompiler(path, resolver, new DecompilerSettings());
            var tree = decompiler.DecompileType(new FullTypeName("NativeOperations"));
            return Assert.Single(
                tree.Descendants.OfType<MethodDeclaration>(),
                method => method.Name == "Execute"
            );
        }
        finally
        {
            File.Delete(path);
        }
    }

    private static MetadataReference[] RuntimeReferences()
    {
        string assemblies =
            (string?)AppContext.GetData("TRUSTED_PLATFORM_ASSEMBLIES")
            ?? throw new InvalidOperationException(
                "The fixture host has no runtime assembly locations"
            );
        var names = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        {
            "System.Private.CoreLib.dll",
            "System.Runtime.dll",
            "System.Collections.dll",
        };
        var references = new List<MetadataReference>(names.Count);
        foreach (string path in assemblies.Split(Path.PathSeparator))
        {
            if (names.Remove(Path.GetFileName(path)))
                references.Add(MetadataReference.CreateFromFile(path));
        }
        Assert.Empty(names);
        return references.ToArray();
    }

    private const string ContextStart = """
        class NativeOperations {
            public string operation = "Break Fossil";
            public bool eligible;
            public int Quantity;
            public Item item = new Item();
            public Item otherItem = new Item();
            public string itemId = "other";
            public Inventory otherInventory = new Inventory();
            public ItemDatabase otherDatabase = new ItemDatabase();
            void Execute() {
        """;

    private const string ContextEnd = """
            }
            public class Item { }
            public class OtherItem {
                public static implicit operator OtherItem(Item item) => new OtherItem();
                public static implicit operator Item(OtherItem item) => new Item();
            }
            public class MiscData {
                public List<Item> FossilGame = new List<Item>();
            }
            public class Inventory {
                public bool AddItemToInv(Item item) => false;
                public bool AddItemToInv(Item item, int quantity) => false;
                public bool ForceItemToInv(Item item) => true;
                public bool ForceItemToInv(Item item, int quantity) => true;
                public int OtherInventoryMethod(Item item) => 0;
            }
            public class ItemDatabase {
                public Item GetItemByID(string id) => new Item();
            }
            public static class GameData {
                public static MiscData Misc = new MiscData();
                public static Inventory PlayerInv = new Inventory();
                public static ItemDatabase ItemDB = new ItemDatabase();
            }
            public static class Random {
                public static int Range(int minimum, int maximum) => minimum;
            }
            public static class OtherRandom {
                public static int Range(int minimum, int maximum) => minimum;
            }
            public static class UpdateSocialLog {
                public static void LogAdd(object message) { }
            }
            public static class OtherLog {
                public static void LogAdd(object message) { }
            }
        }
        """;
}
