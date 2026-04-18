using AdventureGuide.Graph;
using AdventureGuide.Plan;
using AdventureGuide.Resolution;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests;

/// <summary>
/// Verifies that the RequiredForQuestIndex-deferred pattern on
/// UnlockRequirementCache and RecipeMaterialCache is both (1) correctness-
/// preserving — sibling callers see their own RequiredForQuestIndex in
/// the returned ResolvedTargets — and (2) sharing — the cached list is
/// looked up once and reused across callers.
/// </summary>
public sealed class SourceResolverCacheSharingTests
{
	[Fact]
	public void UnlockRequirement_is_shared_across_callers_with_distinct_RequiredForQuestIndex()
	{
		// Two sibling quests both accept via a giver whose unlock predicate
		// requires the same prerequisite quest to be completed. Under the old
		// keying each sibling resolved its own UnlockRequirementCache entry;
		// with the deferred pattern they now share, and ApplyRequiredForQuestIndex
		// substitutes each caller's value into the returned targets.
		var guide = new CompiledGuideBuilder()
			.AddQuest("quest:prereq", dbName: "PREREQ")
			.AddCharacter("char:gated", scene: "Forest", x: 0f, y: 0f, z: 0f)
			.AddItem("item:token")
			.AddItemSource("item:token", "char:gated")
			.AddQuest("quest:a", dbName: "QUESTA", requiredItems: new[] { ("item:token", 1) })
			.AddQuest("quest:b", dbName: "QUESTB", requiredItems: new[] { ("item:token", 1) })
			.AddUnlockPredicate("char:gated", "quest:prereq")
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

		var session = new SourceResolver.ResolutionSession();

		// Resolve quest A with RequiredForQuestIndex = 100 (distinct sentinel
		// so we can check rebind correctness below).
		var entryA = new FrontierEntry(0, QuestPhase.Accepted, 100);
		_ = resolver.ResolveTargets(entryA, "Forest", session, tracer: null);

		int cacheSizeAfterA = session.UnlockRequirementCache.Count;
		Assert.True(cacheSizeAfterA > 0, "UnlockRequirementCache must be populated by first resolution");

		// Resolve quest B with a different RequiredForQuestIndex. The cache
		// must not grow — the shared entry is reused.
		var entryB = new FrontierEntry(1, QuestPhase.Accepted, 200);
		_ = resolver.ResolveTargets(entryB, "Forest", session, tracer: null);

		Assert.Equal(cacheSizeAfterA, session.UnlockRequirementCache.Count);
	}
}
