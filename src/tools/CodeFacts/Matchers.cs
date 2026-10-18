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
                    "statement_order" => Matchers.StatementOrder(scope, fact),
                    "string_set" => Matchers.StringSet(scope, fact),
                    "node_shape" => Matchers.NodeShape(scope, fact),
                    "foreach_source" => Matchers.ForeachSource(scope, fact),
                    "int_expression" => Matchers.IntExpression(scope, fact),
                    "branch_shape" => Matchers.BranchShape(scope, fact),
                    "nested_branch_split" => Matchers.NestedBranchSplit(scope, fact),
                    "switch_item_grant" => Matchers.SwitchItemGrant(scope, fact),
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

    /// Extract a literal assignment, argument, closed switch, or equality literals.
    public static Dictionary<string, string> StringConstants(EntityDeclaration scope, FactSpec fact)
    {
        if (fact.Args.TryGetValue("switch", out string? governingExpression))
        {
            string expression = Normalize(governingExpression);
            var switches = scope
                .Descendants.OfType<SwitchStatement>()
                .Where(node => Normalize(node.Expression.ToString()) == expression)
                .ToList();
            if (switches.Count != 1)
                throw new InvalidDataException(
                    $"string_constants switch '{governingExpression}' bound {switches.Count} times (need exactly 1)"
                );
            var labels = new List<string>();
            foreach (
                var label in switches[0].SwitchSections.SelectMany(section => section.CaseLabels)
            )
            {
                if (label.Expression is null)
                    throw new InvalidDataException(
                        $"string_constants switch '{governingExpression}' has a default label, not a closed string set"
                    );
                if (label.Expression is not PrimitiveExpression { Value: string value })
                    throw new InvalidDataException(
                        $"string_constants switch '{governingExpression}' has a non-string literal label"
                    );
                labels.Add(value);
            }
            return new() { [fact.Keys?.SingleOrDefault() ?? "strings"] = string.Join(",", labels) };
        }
        if (fact.Args.TryGetValue("assignment", out string? member))
        {
            var assignments = scope
                .Descendants.OfType<AssignmentExpression>()
                .Where(node => Normalize(node.Left!.ToString()) == Normalize(member))
                .ToList();
            if (
                assignments.Count != 1
                || assignments[0].Operator != AssignmentOperatorType.Assign
                || assignments[0].Right is not PrimitiveExpression { Value: string value }
            )
                throw new InvalidDataException(
                    $"string_constants assignment '{member}' needs exactly one string literal assignment"
                );
            return new() { ["string"] = value };
        }
        if (fact.Args.ContainsKey("invocation") || fact.Args.ContainsKey("creation"))
        {
            var arguments = fact.Args.TryGetValue("invocation", out string? invocation)
                ? scope
                    .Descendants.OfType<InvocationExpression>()
                    .Where(node => Normalize(node.Target.ToString()) == Normalize(invocation))
                    .Select(node => node.Arguments.ToArray())
                    .ToList()
                : scope
                    .Descendants.OfType<ObjectCreateExpression>()
                    .Where(node =>
                        Normalize(node.Type.ToString()) == Normalize(fact.Args["creation"])
                    )
                    .Select(node => node.Arguments.ToArray())
                    .ToList();
            if (
                !fact.Args.TryGetValue("argument", out string? position)
                || !int.TryParse(
                    position,
                    NumberStyles.None,
                    CultureInfo.InvariantCulture,
                    out int index
                )
                || arguments.Count != 1
                || index >= arguments[0].Length
                || arguments[0][index] is not PrimitiveExpression { Value: string value }
            )
                throw new InvalidDataException(
                    "string_constants argument needs exactly one matching call with a string literal at the requested zero-based position"
                );
            return new() { ["string"] = value };
        }
        AstNode search = scope;
        if (fact.Args.TryGetValue("guard_assignment", out string? guard))
        {
            var guards = scope
                .Descendants.OfType<IfElseStatement>()
                .Where(node =>
                    node.TrueStatement.Descendants.OfType<AssignmentExpression>()
                        .Any(assignment =>
                            Normalize(assignment.Left!.ToString()) == guard
                            && assignment.Right is PrimitiveExpression { Value: true }
                        )
                )
                .ToList();
            if (guards.Count != 1)
                throw new InvalidDataException(
                    $"string_constants guard bound {guards.Count} times (need exactly 1)"
                );
            search = guards[0].Condition;
        }
        var strings = search
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

    /// Pin one selected branch without snapshotting its unrelated sibling.
    public static Dictionary<string, string> BranchShape(EntityDeclaration scope, FactSpec fact)
    {
        var matches = scope
            .Descendants.OfType<IfElseStatement>()
            .Where(node =>
                Normalize(node.Condition.ToString()) == Normalize(fact.Args["condition"])
            )
            .ToList();
        if (matches.Count != 1)
            throw new InvalidDataException(
                $"branch_shape bound {matches.Count} times (need exactly 1)"
            );
        AstNode? branch =
            fact.Args["branch"] == "false" ? matches[0].FalseStatement : matches[0].TrueStatement;
        if (branch is null || Normalize(branch.ToString()) != Normalize(fact.Args["shape"]))
            throw new InvalidDataException($"branch_shape mismatch: {branch}");
        return new();
    }

    /// Extract the integer right operand of one binary expression, matching its
    /// left operand and operator exactly. Unlike int_comparisons this preserves
    /// the distinction between a cap and a relative level-window offset.
    public static Dictionary<string, string> IntExpression(EntityDeclaration scope, FactSpec fact)
    {
        AstNode search = scope;
        if (fact.Args.TryGetValue("within_draw", out string? identifier))
        {
            var draws = scope
                .Descendants.OfType<DoWhileStatement>()
                .Where(node => NodeMentions(node, identifier))
                .ToList();
            if (draws.Count != 1)
                throw new InvalidDataException(
                    $"int_expression draw bound {draws.Count} times (need exactly 1)"
                );
            search = draws[0];
        }
        var matches = search
            .Descendants.OfType<BinaryOperatorExpression>()
            .Where(node =>
                Normalize(node.Left!.ToString()) == Normalize(fact.Args["left"])
                && OpName(node.Operator) == fact.Args["operator"]
                && node.Right is PrimitiveExpression { Value: int }
            )
            .Where(node =>
                !fact.Args.ContainsKey("top_level")
                || (
                    scope is MethodDeclaration method
                    && node.Parent is IfElseStatement guard
                    && guard.Parent == method.Body
                )
            )
            .Select(node => ((PrimitiveExpression)node.Right!).Value.ToString()!)
            .Distinct()
            .ToList();
        if (matches.Count != 1)
            throw new InvalidDataException(
                $"int_expression bound {matches.Count} times (need exactly 1)"
            );
        return new() { ["value"] = matches[0] };
    }

    /// <summary>Assert that exactly one foreach loop iterates the named source.</summary>
    public static Dictionary<string, string> ForeachSource(EntityDeclaration scope, FactSpec fact)
    {
        var source = Normalize(fact.Args["source"]);
        var count = scope
            .Descendants.OfType<ForeachStatement>()
            .Count(loop => Normalize(loop.InExpression.ToString()) == source);
        if (count != 1)
            throw new InvalidDataException(
                $"foreach_source('{source}') bound {count} times (need exactly 1)"
            );
        return new();
    }

    /// Extract one direct or weighted-pool item grant from a native spell switch case.
    /// Logging is not gameplay control flow. All other case statements are constrained.
    public static Dictionary<string, string> SwitchItemGrant(EntityDeclaration scope, FactSpec fact)
    {
        string spell = fact.Args["case"];
        var sections = scope
            .Descendants.OfType<SwitchSection>()
            .Where(section =>
                section.CaseLabels.Any(label =>
                    label.Expression is PrimitiveExpression { Value: string value }
                    && value == spell
                )
            )
            .ToList();
        if (sections.Count != 1 || sections[0].CaseLabels.Count != 1)
            throw new InvalidDataException(
                $"switch_item_grant('{spell}') needs exactly one unshared case"
            );

        var section = sections[0];
        var statements = section.Statements.ToList();
        if (statements.Count == 1 && statements[0] is BlockStatement block)
            statements = block.Statements.ToList();
        statements.RemoveAll(statement => IsSocialLog(statement));
        bool poolMode = fact.Args.TryGetValue("pool", out string? pool);
        int expectedCount = poolMode ? 3 : 2;
        if (
            statements.Count != expectedCount
            || statements[^1] is not BreakStatement
            || statements[^2] is not IfElseStatement fallback
            || fallback.FalseStatement is not null
            || fallback.Condition
                is not UnaryOperatorExpression
                {
                    Operator: UnaryOperatorType.Not,
                    Expression: InvocationExpression add
                }
            || Normalize(add.Target.ToString()) != "GameData.PlayerInv.AddItemToInv"
            || add.Arguments.Count != 1
        )
            throw new InvalidDataException(
                $"switch_item_grant('{spell}') has unexpected grant control flow"
            );

        var fallbackStatements = fallback.TrueStatement is BlockStatement body
            ? body.Statements.ToList()
            : new List<Statement> { fallback.TrueStatement };
        if (
            fallbackStatements.Count != 1
            || fallbackStatements[0]
                is not ExpressionStatement { Expression: InvocationExpression force }
            || Normalize(force.Target.ToString()) != "GameData.PlayerInv.ForceItemToInv"
            || force.Arguments.Count != 1
            || Normalize(force.Arguments[0].ToString()) != Normalize(add.Arguments[0].ToString())
        )
            throw new InvalidDataException(
                $"switch_item_grant('{spell}') needs the same-item failure fallback"
            );

        int grantCalls = section
            .Descendants.OfType<InvocationExpression>()
            .Count(call =>
                call.Target
                    is MemberReferenceExpression { MemberName: "AddItemToInv" or "ForceItemToInv" }
            );
        if (grantCalls != 2)
            throw new InvalidDataException(
                $"switch_item_grant('{spell}') has additional item grants"
            );

        var values = new Dictionary<string, string> { ["spell_name"] = spell, ["quantity"] = "1" };
        if (poolMode)
        {
            if (
                statements[0] is not VariableDeclarationStatement declaration
                || Normalize(declaration.Type.ToString()) != "Item"
                || declaration.Variables.Count != 1
            )
                throw new InvalidDataException(
                    $"switch_item_grant('{spell}') needs one selected Item variable"
                );
            var variable = declaration.Variables[0];
            if (
                variable.Initializer is not IndexerExpression selected
                || selected.Target is null
                || Normalize(selected.Target.ToString()) != Normalize(pool!)
                || selected.Arguments.Count != 1
                || selected.Arguments[0] is not InvocationExpression range
                || Normalize(range.Target.ToString()) != "Random.Range"
                || range.Arguments.Count != 2
                || range.Arguments[0] is not PrimitiveExpression { Value: int minimum }
                || minimum != 0
                || Normalize(range.Arguments[1].ToString()) != Normalize(pool! + ".Count")
                || add.Arguments[0] is not IdentifierExpression item
                || item.Identifier != variable.Name
            )
                throw new InvalidDataException(
                    $"switch_item_grant('{spell}') must grant one full-pool uniform draw"
                );
            values["pool"] = pool!;
            values["rolls"] = "1";
        }
        else
        {
            if (
                add.Arguments[0] is not InvocationExpression lookup
                || Normalize(lookup.Target.ToString()) != "GameData.ItemDB.GetItemByID"
                || lookup.Arguments.Count != 1
                || lookup.Arguments[0] is not PrimitiveExpression { Value: string itemId }
            )
                throw new InvalidDataException(
                    $"switch_item_grant('{spell}') needs one literal item ID lookup"
                );
            values["created_item_id"] = itemId;
        }
        return values;
    }

    private static bool IsSocialLog(AstNode node)
    {
        if (
            node is not ExpressionStatement { Expression: InvocationExpression call }
            || Normalize(call.Target.ToString()) != "UpdateSocialLog.LogAdd"
        )
            return false;
        if (
            call
                .Arguments.SelectMany(argument => argument.DescendantsAndSelf)
                .Any(part =>
                {
                    if (
                        part is AssignmentExpression
                        || part
                            is UnaryOperatorExpression
                            {
                                Operator: UnaryOperatorType.Increment
                                    or UnaryOperatorType.Decrement
                                    or UnaryOperatorType.PostIncrement
                                    or UnaryOperatorType.PostDecrement
                            }
                    )
                        return true;
                    if (
                        part
                        is not InvocationExpression { Target: MemberReferenceExpression target }
                    )
                        return false;
                    if (target.MemberName is "AddItemToInv" or "ForceItemToInv")
                        return true;
                    string receiver = Normalize(target.Target.ToString());
                    return receiver == "GameData.PlayerInv"
                        || receiver.StartsWith("GameData.PlayerInv.", StringComparison.Ordinal);
                })
        )
            throw new InvalidDataException(
                "A social-log argument contains inventory or mutation effects"
            );
        return true;
    }

    private static string Shape(AstNode node, bool ignoreSocialLogs)
    {
        if (!ignoreSocialLogs)
            return Normalize(node.ToString());
        var copy = node.Clone();
        foreach (
            var statement in copy
                .Descendants.OfType<ExpressionStatement>()
                .Where(IsSocialLog)
                .ToList()
        )
            statement.Remove();
        return Normalize(copy.ToString());
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

    /// Assert mode. Pins two unique statements directly in a method body.
    /// Matching nested statements also count, so a conditional duplicate cannot
    /// hide beside an unconditional call.
    public static Dictionary<string, string> StatementOrder(EntityDeclaration scope, FactSpec fact)
    {
        if (scope is not MethodDeclaration { Body: { } body })
            throw new InvalidDataException("statement_order requires a method body");

        string before = Normalize(fact.Args["before"]);
        string after = Normalize(fact.Args["after"]);
        var statements = body.Statements.ToList();
        int FindIndex(string wanted)
        {
            var matches = body
                .Descendants.OfType<Statement>()
                .Where(statement => Normalize(statement.ToString()) == wanted)
                .ToList();
            if (matches.Count != 1 || matches[0].Parent != body)
                throw new InvalidDataException(
                    $"statement_order needs exactly one direct statement and no nested duplicates: {wanted}"
                );
            if (matches[0] is ExpressionStatement expression)
            {
                string expressionShape = Normalize(expression.Expression.ToString());
                int expressions = body
                    .Descendants.OfType<Expression>()
                    .Count(node => Normalize(node.ToString()) == expressionShape);
                if (expressions != 1)
                    throw new InvalidDataException(
                        $"statement_order found a nested duplicate expression: {wanted}"
                    );
            }
            return statements.IndexOf(matches[0]);
        }

        int beforeIndex = FindIndex(before);
        int afterIndex = FindIndex(after);
        if (beforeIndex >= afterIndex)
            throw new InvalidDataException("statement_order requires before to precede after");
        return new();
    }

    /// Assert mode. Asserts exactly args["count"] AST nodes (default 1) of
    /// args["kind"] have the whitespace-normalized args["shape"].
    /// Optional ignore_social_logs excludes standalone social-log calls, not control flow.
    public static Dictionary<string, string> NodeShape(EntityDeclaration scope, FactSpec fact)
    {
        string kind = fact.Args["kind"];
        string wanted = Normalize(fact.Args["shape"]);
        bool ignoreSocialLogs =
            fact.Args.TryGetValue("ignore_social_logs", out string? ignore) && bool.Parse(ignore);
        int expected = fact.Args.TryGetValue("count", out string? expectedCount)
            ? int.Parse(expectedCount, CultureInfo.InvariantCulture)
            : 1;
        var candidates = scope
            .DescendantsAndSelf.Where(node => node.GetType().Name == kind)
            .Select(node => Shape(node, ignoreSocialLogs))
            .ToList();

        int count = candidates.Count(candidate => candidate == wanted);
        if (count != expected)
        {
            string sample =
                candidates.Count == 0 ? "no candidates" : string.Join(" | ", candidates.Take(5));
            throw new InvalidDataException(
                $"node_shape('{kind}') bound {count} times (need exactly {expected}): {fact.Args["shape"]}; "
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
            BinaryOperatorType.Add => "+",
            BinaryOperatorType.Subtract => "-",
            _ => op.ToString(),
        };
}
