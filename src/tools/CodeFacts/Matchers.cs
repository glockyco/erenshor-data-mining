using System.Globalization;
using ICSharpCode.Decompiler;
using ICSharpCode.Decompiler.CSharp;
using ICSharpCode.Decompiler.CSharp.Syntax;
using ICSharpCode.Decompiler.Metadata;
using ICSharpCode.Decompiler.TypeSystem;

namespace CodeFacts;

internal static class Runner
{
    public static RunResult Run(string assemblyPath, string specsPath, string? variant = null)
    {
        var specs = RunResult.LoadSpecs(specsPath);
        var result = new RunResult { Assembly = assemblyPath };
        // Resolve only against the assembly's own directory -- the game's
        // Managed/ folder ships its full dependency closure -- and tolerate
        // anything missing. Decompilation stays hermetic: it never reaches into
        // the host .NET runtime for a core library, so the pinned decompiler
        // renders identically on any SDK/runtime. The spec-pinned output is a
        // function of the input DLL, not the toolchain that runs this tool.
        var resolver = new UniversalAssemblyResolver(assemblyPath, throwOnError: false, targetFramework: null);
        var decompiler = new CSharpDecompiler(assemblyPath, resolver, new DecompilerSettings());
        string? activeVariant = string.IsNullOrWhiteSpace(variant) ? null : variant;

        foreach (var fact in specs.Facts)
        {
            if (!AppliesToVariant(fact, activeVariant)) continue;
            try
            {
                var method = FindMethod(decompiler, fact);
                var values = fact.Matcher switch
                {
                    "guarded_member_roll" => Matchers.GuardedMemberRoll(method, fact),
                    "string_constants" => Matchers.StringConstants(method, fact),
                    "int_comparisons" => Matchers.IntComparisons(method, fact),
                    "statement_shape" => Matchers.StatementShape(method, fact),
                    "string_set" => Matchers.StringSet(method, fact),
                    "node_shape" => Matchers.NodeShape(method, fact),
                    _ => throw new InvalidDataException($"unknown matcher '{fact.Matcher}'"),
                };
                result.Facts.Add(fact.Mode == "assert"
                    ? new FactResult(fact.Id, fact.Mode, null, AssertOk: true)
                    : new FactResult(fact.Id, fact.Mode, values, null));
            }
            catch (Exception ex)
            {
                result.Errors.Add($"{fact.Id}: {ex.Message}");
            }
        }
        return result;
    }

    private static MethodDeclaration FindMethod(CSharpDecompiler decompiler, FactSpec fact)
    {
        SyntaxTree tree = decompiler.DecompileType(new FullTypeName(fact.Type));
        var matches = tree.Descendants.OfType<MethodDeclaration>()
            .Where(m => m.Name == fact.Method).ToList();
        if (matches.Count != 1)
            throw new InvalidDataException(
                $"method {fact.Type}::{fact.Method} bound {matches.Count} times (need exactly 1)");
        return matches[0];
    }

    private static bool AppliesToVariant(FactSpec fact, string? activeVariant)
    {
        if (fact.Variants is null || fact.Variants.Count == 0) return true;
        if (activeVariant is null) return true;
        return fact.Variants.Contains(activeVariant);
    }
}

internal static class Matchers
{
    /// Binds the unique `if` whose then-branch references args["member"] in an
    /// Add(...) call and whose condition compares a float literal (optionally
    /// `* expr`). Emits rate (literal as invariant string) and min_level
    /// (from a `Level > N` conjunct, else "0").
    public static Dictionary<string, string> GuardedMemberRoll(MethodDeclaration method, FactSpec fact)
    {
        string member = fact.Args["member"];
        var hits = new List<(string Rate, string MinLevel)>();

        foreach (var ifs in method.Descendants.OfType<IfElseStatement>())
        {
            bool addsMember = ifs.TrueStatement.Descendants.OfType<InvocationExpression>().Any(inv =>
                inv.Target is MemberReferenceExpression { MemberName: "Add" }
                && inv.Arguments.Count == 1
                && NodeMentions(inv.Arguments.First(), member));
            if (!addsMember) continue;

            string? rate = ifs.Condition.DescendantsAndSelf.OfType<BinaryOperatorExpression>()
                .Where(b => b.Operator == BinaryOperatorType.LessThan)
                .Select(b => FloatLiteralOf(b.Right) ?? FloatLiteralOf(b.Left))
                .FirstOrDefault(v => v is not null);
            if (rate is null) continue;

            string minLevel = ifs.Condition.DescendantsAndSelf.OfType<BinaryOperatorExpression>()
                .Where(b => b.Operator == BinaryOperatorType.GreaterThan
                    && MemberNamed(b.Left, "Level")
                    && b.Right is PrimitiveExpression { Value: int })
                .Select(b => ((PrimitiveExpression)b.Right).Value!.ToString()!)
                .FirstOrDefault() ?? "0";

            hits.Add((rate, minLevel));
        }

        if (hits.Count != 1)
            throw new InvalidDataException(
                $"guarded_member_roll('{member}') bound {hits.Count} times (need exactly 1)");
        return new() { ["rate"] = hits[0].Rate, ["min_level"] = hits[0].MinLevel };
    }

    /// All distinct string literals used in `==` comparisons in the method,
    /// in source order, joined with ','.
    public static Dictionary<string, string> StringConstants(MethodDeclaration method, FactSpec fact)
    {
        var strings = method.Descendants.OfType<BinaryOperatorExpression>()
            .Where(b => b.Operator == BinaryOperatorType.Equality)
            .SelectMany(b => new[] { b.Left, b.Right })
            .OfType<PrimitiveExpression>()
            .Where(p => p.Value is string)
            .Select(p => (string)p.Value!)
            .Distinct()
            .ToList();
        if (strings.Count == 0)
            throw new InvalidDataException("string_constants bound 0 literals (need >= 1)");
        return new() { ["strings"] = string.Join(",", strings) };
    }

    /// For each args entry `member` -> `key`, collects every distinct
    /// integer comparison against that member in source order and emits
    /// `key` = `op int[,op int...]`. Requires at least one comparison
    /// (a member with both a lower and an upper bound yields two entries);
    /// zero comparisons throws.
    public static Dictionary<string, string> IntComparisons(MethodDeclaration method, FactSpec fact)
    {
        var values = new Dictionary<string, string>();
        foreach (var (memberName, key) in fact.Args)
        {
            var cmps = method.Descendants.OfType<BinaryOperatorExpression>()
                .Where(b => (NodeMentions(b.Left, memberName) && b.Right is PrimitiveExpression { Value: int })
                         || (NodeMentions(b.Right, memberName) && b.Left is PrimitiveExpression { Value: int }))
                .Select(b =>
                {
                    var lit = (b.Right as PrimitiveExpression ?? (PrimitiveExpression)b.Left).Value;
                    return $"{OpName(b.Operator)} {lit}";
                })
                .Distinct().ToList();
            if (cmps.Count == 0)
                throw new InvalidDataException(
                    $"int_comparisons('{memberName}') bound 0 times (need >= 1)");
            values[key] = string.Join(",", cmps);
        }
        return values;
    }

    /// Assert mode. Asserts the method contains EXACTLY ONE statement whose
    /// whitespace-normalized text equals args["statement"]. One statement, not
    /// a body snapshot: stable under the pinned decompiler and immune to edits
    /// in neighboring statements. The spec arg MUST match the DECOMPILER's
    /// rendering (e.g. `Foo.Add (Bar [Baz (0)]);` — note the spaces the
    /// decompiler emits before `(`/`[`), not the original source spelling.
    /// Binding zero or multiple times throws (lands in errors[] -> exit 1).
    public static Dictionary<string, string> StatementShape(MethodDeclaration method, FactSpec fact)
    {
        string wanted = Normalize(fact.Args["statement"]);
        int count = method.Descendants.OfType<ExpressionStatement>()
            .Count(s => Normalize(s.ToString()) == wanted);
        if (count != 1)
            throw new InvalidDataException(
                $"statement_shape bound {count} times (need exactly 1): {fact.Args["statement"]}");
        return new();
    }

    /// Assert mode. Asserts the method contains EXACTLY ONE AST node of
    /// args["kind"] whose whitespace-normalized text equals args["shape"].
    /// Unlike statement_shape, this pins compound nodes such as for/do loops.
    public static Dictionary<string, string> NodeShape(MethodDeclaration method, FactSpec fact)
    {
        string kind = fact.Args["kind"];
        string wanted = Normalize(fact.Args["shape"]);
        var candidates = method.DescendantsAndSelf
            .Where(node => node.GetType().Name == kind)
            .Select(node => Normalize(node.ToString()))
            .ToList();

        int count = candidates.Count(candidate => candidate == wanted);
        if (count != 1)
        {
            string sample = candidates.Count == 0
                ? "no candidates"
                : string.Join(" | ", candidates.Take(5));
            throw new InvalidDataException(
                $"node_shape('{kind}') bound {count} times (need exactly 1): {fact.Args["shape"]}; "
                + $"candidates: {sample}");
        }

        return new();
    }

    /// Assert mode. Asserts the method's set of `==`-compared string literals
    /// EQUALS the expected set in args["strings"] (comma-separated) exactly.
    /// Reuses the StringConstants collector, so it only sees literals that
    /// participate in `==` comparisons; literals that are merely ASSIGNED are
    /// invisible here (pin those with statement_shape instead). A mismatch in
    /// either direction throws (lands in errors[] -> exit 1).
    public static Dictionary<string, string> StringSet(MethodDeclaration method, FactSpec fact)
    {
        var expected = fact.Args["strings"].Split(',').ToHashSet();
        var actual = StringConstants(method, fact)["strings"].Split(',').ToHashSet();
        if (!expected.SetEquals(actual))
            throw new InvalidDataException(
                $"string_set mismatch: expected [{string.Join(",", expected.Order())}], "
                + $"got [{string.Join(",", actual.Order())}]");
        return new();
    }

    private static string Normalize(string s) =>
        string.Join(" ", s.Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries));

    private static bool NodeMentions(AstNode node, string member) =>
        node.DescendantsAndSelf.Any(n =>
            (n is MemberReferenceExpression mre && mre.MemberName == member)
            || (n is IdentifierExpression ide && ide.Identifier == member));

    private static bool MemberNamed(Expression expr, string member) =>
        expr is MemberReferenceExpression { } mre && mre.MemberName == member
        || expr is IdentifierExpression { } ide && ide.Identifier == member;

    private static string? FloatLiteralOf(Expression expr) =>
        expr.DescendantsAndSelf.OfType<PrimitiveExpression>()
            .Where(p => p.Value is float or double)
            .Select(p => Convert.ToString(p.Value, CultureInfo.InvariantCulture)!)
            .FirstOrDefault();

    private static string OpName(BinaryOperatorType op) => op switch
    {
        BinaryOperatorType.GreaterThan => ">",
        BinaryOperatorType.GreaterThanOrEqual => ">=",
        BinaryOperatorType.LessThan => "<",
        BinaryOperatorType.LessThanOrEqual => "<=",
        BinaryOperatorType.Equality => "==",
        BinaryOperatorType.InEquality => "!=",
        _ => op.ToString(),
    };
}
