using AdventureGuide.Data;

namespace AdventureGuide.UI;

/// <summary>Text for the collapsed tail of a step's item source list.</summary>
internal static class SourceListText
{
    /// <summary>
    /// "N more sources (Lv a-b)" for the sources from <paramref name="start"/>
    /// on. The range spans only sources with a level, which sort first; with
    /// no level among them, the label shows no range.
    /// </summary>
    public static string MoreSources(IReadOnlyList<ItemSource> sources, int start)
    {
        int? min = null;
        int? max = null;
        for (int i = start; i < sources.Count; i++)
        {
            if (sources[i].Level is not int level)
                continue;
            if (min == null || level < min)
                min = level;
            if (max == null || level > max)
                max = level;
        }

        int remaining = sources.Count - start;
        if (min == null)
            return $"{remaining} more sources";
        return min == max
            ? $"{remaining} more sources (Lv {min})"
            : $"{remaining} more sources (Lv {min}-{max})";
    }
}
