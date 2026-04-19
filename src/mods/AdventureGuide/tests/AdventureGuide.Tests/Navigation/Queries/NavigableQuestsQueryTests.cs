using AdventureGuide.CompiledGuide;
using AdventureGuide.Frontier;
using AdventureGuide.Incremental;
using AdventureGuide.Navigation.Queries;
using AdventureGuide.State;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests.Navigation.Queries;

public sealed class NavigableQuestsQueryTests
{
	[Fact]
	public void Read_ReturnsSortedDeduplicatedQuestKeysAcrossAllSources()
	{
		var fixture = NavigableQuestsFixture.Create();

		var result = fixture.Engine.Read(fixture.Query.Query, Unit.Value);

		Assert.Equal(new[] { "quest:a", "quest:b", "quest:c", "quest:d" }, result.Keys);
	}

	[Fact]
	public void Read_Memoizes_WhenNoInvalidationOccurs()
	{
		var fixture = NavigableQuestsFixture.Create();

		var first = fixture.Engine.Read(fixture.Query.Query, Unit.Value);
		var second = fixture.Engine.Read(fixture.Query.Query, Unit.Value);

		Assert.Same(first, second);
	}

	[Fact]
	public void Read_Recomputes_WhenQuestActiveWildcardInvalidatesEntry()
	{
		var fixture = NavigableQuestsFixture.Create();
		var first = fixture.Engine.Read(fixture.Query.Query, Unit.Value);

		fixture.Engine.InvalidateFacts(new[] { new FactKey(FactKind.QuestActive, "*") });
		var second = fixture.Engine.Read(fixture.Query.Query, Unit.Value);

		Assert.NotSame(first, second);
		Assert.Equal(first, second);
	}

	[Fact]
	public void Read_Recomputes_WhenNavSetWildcardInvalidatesEntry()
	{
		var fixture = NavigableQuestsFixture.Create();
		var first = fixture.Engine.Read(fixture.Query.Query, Unit.Value);

		fixture.Engine.InvalidateFacts(new[] { new FactKey(FactKind.NavSet, "*") });
		var second = fixture.Engine.Read(fixture.Query.Query, Unit.Value);

		Assert.NotSame(first, second);
		Assert.Equal(first, second);
	}

	[Fact]
	public void Read_Recomputes_WhenTrackerSetWildcardInvalidatesEntry()
	{
		var fixture = NavigableQuestsFixture.Create();
		var first = fixture.Engine.Read(fixture.Query.Query, Unit.Value);

		fixture.Engine.InvalidateFacts(new[] { new FactKey(FactKind.TrackerSet, "*") });
		var second = fixture.Engine.Read(fixture.Query.Query, Unit.Value);

		Assert.NotSame(first, second);
		Assert.Equal(first, second);
	}

	private sealed class NavigableQuestsFixture
	{
		private NavigableQuestsFixture(
			Engine<FactKey> engine,
			NavigableQuestsQuery query)
		{
			Engine = engine;
			Query = query;
		}

		public Engine<FactKey> Engine { get; }
		public NavigableQuestsQuery Query { get; }

		public static NavigableQuestsFixture Create()
		{
			var guide = new CompiledGuideBuilder()
				.AddQuest("quest:a", dbName: "QUESTA")
				.AddQuest("quest:b", dbName: "QUESTB")
				.AddQuest("quest:c", dbName: "QUESTC")
				.AddQuest("quest:d", dbName: "QUESTD")
				.AddCharacter("char:vendor")
				.Build();
			var engine = new Engine<FactKey>();
			var reader = new GuideReader(
				engine,
				new FakeInventory(),
				new FakeQuestState(),
				new FakeTrackerState(new[] { "QUESTC", "QUESTA" }),
				new FakeNavigationSet(new[] { "quest:a", "char:vendor" }));

			return new NavigableQuestsFixture(
				engine,
				new NavigableQuestsQuery(engine, guide, reader));
		}
	}

	private sealed class FakeInventory : IInventoryFactSource
	{
		public int GetCount(string itemId) => 0;
	}

	private sealed class FakeQuestState : IQuestStateFactSource
	{
		public string CurrentScene => "Town";
		public bool IsActive(string dbName) => true;
		public bool IsCompleted(string dbName) => false;
		public IEnumerable<string> GetActionableQuestDbNames() => new[] { "QUESTB" };
		public IEnumerable<string> GetImplicitlyAvailableQuestDbNames() => new[] { "QUESTD", "QUESTB" };
	}

	private sealed class FakeTrackerState : ITrackerStateFactSource
	{
		public FakeTrackerState(IReadOnlyList<string> trackedQuests) => TrackedQuests = trackedQuests;
		public IReadOnlyList<string> TrackedQuests { get; }
	}

	private sealed class FakeNavigationSet : INavigationSetFactSource
	{
		private readonly NavigationSet _navigationSet = new();

		public FakeNavigationSet(IEnumerable<string> keys) => _navigationSet.Load(keys);
		public IReadOnlyCollection<string> Keys => _navigationSet.Keys;
	}
}
