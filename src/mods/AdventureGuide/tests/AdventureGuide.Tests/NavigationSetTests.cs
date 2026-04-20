using AdventureGuide.Navigation;
using AdventureGuide.State;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class NavigationSetTests
{
	[Fact]
	public void DrainPendingFacts_IsEmpty_ForUnmutatedSet()
	{
		var set = new NavigationSet();

		var facts = set.DrainPendingFacts();

		Assert.Empty(facts);
	}

	[Fact]
	public void DrainPendingFacts_EmitsNavSetWildcard_AfterOverride()
	{
		var set = new NavigationSet();

		set.Override("node:foo");

		Assert.Contains(new FactKey(FactKind.NavSet, "*"), set.DrainPendingFacts());
	}

	[Fact]
	public void DrainPendingFacts_EmitsNavSetWildcard_AfterToggleAdd()
	{
		var set = new NavigationSet();

		set.Toggle("node:foo");

		Assert.Contains(new FactKey(FactKind.NavSet, "*"), set.DrainPendingFacts());
	}

	[Fact]
	public void DrainPendingFacts_EmitsNavSetWildcard_AfterToggleRemove()
	{
		var set = new NavigationSet();
		set.Override("node:foo");
		set.DrainPendingFacts();

		set.Toggle("node:foo");

		Assert.Contains(new FactKey(FactKind.NavSet, "*"), set.DrainPendingFacts());
	}

	[Fact]
	public void DrainPendingFacts_EmitsNavSetWildcard_AfterClear()
	{
		var set = new NavigationSet();
		set.Override("node:foo");
		set.DrainPendingFacts();

		set.Clear();

		Assert.Contains(new FactKey(FactKind.NavSet, "*"), set.DrainPendingFacts());
	}

	[Fact]
	public void DrainPendingFacts_Suppresses_WhenClearIsNoOp()
	{
		var set = new NavigationSet();

		set.Clear();

		Assert.Empty(set.DrainPendingFacts());
	}

	[Fact]
	public void DrainPendingFacts_EmitsNavSetWildcard_AfterLoad()
	{
		var set = new NavigationSet();

		set.Load(new[] { "node:a", "node:b" });

		Assert.Contains(new FactKey(FactKind.NavSet, "*"), set.DrainPendingFacts());
	}

	[Fact]
	public void DrainPendingFacts_ClearsFlag_AfterFirstDrain()
	{
		var set = new NavigationSet();
		set.Override("node:foo");

		var first = set.DrainPendingFacts();
		var second = set.DrainPendingFacts();

		Assert.NotEmpty(first);
		Assert.Empty(second);
	}

	[Fact]
	public void DrainPendingFacts_Coalesces_MultipleMutationsIntoSingleWildcard()
	{
		var set = new NavigationSet();

		set.Override("node:a");
		set.Toggle("node:b");
		set.Toggle("node:c");

		var facts = set.DrainPendingFacts();
		Assert.Single(facts);
		Assert.Contains(new FactKey(FactKind.NavSet, "*"), facts);
	}
}
