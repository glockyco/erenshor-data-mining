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
        var resolver = new UniversalAssemblyResolver(
            assemblyPath,
            throwOnError: false,
            targetFramework: null
        );
        var decompiler = new CSharpDecompiler(assemblyPath, resolver, new DecompilerSettings());
        string? activeVariant = string.IsNullOrWhiteSpace(variant) ? null : variant;

        foreach (var fact in specs.Facts)
        {
            if (!AppliesToVariant(fact, activeVariant))
                continue;
            try
            {
                var scope = FindMember(decompiler, fact);
                var values = fact.Matcher switch
                {
                    "guarded_member_roll" => Matchers.GuardedMemberRoll(scope, fact),
                    "string_constants" => Matchers.StringConstants(scope, fact),
                    "int_comparisons" => Matchers.IntComparisons(scope, fact),
                    "statement_shape" => Matchers.StatementShape(scope, fact),
                    "string_set" => Matchers.StringSet(scope, fact),
                    "node_shape" => Matchers.NodeShape(scope, fact),
                    "nested_branch_split" => Matchers.NestedBranchSplit(scope, fact),
                    _ => throw new InvalidDataException($"unknown matcher '{fact.Matcher}'"),
                };
                result.Facts.Add(
                    fact.Mode == "assert"
                        ? new FactResult(fact.Id, fact.Mode, null, AssertOk: true)
                        : new FactResult(fact.Id, fact.Mode, values, null)
                );
            }
            catch (Exception ex)
            {
                result.Errors.Add($"{fact.Id}: {ex.Message}");
            }
        }
        return result;
    }

    /// Binds the member that a fact names: the one method named `method`, or
    /// the one field declaration that declares the variable named `field`.
    /// `parameters` picks one overload of a method by the decompiler's
    /// rendering of its parameter types, for example `["Spell", "bool", "int"]`.
    /// The decompiler renders an initializer that the compiler moved into the
    /// constructor back on its field, so a field scope pins the initial value.
    private static EntityDeclaration FindMember(CSharpDecompiler decompiler, FactSpec fact)
    {
        if ((fact.Method is null) == (fact.Field is null))
            throw new InvalidDataException("a fact names exactly one of method and field");
        if (fact.Parameters is not null && fact.Method is null)
            throw new InvalidDataException("parameters select a method overload, not a field");
        SyntaxTree tree = decompiler.DecompileType(new FullTypeName(fact.Type));
        List<EntityDeclaration> matches = fact.Method is not null
            ? tree
                .Descendants.OfType<MethodDeclaration>()
                .Where(m => m.Name == fact.Method && HasParameters(m, fact.Parameters))
                .Cast<EntityDeclaration>()
                .ToList()
            : tree
                .Descendants.OfType<FieldDeclaration>()
                .Where(f => f.Variables.Any(v => v.Name == fact.Field))
                .Cast<EntityDeclaration>()
                .ToList();
        if (matches.Count != 1)
        {
            string member = fact.Method is not null
                ? $"method {fact.Type}::{fact.Method}"
                    + (fact.Parameters is null ? "" : $"({string.Join(", ", fact.Parameters)})")
                : $"field {fact.Type}::{fact.Field}";
            throw new InvalidDataException(
                $"{member} bound {matches.Count} times (need exactly 1)"
            );
        }
        return matches[0];
    }

    private static bool HasParameters(MethodDeclaration method, List<string>? parameters) =>
        parameters is null
        || method.Parameters.Select(p => p.Type!.ToString()).SequenceEqual(parameters);

    private static bool AppliesToVariant(FactSpec fact, string? activeVariant)
    {
        if (fact.Variants is null || fact.Variants.Count == 0)
            return true;
        if (activeVariant is null)
            return true;
        return fact.Variants.Contains(activeVariant);
    }
}

internal static class Matchers
{
    /// Binds the unique `if` whose then-branch references args["member"] in an
    /// Add(...) call and whose condition compares a float literal (optionally
    /// `* expr`). Emits rate (literal as invariant string) and min_level
    /// (from a `Level > N` conjunct, else "0").
    public static Dictionary<string, string> GuardedMemberRoll(
        EntityDeclaration scope,
        FactSpec fact
    )
    {
        string member = fact.Args["member"];
        var hits = new List<(string Rate, string MinLevel)>();

        foreach (var ifs in scope.Descendants.OfType<IfElseStatement>())
        {
            bool addsMember = ifs
                .TrueStatement.Descendants.OfType<InvocationExpression>()
                .Any(inv =>
                    inv.Target is MemberReferenceExpression { MemberName: "Add" }
                    && inv.Arguments.Count == 1
                    && NodeMentions(inv.Arguments[0], member)
                );
            if (!addsMember)
                continue;

            string? rate = ifs
                .Condition.DescendantsAndSelf.OfType<BinaryOperatorExpression>()
                .Where(b => b.Operator == BinaryOperatorType.LessThan)
                .Select(b => FloatLiteralOf(b.Right) ?? FloatLiteralOf(b.Left))
                .FirstOrDefault(v => v is not null);
            if (rate is null)
                continue;

            string minLevel =
                ifs.Condition.DescendantsAndSelf.OfType<BinaryOperatorExpression>()
                    .Where(b =>
                        b.Operator == BinaryOperatorType.GreaterThan
                        && MemberNamed(b.Left, "Level")
                        && b.Right is PrimitiveExpression { Value: int }
                    )
                    .Select(b => ((PrimitiveExpression)b.Right!).Value.ToString()!)
                    .FirstOrDefault()
                ?? "0";

            hits.Add((rate, minLevel));
        }

        if (hits.Count != 1)
            throw new InvalidDataException(
                $"guarded_member_roll('{member}') bound {hits.Count} times (need exactly 1)"
            );
        return new() { ["rate"] = hits[0].Rate, ["min_level"] = hits[0].MinLevel };
    }

    /// Binds the unique `if (Random.Range (a, b) > c)` statement whose then
    /// branch adds args["then"] and whose else branch adds args["else"]. Emits
    /// range_min (a), range_max (b), and cutoff (c) as integers. The binding is
    /// scoped to that one statement, so other `Random.Range` comparisons in the
    /// same member cannot bind.
    public static Dictionary<string, string> NestedBranchSplit(
        EntityDeclaration scope,
        FactSpec fact
    )
    {
        string thenMember = fact.Args["then"];
        string elseMember = fact.Args["else"];
        var hits = new List<(int Min, int Max, int Cutoff)>();

        foreach (var ifs in scope.Descendants.OfType<IfElseStatement>())
        {
            if (
                ifs.Condition
                    is not BinaryOperatorExpression
                    {
                        Operator: BinaryOperatorType.GreaterThan,
                        Left: InvocationExpression
                        {
                            Target: MemberReferenceExpression { MemberName: "Range" },
                        } range,
                        Right: PrimitiveExpression { Value: int cutoff },
                    }
                || range.Arguments.Count != 2
                || range.Arguments.ElementAt(0) is not PrimitiveExpression { Value: int min }
                || range.Arguments.ElementAt(1) is not PrimitiveExpression { Value: int max }
            )
                continue;
            if (
                !AddsMember(ifs.TrueStatement, thenMember)
                || !AddsMember(ifs.FalseStatement, elseMember)
            )
                continue;
            hits.Add((min, max, cutoff));
        }

        if (hits.Count != 1)
            throw new InvalidDataException(
                $"nested_branch_split('{thenMember}'/'{elseMember}') bound {hits.Count} times (need exactly 1)"
            );
        return new()
        {
            ["range_min"] = hits[0].Min.ToString(CultureInfo.InvariantCulture),
            ["range_max"] = hits[0].Max.ToString(CultureInfo.InvariantCulture),
            ["cutoff"] = hits[0].Cutoff.ToString(CultureInfo.InvariantCulture),
        };
    }

    private static bool AddsMember(AstNode? branch, string member) =>
        branch is not null
        && branch
            .Descendants.OfType<InvocationExpression>()
            .Any(inv =>
                inv.Target is MemberReferenceExpression { MemberName: "Add" }
                && inv.Arguments.Count == 1
                && NodeMentions(inv.Arguments[0], member)
            );

    /// All distinct string literals used in `==` comparisons in the member,
    /// in source order, joined with ','.
    public static Dictionary<string, string> StringConstants(EntityDeclaration scope, FactSpec fact)
    {
        var strings = scope
            .Descendants.OfType<BinaryOperatorExpression>()
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
    public static Dictionary<string, string> IntComparisons(EntityDeclaration scope, FactSpec fact)
    {
        var values = new Dictionary<string, string>();
        foreach (var (memberName, key) in fact.Args)
        {
            var cmps = scope
                .Descendants.OfType<BinaryOperatorExpression>()
                .Where(b =>
                    (
                        NodeMentions(b.Left, memberName)
                        && b.Right is PrimitiveExpression { Value: int }
                    )
                    || (
                        NodeMentions(b.Right, memberName)
                        && b.Left is PrimitiveExpression { Value: int }
                    )
                )
                .Select(b =>
                {
                    var lit = (
                        b.Right as PrimitiveExpression ?? (PrimitiveExpression)b.Left!
                    ).Value;
                    return $"{OpName(b.Operator)} {lit}";
                })
                .Distinct()
                .ToList();
            if (cmps.Count == 0)
                throw new InvalidDataException(
                    $"int_comparisons('{memberName}') bound 0 times (need >= 1)"
                );
            values[key] = string.Join(",", cmps);
        }
        return values;
    }

    /// Assert mode. Asserts the member contains exactly args["count"] statements
    /// (default 1) whose whitespace-normalized text equals args["statement"].
    /// Statements, not a body snapshot: stable under the pinned decompiler and
    /// immune to edits in neighboring statements. A count pins a call that
    /// several branches make, such as the recalculation after each way a status
    /// effect can land. The spec arg MUST match the DECOMPILER's rendering
    /// (e.g. `Foo.Add (Bar [Baz (0)]);` — note the spaces the decompiler emits
    /// before `(`/`[`), not the original source spelling. Any other number of
    /// bindings throws (lands in errors[] -> exit 1).
    public static Dictionary<string, string> StatementShape(EntityDeclaration scope, FactSpec fact)
    {
        string wanted = Normalize(fact.Args["statement"]);
        int expected = fact.Args.TryGetValue("count", out string? count)
            ? int.Parse(count, CultureInfo.InvariantCulture)
            : 1;
        int bound = scope
            .Descendants.OfType<ExpressionStatement>()
            .Count(s => Normalize(s.ToString()) == wanted);
        if (bound != expected)
            throw new InvalidDataException(
                $"statement_shape bound {bound} times (need exactly {expected}): {fact.Args["statement"]}"
            );
        return new();
    }

    /// Assert mode. Asserts the member contains EXACTLY ONE AST node of
    /// args["kind"] whose whitespace-normalized text equals args["shape"].
    /// Unlike statement_shape, this pins compound nodes such as for/do loops,
    /// and in a field scope the initializer (kind `VariableInitializer`).
    public static Dictionary<string, string> NodeShape(EntityDeclaration scope, FactSpec fact)
    {
        string kind = fact.Args["kind"];
        string wanted = Normalize(fact.Args["shape"]);
        var candidates = scope
            .DescendantsAndSelf.Where(node => node.GetType().Name == kind)
            .Select(node => Normalize(node.ToString()))
            .ToList();

        int count = candidates.Count(candidate => candidate == wanted);
        if (count != 1)
        {
            string sample =
                candidates.Count == 0 ? "no candidates" : string.Join(" | ", candidates.Take(5));
            throw new InvalidDataException(
                $"node_shape('{kind}') bound {count} times (need exactly 1): {fact.Args["shape"]}; "
                    + $"candidates: {sample}"
            );
        }

        return new();
    }

    /// Assert mode. Asserts the member's set of `==`-compared string literals
    /// EQUALS the expected set in args["strings"] (comma-separated) exactly.
    /// Reuses the StringConstants collector, so it only sees literals that
    /// participate in `==` comparisons; literals that are merely ASSIGNED are
    /// invisible here (pin those with statement_shape instead). A mismatch in
    /// either direction throws (lands in errors[] -> exit 1).
    public static Dictionary<string, string> StringSet(EntityDeclaration scope, FactSpec fact)
    {
        var expected = fact.Args["strings"].Split(',').ToHashSet();
        var actual = StringConstants(scope, fact)["strings"].Split(',').ToHashSet();
        if (!expected.SetEquals(actual))
            throw new InvalidDataException(
                $"string_set mismatch: expected [{string.Join(",", expected.Order())}], "
                    + $"got [{string.Join(",", actual.Order())}]"
            );
        return new();
    }

    private static string Normalize(string s) =>
        string.Join(" ", s.Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries));

    private static bool NodeMentions(AstNode? node, string member) =>
        node is not null
        && node.DescendantsAndSelf.Any(n =>
            (n is MemberReferenceExpression mre && mre.MemberName == member)
            || (n is IdentifierExpression ide && ide.Identifier == member)
        );

    private static bool MemberNamed(Expression? expr, string member) =>
        expr is MemberReferenceExpression { } mre && mre.MemberName == member
        || expr is IdentifierExpression { } ide && ide.Identifier == member;

    private static string? FloatLiteralOf(Expression? expr) =>
        expr
            ?.DescendantsAndSelf.OfType<PrimitiveExpression>()
            .Where(p => p.Value is float or double)
            .Select(p => Convert.ToString(p.Value, CultureInfo.InvariantCulture)!)
            .FirstOrDefault();

    private static string OpName(BinaryOperatorType op) =>
        op switch
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
