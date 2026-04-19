using AdventureGuide.Graph;
using AdventureGuide.State;
using CompiledGuideModel = AdventureGuide.CompiledGuide.CompiledGuide;

namespace AdventureGuide.Position;

/// <summary>
/// Zone connectivity graph with shortest-path BFS routing.
///
/// Built from zone line nodes and their unlock state. Provides
/// cross-zone routing: given a current scene and a target scene, returns
/// the next-hop zone line to navigate toward.
/// </summary>
public sealed class ZoneRouter
{
	/// <summary>Result of a route query.</summary>
	public sealed class Route
	{
		/// <summary>Zone key of the first hop (the destination zone to head toward).</summary>
		public string NextHopZoneKey { get; }

		/// <summary>Scene name of the zone line in current zone to navigate to.</summary>
		public string ZoneLineScene { get; }

		/// <summary>World position of the zone line to navigate to.</summary>
		public float X { get; }
		public float Y { get; }
		public float Z { get; }

		/// <summary>Whether the first hop is through a locked zone line.</summary>
		public bool IsLocked { get; }

		/// <summary>Full path as scene names (including start and end).</summary>
		public IReadOnlyList<string> Path { get; }

		public Route(
			string nextHopZoneKey,
			string zoneLineScene,
			float x,
			float y,
			float z,
			bool isLocked,
			IReadOnlyList<string> path
		)
		{
			NextHopZoneKey = nextHopZoneKey;
			ZoneLineScene = zoneLineScene;
			X = x;
			Y = y;
			Z = z;
			IsLocked = isLocked;
			Path = path;
		}
	}

	/// <summary>First locked hop on a route that otherwise exists.</summary>
	public sealed class LockedHop
	{
		public string ZoneLineKey { get; }
		public string FromScene { get; }
		public string ToScene { get; }
		public float X { get; }
		public float Y { get; }
		public float Z { get; }

		public LockedHop(
			string zoneLineKey,
			string fromScene,
			string toScene,
			float x,
			float y,
			float z
		)
		{
			ZoneLineKey = zoneLineKey;
			FromScene = fromScene;
			ToScene = toScene;
			X = x;
			Y = y;
			Z = z;
		}
	}

	private readonly CompiledGuideModel _guide;
	private readonly UnlockEvaluator _unlocks;
	// scene -> list of (destScene, zoneLineNodeKey, accessible)
	private readonly Dictionary<string, List<ZoneEdge>> _adj = new(
		StringComparer.OrdinalIgnoreCase
	);

	// zone_key -> scene name
	private readonly Dictionary<string, string> _zoneKeyToScene = new(
		StringComparer.OrdinalIgnoreCase
	);

	// Hop-count cache: fromScene -> (scene -> hop count). Invalidated on Rebuild().
	// Computed lazily on first GetHopCount call for a given source scene.
	private Dictionary<string, int>? _hopCache;
	private string? _hopCacheFrom;

	// Locked-hop memo keyed by (from, to) scene pair. Invariant for a given
	// adjacency snapshot: FindFirstLockedHop is a pure function of the zone-line
	// unlock graph. Marker batches issue the same query hundreds of times per
	// startup (548× Stowaway->Tutorial observed); this memo reduces that to one
	// BFS pair per unique scene pair. Null-valued entries record "no locked hop"
	// so negative results short-circuit too.
	private readonly Dictionary<(string From, string To), LockedHop?> _lockedHopCache
		= new(SceneHopKeyComparer.Instance);

	private sealed class SceneHopKeyComparer : IEqualityComparer<(string From, string To)>
	{
		public static readonly SceneHopKeyComparer Instance = new();

		public bool Equals((string From, string To) x, (string From, string To) y) =>
			string.Equals(x.From, y.From, StringComparison.OrdinalIgnoreCase)
			&& string.Equals(x.To, y.To, StringComparison.OrdinalIgnoreCase);

		public int GetHashCode((string From, string To) obj) =>
			HashCode.Combine(
				StringComparer.OrdinalIgnoreCase.GetHashCode(obj.From),
				StringComparer.OrdinalIgnoreCase.GetHashCode(obj.To)
			);
	}

	internal IReadOnlyDictionary<string, List<ZoneEdge>> DebugAdj => _adj;
	internal IReadOnlyDictionary<string, string> DebugZoneKeyToScene => _zoneKeyToScene;
	public int RebuildCount { get; private set; }

	internal AdventureGuide.Diagnostics.DiagnosticsCore? Diagnostics { get; set; }

	internal readonly struct ZoneEdge
	{
		public readonly string DestScene;
		public readonly string ZoneLineKey;
		public readonly bool Accessible;
		public readonly float X,
			Y,
			Z;

		public ZoneEdge(
			string destScene,
			string zoneLineKey,
			bool accessible,
			float x,
			float y,
			float z
		)
		{
			DestScene = destScene;
			ZoneLineKey = zoneLineKey;
			Accessible = accessible;
			X = x;
			Y = y;
			Z = z;
		}
	}

	public ZoneRouter(
	    CompiledGuideModel guide,
	    UnlockEvaluator unlocks)
	{
	    _guide = guide;
	    _unlocks = unlocks;
		// Build zone_key -> scene mapping from zone nodes
		foreach (var zone in guide.NodesOfType(NodeType.Zone))
		{
			if (zone.Scene != null)
				_zoneKeyToScene[zone.Key] = zone.Scene;
		}

		Rebuild();
		RebuildCount = 0;
	}

	/// <summary>
	/// Rebuild the adjacency graph from current zone line data and unlock state.
	/// Call when tracked unlock facts change.
	/// </summary>
	public void Rebuild()
	{
		_adj.Clear();
		_hopCache = null; // invalidate cached hop counts — adjacency changed
		_hopCacheFrom = null;

		_lockedHopCache.Clear(); // adjacency change invalidates memoized routes

		foreach (var zl in _guide.NodesOfType(NodeType.ZoneLine))
		{
			if (zl.Scene == null || zl.DestinationZoneKey == null)
				continue;
			if (!zl.X.HasValue || !zl.Y.HasValue || !zl.Z.HasValue)
				continue;
			if (!_zoneKeyToScene.TryGetValue(zl.DestinationZoneKey, out var destScene))
				continue;

			bool accessible = IsZoneLineAccessible(zl.Key);

			if (!_adj.TryGetValue(zl.Scene, out var edges))
			{
				edges = new List<ZoneEdge>();
				_adj[zl.Scene] = edges;
			}

			// Avoid duplicate edges to same destination — keep most permissive
			bool found = false;
			for (int i = 0; i < edges.Count; i++)
			{
				if (
					string.Equals(edges[i].DestScene, destScene, StringComparison.OrdinalIgnoreCase)
				)
				{
					if (accessible && !edges[i].Accessible)
						edges[i] = new ZoneEdge(
							destScene,
							zl.Key,
							true,
							zl.X.Value,
							zl.Y.Value,
							zl.Z.Value
						);
					found = true;
					break;
				}
			}

			if (!found)
				edges.Add(
					new ZoneEdge(destScene, zl.Key, accessible, zl.X.Value, zl.Y.Value, zl.Z.Value)
				);
		}

		RebuildCount++;
	}

	public void ObserveInvalidation(IReadOnlyCollection<FactKey> changedFacts)
	{
		// The route graph depends on zone-line unlock state. That state is gated by
		// item possession (keyring/unlock items), source state (live spawns / NPC
		// presence affecting yielders/givers), and quest completion (quest-gated
		// zones). Plain inventory-count changes that do not flip an unlock are
		// covered by UnlockItemPossessed; reacting to InventoryItemCount as well
		// would over-rebuild on every loot pickup. Scene changes go through Rebuild
		// directly from the Plugin's scene-changed branch, so they are not handled
		// here.
		foreach (var fact in changedFacts)
		{
			if (fact.Kind is FactKind.UnlockItemPossessed
				or FactKind.SourceState
				or FactKind.QuestCompleted)
			{
				Rebuild();
				return;
			}
		}
	}
	/// <summary>
	/// Find the best route from currentScene to targetScene.
	/// Returns null if no route exists or both are the same zone.
	/// </summary>
	/// <summary>
	/// Minimum hop count from <paramref name="fromScene"/> to
	/// <paramref name="toScene"/>. Returns <see cref="int.MaxValue"/> when
	/// unreachable.
	///
	/// Results are computed once per source scene via a single BFS over all
	/// zones and cached until the next <see cref="Rebuild"/> call. Use this
	/// instead of <see cref="FindRoute"/> when only the distance matters.
	/// </summary>
	public int GetHopCount(string fromScene, string toScene)
	{
		if (string.Equals(fromScene, toScene, StringComparison.OrdinalIgnoreCase))
			return 0;

		if (
			_hopCache == null
			|| !string.Equals(_hopCacheFrom, fromScene, StringComparison.OrdinalIgnoreCase)
		)
		{
			_hopCache = ComputeHopsFrom(fromScene);
			_hopCacheFrom = fromScene;
		}

		return _hopCache.TryGetValue(toScene, out var h) ? h : int.MaxValue;
	}

	/// <summary>
	/// BFS from <paramref name="fromScene"/> across all edges (accessible and
	/// locked) to compute minimum hop counts to every reachable zone.
	/// </summary>
	private Dictionary<string, int> ComputeHopsFrom(string fromScene)
	{
		var hops = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
		var queue = new Queue<string>();

		hops[fromScene] = 0;
		queue.Enqueue(fromScene);

		while (queue.Count > 0)
		{
			var current = queue.Dequeue();
			int depth = hops[current];

			if (!_adj.TryGetValue(current, out var edges))
				continue;

			foreach (var edge in edges)
			{
				if (!hops.ContainsKey(edge.DestScene))
				{
					hops[edge.DestScene] = depth + 1;
					queue.Enqueue(edge.DestScene);
				}
			}
		}

		return hops;
	}

	public Route? FindRoute(string currentScene, string targetScene)
	{
		if (string.Equals(currentScene, targetScene, StringComparison.OrdinalIgnoreCase))
			return null;

		// Try accessible-only path first
		var result = BFS(currentScene, targetScene, accessibleOnly: true);
		if (result == null)
			result = BFS(currentScene, targetScene, accessibleOnly: false);
		return result;
	}

	/// <summary>
	/// Find the first locked hop on the best route from currentScene to targetScene.
	/// Returns null when an accessible-only route exists or no route exists at all.
	/// </summary>

	public LockedHop? FindFirstLockedHop(string currentScene, string targetScene)
	{
		var token = Diagnostics?.BeginSpan(
			AdventureGuide.Diagnostics.DiagnosticSpanKind.ZoneRouterFindLockedHop,
			AdventureGuide.Diagnostics.DiagnosticsContext.Root(AdventureGuide.Diagnostics.DiagnosticTrigger.Unknown),
			primaryKey: currentScene + "->" + targetScene
		);
		long startTick = System.Diagnostics.Stopwatch.GetTimestamp();
		try
		{
			var cacheKey = (currentScene, targetScene);
			if (_lockedHopCache.TryGetValue(cacheKey, out var cached))
				return cached;

			var lockedHops = FindLockedHops(currentScene, targetScene);
			var result = lockedHops.Count == 0 ? null : lockedHops[0];
			_lockedHopCache[cacheKey] = result;
			return result;
		}
		finally
		{
			if (token != null)
				Diagnostics!.EndSpan(
					token.Value,
					System.Diagnostics.Stopwatch.GetTimestamp() - startTick
				);
		}
	}

	public IReadOnlyList<LockedHop> FindLockedHops(string currentScene, string targetScene)
	{
		if (string.Equals(currentScene, targetScene, StringComparison.OrdinalIgnoreCase))
			return Array.Empty<LockedHop>();

		if (BFS(currentScene, targetScene, accessibleOnly: true) != null)
			return Array.Empty<LockedHop>();

		var route = BFS(currentScene, targetScene, accessibleOnly: false);
		if (route == null)
			return Array.Empty<LockedHop>();

		var lockedHops = new List<LockedHop>();
		for (int i = 0; i < route.Path.Count - 1; i++)
		{
			var edge = FindEdge(route.Path[i], route.Path[i + 1], accessibleOnly: false);
			if (edge == null || edge.Value.Accessible)
				continue;

			lockedHops.Add(
				new LockedHop(
					edge.Value.ZoneLineKey,
					route.Path[i],
					route.Path[i + 1],
					edge.Value.X,
					edge.Value.Y,
					edge.Value.Z
				)
			);
		}

		return lockedHops;
	}

	private Route? BFS(string start, string goal, bool accessibleOnly)
	{
		// Parent-map BFS: record each visited scene's predecessor instead of
		// carrying per-edge List<string> copies. Path is reconstructed once at
		// the goal by walking parent pointers back to start. Drops per-edge
		// allocation from O(edges × path-length) to a single Dictionary sized
		// by reachable-zones.
		var parent = new Dictionary<string, string?>(StringComparer.OrdinalIgnoreCase)
		{
			[start] = null,
		};
		var queue = new Queue<string>();
		queue.Enqueue(start);

		while (queue.Count > 0)
		{
			var current = queue.Dequeue();

			if (!_adj.TryGetValue(current, out var edges))
				continue;

			foreach (var edge in edges)
			{
				if (accessibleOnly && !edge.Accessible)
					continue;
				if (parent.ContainsKey(edge.DestScene))
					continue;

				parent[edge.DestScene] = current;

				if (string.Equals(edge.DestScene, goal, StringComparison.OrdinalIgnoreCase))
				{
					var path = ReconstructPath(parent, edge.DestScene);
					var firstHopScene = path[1];
					var firstEdge = FindEdge(start, firstHopScene, accessibleOnly);
					if (firstEdge == null)
						return null;

					// A route from the fallback (accessibleOnly=false) pass is locked
					// if any hop is inaccessible. The first hop is the only one we
					// know for certain here, but any fallback route implies at least
					// one locked hop — we would have returned from the accessible-only
					// pass otherwise.
					bool locked = !accessibleOnly || !firstEdge.Value.Accessible;
					var destZoneKey =
						_guide.GetNode(firstEdge.Value.ZoneLineKey)?.DestinationZoneKey ?? "";
					return new Route(
						destZoneKey,
						start,
						firstEdge.Value.X,
						firstEdge.Value.Y,
						firstEdge.Value.Z,
						locked,
						path
					);
				}

				queue.Enqueue(edge.DestScene);
			}
		}

		return null;
	}

	private static IReadOnlyList<string> ReconstructPath(
		Dictionary<string, string?> parent,
		string goal
	)
	{
		// Walk predecessors goal → start, then reverse to produce start → goal.
		var reversed = new List<string>();
		var cursor = goal;
		while (cursor != null)
		{
			reversed.Add(cursor);
			if (!parent.TryGetValue(cursor, out var prev))
				break;
			cursor = prev;
		}
		reversed.Reverse();
		return reversed;
	}

	private ZoneEdge? FindEdge(string fromScene, string toScene, bool accessibleOnly)
	{
		if (!_adj.TryGetValue(fromScene, out var edges))
			return null;

		foreach (var edge in edges)
		{
			if (string.Equals(edge.DestScene, toScene, StringComparison.OrdinalIgnoreCase))
			{
				if (!accessibleOnly || edge.Accessible)
					return edge;
			}
		}
		return null;
	}

	/// <summary>
	/// Check zone line accessibility via the shared incoming-unlock evaluator.
	/// </summary>
	private bool IsZoneLineAccessible(string zoneLineKey)
	{
		var node = _guide.GetNode(zoneLineKey);
		if (node == null || !node.IsEnabled)
			return false;

		return _unlocks.Evaluate(node).IsUnlocked;
	}
}
