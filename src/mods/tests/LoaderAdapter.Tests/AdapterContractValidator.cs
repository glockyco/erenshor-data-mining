using System.Xml;
using System.Xml.Linq;
using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;
using Microsoft.CodeAnalysis.CSharp.Syntax;
using Microsoft.CodeAnalysis.Text;

namespace LoaderAdapter.Tests;

internal sealed record AdapterContract(
    string ProjectPath,
    string SourcePath,
    string MetadataAttribute,
    string StartupMethod,
    string RuntimeReceiver
);

internal static class AdapterContractValidator
{
    public static IReadOnlyList<string> Validate(
        AdapterContract contract,
        string source,
        string? projectXml = null
    )
    {
        ArgumentNullException.ThrowIfNull(contract);
        ArgumentNullException.ThrowIfNull(source);

        var diagnostics = new List<string>();
        var tree = CSharpSyntaxTree.ParseText(source, path: contract.SourcePath);
        var root = tree.GetRoot();

        foreach (
            var error in tree.GetDiagnostics()
                .Where(diagnostic => diagnostic.Severity == DiagnosticSeverity.Error)
        )
        {
            diagnostics.Add(
                Diagnostic(
                    contract,
                    "syntax",
                    error.GetMessage(),
                    error.Location.IsInSource
                        ? error.Location.GetLineSpan().StartLinePosition
                        : null
                )
            );
        }

        var pluginClasses = root.DescendantNodes()
            .OfType<ClassDeclarationSyntax>()
            .Where(declaration => declaration.Identifier.ValueText == "Plugin")
            .ToArray();

        if (pluginClasses.Length == 0)
        {
            diagnostics.Add(Diagnostic(contract, "plugin-class", "no Plugin class was found"));
            return AppendProjectDiagnostics(contract, diagnostics, projectXml);
        }

        if (pluginClasses.Length != 1)
        {
            diagnostics.Add(
                Diagnostic(
                    contract,
                    "plugin-class",
                    $"expected exactly one Plugin class, found {pluginClasses.Length}",
                    pluginClasses[1].GetLocation().GetLineSpan().StartLinePosition
                )
            );
        }

        var plugin = pluginClasses[0];
        ValidateBaseType(contract, plugin, diagnostics);
        ValidateMetadata(contract, plugin, diagnostics);

        var awakeMethods = MethodsNamed(plugin, "Awake").ToArray();
        if (awakeMethods.Length == 0)
        {
            diagnostics.Add(
                Diagnostic(contract, "awake-first-operation", "Awake method is missing")
            );
        }
        else
        {
            if (awakeMethods.Length != 1)
            {
                diagnostics.Add(
                    Diagnostic(
                        contract,
                        "awake-first-operation",
                        $"expected exactly one Awake method, found {awakeMethods.Length}",
                        awakeMethods[1].GetLocation().GetLineSpan().StartLinePosition
                    )
                );
            }

            ValidateHideFlagsFirst(contract, awakeMethods[0], diagnostics);
        }

        var startupMethods = MethodsNamed(plugin, contract.StartupMethod).ToArray();
        if (startupMethods.Length == 0)
        {
            diagnostics.Add(
                Diagnostic(
                    contract,
                    "startup",
                    $"configured startup method '{contract.StartupMethod}' is missing"
                )
            );
        }
        else
        {
            if (
                !startupMethods.Any(method =>
                    HasInvocation(method, contract.RuntimeReceiver, "Start")
                )
            )
            {
                diagnostics.Add(
                    Diagnostic(
                        contract,
                        "startup",
                        $"startup method '{contract.StartupMethod}' does not invoke {contract.RuntimeReceiver}.Start()"
                    )
                );
            }

            if (string.Equals(contract.StartupMethod, "Awake", StringComparison.Ordinal))
            {
                var awake = startupMethods[0];
                var firstStatement = awake.Body?.Statements.FirstOrDefault();
                var startInvocation = Invocations(awake)
                    .FirstOrDefault(invocation =>
                        IsInvocation(invocation, contract.RuntimeReceiver, "Start")
                    );
                if (startInvocation is not null && firstStatement is not null)
                {
                    var hideStatement = firstStatement.GetLocation().SourceSpan;
                    if (startInvocation.SpanStart <= hideStatement.End)
                    {
                        diagnostics.Add(
                            Diagnostic(
                                contract,
                                "startup-order",
                                "startup invocation must occur after the first HideAndDontSave assignment",
                                startInvocation.GetLocation().GetLineSpan().StartLinePosition
                            )
                        );
                    }
                }
            }
        }

        var updateMethods = MethodsNamed(plugin, "Update").ToArray();
        if (updateMethods.Length == 0)
        {
            diagnostics.Add(Diagnostic(contract, "tick", "Update method is missing"));
        }
        else if (
            !updateMethods.Any(method => HasInvocation(method, contract.RuntimeReceiver, "Tick"))
        )
        {
            diagnostics.Add(
                Diagnostic(
                    contract,
                    "tick",
                    $"Update does not invoke {contract.RuntimeReceiver}.Tick()"
                )
            );
        }

        var destroyMethods = MethodsNamed(plugin, "OnDestroy").ToArray();
        if (destroyMethods.Length == 0)
        {
            diagnostics.Add(Diagnostic(contract, "stop", "OnDestroy method is missing"));
        }
        else
        {
            if (
                !destroyMethods.Any(method =>
                    HasInvocation(method, contract.RuntimeReceiver, "Stop")
                )
            )
            {
                diagnostics.Add(
                    Diagnostic(
                        contract,
                        "stop",
                        $"OnDestroy does not invoke {contract.RuntimeReceiver}.Stop()"
                    )
                );
            }

            if (awakeMethods.Length > 0)
            {
                ValidateSubscriptions(contract, awakeMethods[0], destroyMethods[0], diagnostics);
            }
        }

        return AppendProjectDiagnostics(contract, diagnostics, projectXml);
    }

    public static IReadOnlyList<string> ValidateInventory(
        IEnumerable<AdapterContract> contracts,
        IEnumerable<string> discoveredSourcePaths
    )
    {
        ArgumentNullException.ThrowIfNull(contracts);
        ArgumentNullException.ThrowIfNull(discoveredSourcePaths);

        var contractList = contracts.ToArray();
        var discovered = discoveredSourcePaths
            .Where(path => IsAdapterSource(path))
            .Select(NormalizePath)
            .ToArray();
        var diagnostics = new List<string>();

        if (discovered.Length == 0)
        {
            diagnostics.Add(
                "contract 'inventory' source 'inventory' check 'inventory': no maintained loader adapters were discovered"
            );
            return diagnostics;
        }

        foreach (
            var duplicate in contractList
                .GroupBy(contract => NormalizePath(contract.SourcePath), StringComparer.Ordinal)
                .Where(group => group.Count() > 1)
        )
        {
            diagnostics.Add(
                $"contract 'inventory' source '{duplicate.Key}' check 'inventory': duplicate inventory entry"
            );
        }

        var expected = contractList
            .Select(contract => NormalizePath(contract.SourcePath))
            .ToHashSet(StringComparer.Ordinal);
        var actual = discovered.ToHashSet(StringComparer.Ordinal);

        foreach (
            var missing in expected
                .Except(actual, StringComparer.Ordinal)
                .OrderBy(path => path, StringComparer.Ordinal)
        )
        {
            diagnostics.Add(
                $"contract 'inventory' source '{missing}' check 'inventory': maintained adapter is not discovered"
            );
        }

        foreach (
            var extra in actual
                .Except(expected, StringComparer.Ordinal)
                .OrderBy(path => path, StringComparer.Ordinal)
        )
        {
            diagnostics.Add(
                $"contract 'inventory' source '{extra}' check 'inventory': discovered adapter is not listed"
            );
        }

        if (discovered.Length != actual.Count)
        {
            diagnostics.Add(
                "contract 'inventory' source 'inventory' check 'inventory': discovered adapter set contains duplicate paths"
            );
        }

        return diagnostics;
    }

    public static IReadOnlyList<string> ValidateProjectCompileInclude(
        AdapterContract contract,
        string projectXml
    )
    {
        ArgumentNullException.ThrowIfNull(contract);
        ArgumentNullException.ThrowIfNull(projectXml);

        try
        {
            var document = XDocument.Parse(projectXml, LoadOptions.PreserveWhitespace);
            var projectDirectory = NormalizePath(
                Path.GetDirectoryName(contract.ProjectPath) ?? string.Empty
            );
            var expectedSource = NormalizePath(contract.SourcePath);
            var included = document
                .Descendants()
                .Where(element => element.Name.LocalName == "Compile")
                .Select(element => (string?)element.Attribute("Include"))
                .Where(include => !string.IsNullOrWhiteSpace(include))
                .Select(include => NormalizePath(include!))
                .ToArray();

            if (
                included.Any(include =>
                    string.Equals(include, expectedSource, StringComparison.Ordinal)
                    || string.Equals(
                        CombinePaths(projectDirectory, include),
                        expectedSource,
                        StringComparison.Ordinal
                    )
                )
            )
            {
                return Array.Empty<string>();
            }

            return new[]
            {
                Diagnostic(
                    contract,
                    "project-compile-include",
                    "adapter source is not an explicit Compile Include"
                ),
            };
        }
        catch (XmlException exception)
        {
            return new[]
            {
                Diagnostic(
                    contract,
                    "project-compile-include",
                    $"invalid project XML: {exception.Message}"
                ),
            };
        }
    }

    private static IReadOnlyList<string> AppendProjectDiagnostics(
        AdapterContract contract,
        List<string> diagnostics,
        string? projectXml
    )
    {
        if (projectXml is not null)
        {
            diagnostics.AddRange(ValidateProjectCompileInclude(contract, projectXml));
        }

        return diagnostics;
    }

    private static void ValidateBaseType(
        AdapterContract contract,
        ClassDeclarationSyntax plugin,
        ICollection<string> diagnostics
    )
    {
        var baseType = plugin.BaseList?.Types.FirstOrDefault()?.Type.ToString();
        var expectedBase = contract.MetadataAttribute switch
        {
            "BepInPlugin" => "BaseUnityPlugin",
            "LunarisPlugin" => "LunarisPlugin",
            _ => null,
        };

        if (
            expectedBase is not null
            && !string.Equals(baseType, expectedBase, StringComparison.Ordinal)
        )
        {
            diagnostics.Add(
                Diagnostic(
                    contract,
                    "base-type",
                    $"Plugin must derive directly from {expectedBase}; found '{baseType ?? "<none>"}'",
                    plugin.BaseList?.GetLocation().GetLineSpan().StartLinePosition
                )
            );
        }
    }

    private static void ValidateMetadata(
        AdapterContract contract,
        ClassDeclarationSyntax plugin,
        ICollection<string> diagnostics
    )
    {
        var metadata = plugin
            .AttributeLists.SelectMany(list => list.Attributes)
            .FirstOrDefault(attribute => AttributeName(attribute) == contract.MetadataAttribute);

        if (metadata is null)
        {
            diagnostics.Add(
                Diagnostic(
                    contract,
                    "metadata",
                    $"metadata attribute '{contract.MetadataAttribute}' is missing",
                    plugin.GetLocation().GetLineSpan().StartLinePosition
                )
            );
            return;
        }

        var arguments = metadata.ArgumentList?.Arguments;
        var expectedArgumentCount = contract.MetadataAttribute == "LunarisPlugin" ? 4 : 3;
        if (arguments is null || arguments.Value.Count < expectedArgumentCount)
        {
            diagnostics.Add(
                Diagnostic(
                    contract,
                    "metadata",
                    $"metadata attribute '{contract.MetadataAttribute}' must have at least {expectedArgumentCount} arguments",
                    metadata.GetLocation().GetLineSpan().StartLinePosition
                )
            );
            return;
        }

        if (!arguments.Value.Any(argument => IsVersionExpression(argument.Expression)))
        {
            diagnostics.Add(
                Diagnostic(
                    contract,
                    "metadata-version",
                    "metadata must contain a Version expression",
                    metadata.GetLocation().GetLineSpan().StartLinePosition
                )
            );
        }
    }

    private static void ValidateHideFlagsFirst(
        AdapterContract contract,
        MethodDeclarationSyntax awake,
        ICollection<string> diagnostics
    )
    {
        var first = awake.Body?.Statements.FirstOrDefault();
        if (
            first is ExpressionStatementSyntax firstExpression
            && firstExpression.Expression is AssignmentExpressionSyntax assignment
            && assignment.IsKind(SyntaxKind.SimpleAssignmentExpression)
            && IsMemberExpression(assignment.Left, "gameObject", "hideFlags")
            && IsMemberExpression(assignment.Right, "HideFlags", "HideAndDontSave")
        )
        {
            return;
        }

        diagnostics.Add(
            Diagnostic(
                contract,
                "awake-first-operation",
                "Awake first statement must assign gameObject.hideFlags = HideFlags.HideAndDontSave",
                first?.GetLocation().GetLineSpan().StartLinePosition
            )
        );
    }

    private static void ValidateSubscriptions(
        AdapterContract contract,
        MethodDeclarationSyntax awake,
        MethodDeclarationSyntax destroy,
        ICollection<string> diagnostics
    )
    {
        var additions = AssignmentExpressions(awake, SyntaxKind.AddAssignmentExpression).ToArray();
        var removals = AssignmentExpressions(destroy, SyntaxKind.SubtractAssignmentExpression)
            .ToArray();

        foreach (var addition in additions)
        {
            var key = AssignmentKey(addition);
            if (!removals.Any(removal => SubscriptionsMatch(addition, removal)))
            {
                diagnostics.Add(
                    Diagnostic(
                        contract,
                        "subscriptions",
                        $"subscription '{key}' in Awake has no matching unsubscription in OnDestroy",
                        addition.GetLocation().GetLineSpan().StartLinePosition
                    )
                );
            }
        }
    }

    private static IEnumerable<AssignmentExpressionSyntax> AssignmentExpressions(
        MethodDeclarationSyntax method,
        SyntaxKind kind
    ) =>
        LifecycleNodes(method)
            .OfType<AssignmentExpressionSyntax>()
            .Where(expression => expression.IsKind(kind));

    private static bool SubscriptionsMatch(
        AssignmentExpressionSyntax addition,
        AssignmentExpressionSyntax removal
    )
    {
        if (
            !TryGetMemberParts(addition.Left, out var addedReceiver, out var addedMember)
            || !TryGetMemberParts(removal.Left, out var removedReceiver, out var removedMember)
        )
        {
            return false;
        }

        return string.Equals(addedReceiver, removedReceiver, StringComparison.Ordinal)
            && string.Equals(addedMember, removedMember, StringComparison.Ordinal)
            && SyntaxFactory.AreEquivalent(addition.Right, removal.Right);
    }

    private static bool TryGetMemberParts(
        ExpressionSyntax expression,
        out string receiver,
        out string member
    )
    {
        if (expression is MemberAccessExpressionSyntax access)
        {
            receiver = NormalizeConfiguredExpression(access.Expression);
            member = access.Name.Identifier.ValueText;
            return true;
        }

        receiver = string.Empty;
        member = string.Empty;
        return false;
    }

    private static string AssignmentKey(AssignmentExpressionSyntax assignment) =>
        $"{assignment.Left} += {assignment.Right}";

    private static bool HasInvocation(
        MethodDeclarationSyntax method,
        string receiver,
        string member
    ) => Invocations(method).Any(invocation => IsInvocation(invocation, receiver, member));

    private static IEnumerable<InvocationExpressionSyntax> Invocations(
        MethodDeclarationSyntax method
    ) => LifecycleNodes(method).OfType<InvocationExpressionSyntax>();

    private static IEnumerable<SyntaxNode> LifecycleNodes(MethodDeclarationSyntax method)
    {
        if (method.Body is not null)
        {
            return method.Body.DescendantNodes(ShouldDescendIntoLifecycleBody);
        }

        return method.ExpressionBody?.Expression.DescendantNodesAndSelf(
                ShouldDescendIntoLifecycleBody
            ) ?? Enumerable.Empty<SyntaxNode>();
    }

    private static bool ShouldDescendIntoLifecycleBody(SyntaxNode node) =>
        node is not AnonymousFunctionExpressionSyntax && node is not LocalFunctionStatementSyntax;

    private static bool IsInvocation(
        InvocationExpressionSyntax invocation,
        string receiver,
        string member
    )
    {
        if (invocation.Expression is MemberAccessExpressionSyntax direct)
        {
            return string.Equals(direct.Name.Identifier.ValueText, member, StringComparison.Ordinal)
                && string.Equals(
                    NormalizeConfiguredExpression(direct.Expression),
                    receiver,
                    StringComparison.Ordinal
                );
        }

        if (
            invocation.Expression is MemberBindingExpressionSyntax binding
            && invocation.Parent is ConditionalAccessExpressionSyntax conditional
        )
        {
            return string.Equals(
                    binding.Name.Identifier.ValueText,
                    member,
                    StringComparison.Ordinal
                )
                && string.Equals(
                    NormalizeConfiguredExpression(conditional.Expression),
                    receiver,
                    StringComparison.Ordinal
                );
        }

        return false;
    }

    private static bool IsMemberExpression(
        ExpressionSyntax expression,
        string receiver,
        string member
    ) =>
        expression is MemberAccessExpressionSyntax access
        && string.Equals(access.Name.Identifier.ValueText, member, StringComparison.Ordinal)
        && string.Equals(
            NormalizeConfiguredExpression(access.Expression),
            receiver,
            StringComparison.Ordinal
        );

    private static bool IsVersionExpression(ExpressionSyntax expression)
    {
        expression = UnwrapParentheses(expression);
        return expression switch
        {
            IdentifierNameSyntax identifier => identifier.Identifier.ValueText == "Version",
            MemberAccessExpressionSyntax member => member.Name.Identifier.ValueText == "Version",
            _ => false,
        };
    }

    private static ExpressionSyntax UnwrapParentheses(ExpressionSyntax expression)
    {
        while (expression is ParenthesizedExpressionSyntax parenthesized)
        {
            expression = parenthesized.Expression;
        }

        return expression;
    }

    private static IEnumerable<MethodDeclarationSyntax> MethodsNamed(
        ClassDeclarationSyntax plugin,
        string name
    ) =>
        plugin
            .Members.OfType<MethodDeclarationSyntax>()
            .Where(method =>
                method.Identifier.ValueText == name && method.ParameterList.Parameters.Count == 0
            );

    private static string AttributeName(AttributeSyntax attribute)
    {
        var name = attribute.Name.ToString();
        var finalSegment = name[(name.LastIndexOf('.') + 1)..];
        return finalSegment.EndsWith("Attribute", StringComparison.Ordinal)
            ? finalSegment[..^"Attribute".Length]
            : finalSegment;
    }

    private static string NormalizeConfiguredExpression(ExpressionSyntax expression) =>
        expression.ToString().Trim();

    private static bool IsAdapterSource(string path)
    {
        var fileName = path.Replace('\\', '/').Split('/').Last();
        return fileName is "Plugin.BepInEx.cs" or "Plugin.Lunaris.cs";
    }

    private static string NormalizePath(string path)
    {
        var value = path.Replace('\\', '/').Trim();
        var absolute = value.StartsWith("/", StringComparison.Ordinal);
        var parts = new List<string>();
        foreach (var part in value.Split('/', StringSplitOptions.RemoveEmptyEntries))
        {
            if (part == ".")
            {
                continue;
            }

            if (part == ".." && parts.Count > 0 && parts[^1] != "..")
            {
                parts.RemoveAt(parts.Count - 1);
            }
            else if (part != "..")
            {
                parts.Add(part);
            }
            else
            {
                parts.Add(part);
            }
        }

        var normalized = string.Join('/', parts);
        return absolute ? "/" + normalized : normalized;
    }

    private static string CombinePaths(string directory, string include)
    {
        if (include.StartsWith("/", StringComparison.Ordinal))
        {
            return NormalizePath(include);
        }

        return NormalizePath(string.IsNullOrEmpty(directory) ? include : $"{directory}/{include}");
    }

    private static string Diagnostic(
        AdapterContract contract,
        string check,
        string message,
        LinePosition? position = null
    )
    {
        var location = position is null
            ? string.Empty
            : $" ({position.Value.Line + 1}:{position.Value.Character + 1})";
        return $"contract '{contract.MetadataAttribute}' source '{contract.SourcePath}' check '{check}'{location}: {message}";
    }
}
