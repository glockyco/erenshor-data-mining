using System.Globalization;
using ICSharpCode.Decompiler;
using ICSharpCode.Decompiler.CSharp;
using ICSharpCode.Decompiler.CSharp.Syntax;
using ICSharpCode.Decompiler.TypeSystem;

namespace CodeFacts;

internal static class Runner
{
    public static RunResult Run(string assemblyPath, string specsPath)
    {
        var specs = RunResult.LoadSpecs(specsPath);
        var result = new RunResult { Assembly = assemblyPath };
        var decompiler = new CSharpDecompiler(assemblyPath, new DecompilerSettings());

        foreach (var fact in specs.Facts)
        {
            try
            {
                var method = FindMethod(decompiler, fact);
                var values = fact.Matcher switch
                {
                    "guarded_member_roll" => Matchers.GuardedMemberRoll(method, fact),
                    "string_constants" => Matchers.StringConstants(method, fact),
                    "int_comparisons" => Matchers.IntComparisons(method, fact),
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

    /// For each args entry "<MemberName>" -> "<key>", collects every distinct
    /// integer comparison against that member in source order and emits
    /// "<key>" = "<op> <int>[,<op> <int>...]". Requires at least one comparison
    /// (a member with two legitimate bounds, e.g. `> 0` and `< 40`, yields both);
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
