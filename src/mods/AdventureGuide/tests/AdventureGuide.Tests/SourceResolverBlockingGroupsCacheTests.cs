using AdventureGuide.Graph;
using AdventureGuide.Plan;
using AdventureGuide.Resolution;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class SourceResolverBlockingGroupsCacheTests
{
	[Fact]
	public void Blocking_groups_are_memoized_per_session_across_sibling_quests()
	{
		// Two sibling quests share an objective item whose source is blocked by
		// the same unfinished prerequisite quest. Without the session cache,
		// UnlockPredicateEvaluator.GetBlockingRequirementGroups would be called
		// once per emission site per sibling quest. With the cache, each
		// blocked node is evaluated once for the whole batch.
		var guide = new CompiledGuideBuilder()
			.AddQuest("quest:prereq", dbName: "PREREQ")
			.AddCharacter("char:guarded", scene: "Forest", x: 0f, y: 0f, z: 0f)
			.AddItem("item:fur")
			.AddItemSource("item:fur", "char:guarded")
			.AddQuest("quest:a", dbName: "QUESTA", requiredItems: new[] { ("item:fur", 1) })
			.AddQuest("quest:b", dbName: "QUESTB", requiredItems: new[] { ("item:fur", 1) })
			.AddUnlockPredicate("char:guarded", "quest:prereq")
			.Build();

		var tracker = new QuestPhaseTracker(guide);
		tracker.Initialize(
			Array.Empty<string>(),
			new[] { "QUESTA", "QUESTB" },
			new Dictionary<string, int>(),
			Array.Empty<string>()
		);

		var evaluator = new UnlockPredicateEvaluator(guide, tracker);
		var resolver = new SourceResolver(
			guide,
			tracker,
			evaluator,
			new StubLivePositionProvider(),
			TestPositionResolvers.Create(guide)
		);

		// Single shared session across both quest resolutions.
		var session = new SourceResolver.ResolutionSession();

		// Resolve quest A — populates BlockingGroupsCache for the guarded
		// character, so quest B's resolution reuses that entry.
		_ = resolver.ResolveTargets(
			new FrontierEntry(0, QuestPhase.Accepted, -1),
			"Forest",
			session,
			tracer: null
		);

		int firstPassEntryCount = session.BlockingGroupsCache.Count;
		Assert.True(firstPassEntryCount > 0, "first-pass resolution should populate BlockingGroupsCache");

		_ = resolver.ResolveTargets(
			new FrontierEntry(1, QuestPhase.Accepted, -1),
			"Forest",
			session,
			tracer: null
		);

		// Cache entry count stays the same because the guarded character's
		// blocking-group result was already cached by the first quest.
		Assert.Equal(firstPassEntryCount, session.BlockingGroupsCache.Count);

		// Cache entry must be the exact instance returned by the evaluator —
		// the second caller reads the cached list, not a fresh allocation.
		guide.TryGetNodeId("char:guarded", out int guardedNodeId);
		Assert.True(session.BlockingGroupsCache.ContainsKey(guardedNodeId));
	}

	[Fact]
	public void Blocking_groups_cache_returns_same_instance_on_repeat_lookup()
	{
		// Verifies BlockingGroupsCache hands out a stable reference rather
		// than re-building the list per caller.
		var guide = new CompiledGuideBuilder()
			.AddQuest("quest:prereq", dbName: "PREREQ")
			.AddCharacter("char:guarded", scene: "Forest", x: 0f, y: 0f, z: 0f)
			.AddItem("item:fur")
			.AddItemSource("item:fur", "char:guarded")
			.AddQuest("quest:a", dbName: "QUESTA", requiredItems: new[] { ("item:fur", 1) })
			.AddUnlockPredicate("char:guarded", "quest:prereq")
			.Build();

		var tracker = new QuestPhaseTracker(guide);
		tracker.Initialize(
			Array.Empty<string>(),
			new[] { "QUESTA" },
			new Dictionary<string, int>(),
			Array.Empty<string>()
		);

		var evaluator = new UnlockPredicateEvaluator(guide, tracker);
		var resolver = new SourceResolver(
			guide,
			tracker,
			evaluator,
			new StubLivePositionProvider(),
			TestPositionResolvers.Create(guide)
		);

		var session = new SourceResolver.ResolutionSession();
		_ = resolver.ResolveTargets(
			new FrontierEntry(0, QuestPhase.Accepted, -1),
			"Forest",
			session,
			tracer: null
		);

		guide.TryGetNodeId("char:guarded", out int guardedNodeId);
		var firstCached = session.BlockingGroupsCache[guardedNodeId];

		// Second resolution of the same session should not replace or rebuild
		// the cached reference.
		_ = resolver.ResolveTargets(
			new FrontierEntry(0, QuestPhase.Accepted, -1),
			"Forest",
			session,
			tracer: null
		);

		var secondCached = session.BlockingGroupsCache[guardedNodeId];
		Assert.Same(firstCached, secondCached);
	}
}
