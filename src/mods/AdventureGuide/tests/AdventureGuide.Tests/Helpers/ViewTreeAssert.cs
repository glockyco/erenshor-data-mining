using AdventureGuide.Views;
using Xunit;

namespace AdventureGuide.Tests.Helpers;

/// <summary>
/// Assertion helpers for navigating and verifying <see cref="ViewNode"/> trees
/// produced by <see cref="QuestViewBuilder"/>.
/// </summary>
public static class ViewTreeAssert
{
    /// <summary>Finds a descendant EntityViewNode by node key; fails if absent.</summary>
    public static EntityViewNode FindChild(ViewNode root, string nodeKey)
    {
        var found = FindChildRecursive(root, nodeKey);
        Assert.NotNull(found);
        return found!;
    }

    /// <summary>Asserts no descendant EntityViewNode with the given key exists.</summary>
    public static void HasNoChild(ViewNode root, string nodeKey)
    {
        var found = FindChildRecursive(root, nodeKey);
        Assert.Null(found);
    }

    /// <summary>Asserts the descendant with the given key is a cycle back-reference.</summary>
    public static void ChildIsCycleRef(ViewNode root, string nodeKey)
    {
        var found = FindChildRecursive(root, nodeKey);
        Assert.NotNull(found);
        Assert.True(found!.IsCycleRef, $"Expected {nodeKey} to be a cycle ref");
    }

    /// <summary>
    /// Asserts <paramref name="nodeKey"/> has an unlock dependency subtree
    /// containing <paramref name="dependencyKey"/>.
    /// </summary>
    public static void HasUnlockDependency(ViewNode root, string nodeKey, string dependencyKey)
    {
        var node = FindChild(root, nodeKey);
        Assert.NotNull(node.UnlockDependency);
        var dep = FindChildRecursive(node.UnlockDependency!, dependencyKey)
            ?? (node.UnlockDependency is EntityViewNode en && en.NodeKey == dependencyKey ? en : null);
        Assert.NotNull(dep);
    }

    /// <summary>Asserts the frontier list contains a node with the given key.</summary>
    public static void FrontierContains(IReadOnlyList<EntityViewNode> frontier, string nodeKey)
    {
        Assert.Contains(frontier, n => n.NodeKey == nodeKey);
    }

    /// <summary>Asserts the frontier list does NOT contain a node with the given key.</summary>
    public static void FrontierDoesNotContain(IReadOnlyList<EntityViewNode> frontier, string nodeKey)
    {
        Assert.DoesNotContain(frontier, n => n.NodeKey == nodeKey);
    }

    private static EntityViewNode? FindChildRecursive(ViewNode node, string nodeKey)
    {
        if (node is EntityViewNode en && en.NodeKey == nodeKey)
            return en;

        for (int i = 0; i < node.Children.Count; i++)
        {
            var found = FindChildRecursive(node.Children[i], nodeKey);
            if (found != null)
                return found;
        }

        if (node is EntityViewNode entity && entity.UnlockDependency != null)
        {
            var found = FindChildRecursive(entity.UnlockDependency, nodeKey);
            if (found != null)
                return found;
        }

        return null;
    }
}
