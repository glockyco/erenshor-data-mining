using AdventureGuide.CompiledGuide;
using AdventureGuide.Graph;

namespace AdventureGuide.Resolution;

/// <summary>
/// Single owner of item-source visibility rules.
///
/// When at least one hostile <see cref="EdgeType.DropsItem"/> source exists,
/// friendly <see cref="EdgeType.DropsItem"/> sources are suppressed. Non-drop
/// sources are always retained.
///
/// Called on the hot resolution path once per item-source lookup. Operates
/// allocation-free over a <see cref="ReadOnlySpan{SourceSiteEntry}"/> input,
/// writing visible sources into a caller-provided list that is cleared
/// first. Hostility is answered via the supplied <see cref="CompiledGuide.CompiledGuide"/>
/// so callers don't need to build delegate closures per lookup.
/// </summary>
public static class ItemSourceVisibilityPolicy
{
	public static void Filter(
		ReadOnlySpan<SourceSiteEntry> sources,
		CompiledGuide.CompiledGuide guide,
		List<SourceSiteEntry> visible
	)
	{
		visible.Clear();
		if (sources.Length == 0)
			return;

		bool anyHostileDrop = false;
		for (int i = 0; i < sources.Length; i++)
		{
			ref readonly var src = ref sources[i];
			if (src.EdgeType == (byte)EdgeType.DropsItem
				&& !guide.GetNode(src.SourceId).IsFriendly)
			{
				anyHostileDrop = true;
				break;
			}
		}

		if (visible.Capacity < sources.Length)
			visible.Capacity = sources.Length;

		for (int i = 0; i < sources.Length; i++)
		{
			ref readonly var src = ref sources[i];
			bool isDrop = src.EdgeType == (byte)EdgeType.DropsItem;
			if (anyHostileDrop && isDrop && guide.GetNode(src.SourceId).IsFriendly)
				continue;
			visible.Add(src);
		}
	}
}
