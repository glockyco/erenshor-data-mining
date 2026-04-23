using AdventureGuide.CompiledGuide;
using AdventureGuide.Incremental;
using AdventureGuide.Navigation;
using AdventureGuide.Navigation.Queries;
using AdventureGuide.State;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests.Navigation.Queries;

public sealed class SelectorTargetSetQueryTests
{
	[Fact]
	public void Read_UnionsExplicitNonQuestNavKeysWithNavigableQuests()
	{
		var fixture = SelectorTargetSetFixture.Create();

		var result = fixture.Engine.Read(fixture.Query.Query, Unit.Value);

		Assert.Equal(new[] { "item:coin", "quest:a", "quest:b", "quest:c" }, result.Keys);
	}

	[Fact]
	public void Read_Backdates_WhenOnlyQuestResolutionInputsInvalidate()
	{
		var fixture = SelectorTargetSetFixture.Create();
		var first = fixture.Engine.Read(fixture.Query.Query, Unit.Value);

		fixture.Engine.InvalidateFacts(new[] { new FactKey(FactKind.QuestActive, "quest:a") });
		var second = fixture.Engine.Read(fixture.Query.Query, Unit.Value);

		Assert.Same(first, second);
	}

	private sealed class SelectorTargetSetFixture
	{
		private SelectorTargetSetFixture(Engine<FactKey> engine, SelectorTargetSetQuery query)
		{
			Engine = engine;
			Query = query;
		}

		public Engine<FactKey> Engine { get; }
		public SelectorTargetSetQuery Query { get; }

		public static SelectorTargetSetFixture Create()
		{
			var guide = new CompiledGuideBuilder()
				.AddQuest("quest:a", dbName: "QUESTA")
				.AddQuest("quest:b", dbName: "QUESTB")
				.AddQuest("quest:c", dbName: "QUESTC")
				.AddItem("item:coin")
				.Build();
			var engine = new Engine<FactKey>();
			var reader = new GuideReader(
				engine,
				new FakeInventory(),
				new FakeQuestState(),
				new FakeTrackerState(new[] { "QUESTC" }),
				new FakeNavigationSet(new[] { "item:coin", "quest:a" }));
			var navigable = new NavigableQuestsQuery(engine, guide, reader);

			return new SelectorTargetSetFixture(
				engine,
				new SelectorTargetSetQuery(engine, reader, navigable));
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
		public IEnumerable<string> GetImplicitlyAvailableQuestDbNames() => Array.Empty<string>();
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
