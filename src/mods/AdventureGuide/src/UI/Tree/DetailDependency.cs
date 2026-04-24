namespace AdventureGuide.UI.Tree;

internal enum DetailDependencySemantics : byte
{
    AnyOf,
    AllOf,
}

internal readonly record struct DetailDependency(
    DetailDependencySemantics Semantics,
    DetailGoal[] Children,
    byte UnlockGroup
);
