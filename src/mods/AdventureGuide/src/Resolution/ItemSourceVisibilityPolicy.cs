using AdventureGuide.Graph;

namespace AdventureGuide.Resolution;

/// <summary>
/// Single owner of item-source visibility rules.
///
/// When at least one hostile <see cref="EdgeType.DropsItem"/> source exists,
/// friendly <see cref="EdgeType.DropsItem"/> sources are suppressed. Non-drop
/// sources are always retained.
/// </summary>
public static class ItemSourceVisibilityPolicy
{
    public static List<TSource> Filter<TSource>(
        IReadOnlyList<TSource> sources,
        Func<TSource, EdgeType> getEdgeType,
        Func<TSource, bool> isHostile
    )
    {
        bool anyHostileDrop = false;
        for (int i = 0; i < sources.Count; i++)
        {
            if (getEdgeType(sources[i]) == EdgeType.DropsItem && isHostile(sources[i]))
            {
                anyHostileDrop = true;
                break;
            }
        }

        var visible = new List<TSource>(sources.Count);
        for (int i = 0; i < sources.Count; i++)
        {
            var source = sources[i];
            if (
                anyHostileDrop
                && getEdgeType(source) == EdgeType.DropsItem
                && !isHostile(source)
            )
            {
                continue;
            }

            visible.Add(source);
        }

        return visible;
    }
}
