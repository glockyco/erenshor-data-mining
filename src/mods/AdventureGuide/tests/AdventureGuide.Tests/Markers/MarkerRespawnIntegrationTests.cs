using System.Linq;
using AdventureGuide.Markers;
using Xunit;

namespace AdventureGuide.Tests.Markers;

public sealed class MarkerRespawnIntegrationTests
{
	[Theory]
	[InlineData(MarkerLiveStatus.DeadWithCorpse, MarkerType.DeadSpawn)]
	[InlineData(MarkerLiveStatus.ZoneReentry, MarkerType.ZoneReentry)]
	public void Project_RestoresAllSharedSourceMarkers_WhenLifecycleStateClears(
		MarkerLiveStatus lifecycleStatus,
		MarkerType expectedLifecycleMarkerType)
	{
		var fixture = MarkerProjectorTests.MarkerProjectorFixture.CreateTwoActiveQuestsSameSourceDifferentKinds();

		fixture.LiveState.RenderStatesByCandidateKey["spawn:leaf-1"] =
			new MarkerLiveRenderState(
				MarkerLiveStatus.Alive,
				livePosition: (10f, 20.8f, 30f),
				respawnSeconds: 0f,
				unlockReason: null);

		fixture.Projector.Project();
		var liveEntries1 = fixture.Projector.Markers
			.Where(e => e.SourceNodeKey == "spawn:leaf-1")
				.OrderBy(e => e.Type)
				.ToList();

		Assert.Equal(new[] { MarkerType.TurnInReady, MarkerType.Objective }, liveEntries1.Select(e => e.Type).ToArray());

		fixture.LiveState.RenderStatesByCandidateKey["spawn:leaf-1"] =
			new MarkerLiveRenderState(
				lifecycleStatus,
				livePosition: lifecycleStatus == MarkerLiveStatus.DeadWithCorpse ? (14f, 24.8f, 34f) : null,
				respawnSeconds: 30f,
				unlockReason: null);

		fixture.Projector.Project();
		var lifecycleEntries2 = fixture.Projector.Markers
			.Where(e => e.SourceNodeKey == "spawn:leaf-1")
				.ToList();

		var lifecycleEntry = Assert.Single(lifecycleEntries2);
		Assert.Equal(expectedLifecycleMarkerType, lifecycleEntry.Type);

		fixture.LiveState.RenderStatesByCandidateKey["spawn:leaf-1"] =
			new MarkerLiveRenderState(
				MarkerLiveStatus.Alive,
				livePosition: (40f, 50.8f, 60f),
				respawnSeconds: 0f,
				unlockReason: null);

		fixture.Projector.Project();
		var liveEntries3 = fixture.Projector.Markers
			.Where(e => e.SourceNodeKey == "spawn:leaf-1")
				.OrderBy(e => e.Type)
				.ToList();

		Assert.Equal(new[] { MarkerType.TurnInReady, MarkerType.Objective }, liveEntries3.Select(e => e.Type).ToArray());
		Assert.All(
			liveEntries3,
			entry =>
			{
				Assert.Equal(40f, entry.X);
				Assert.Equal(50.8f, entry.Y);
				Assert.Equal(60f, entry.Z);
			});
	}

	[Fact]
	public void Project_UsesSingleZoneReentryMarker_ForSharedSourceAcrossQuestKinds()
	{
		var fixture = MarkerProjectorTests.MarkerProjectorFixture.CreateTwoActiveQuestsSameSourceDifferentKinds();

		fixture.LiveState.RenderStatesByCandidateKey["spawn:leaf-1"] =
			new MarkerLiveRenderState(
				MarkerLiveStatus.ZoneReentry,
				livePosition: null,
				respawnSeconds: 0f,
				unlockReason: null);

		fixture.Projector.Project();
		var entries = fixture.Projector.Markers
			.Where(e => e.SourceNodeKey == "spawn:leaf-1")
			.ToList();

		var entry = Assert.Single(entries);
		Assert.Equal(MarkerType.ZoneReentry, entry.Type);
	}

	[Fact]
	public void Project_LeavesNoStaleDeadMarkerAfterKillTargetRespawns()
	{
		var fixture = MarkerProjectorTests.MarkerProjectorFixture.CreateKillQuest();

		fixture.LiveState.RenderStatesByCandidateKey["spawn:leaf-1"] =
			new MarkerLiveRenderState(
				MarkerLiveStatus.Alive,
				livePosition: (10f, 20.8f, 30f),
				respawnSeconds: 0f,
				unlockReason: null);

		fixture.Projector.Project();
		var entries1 = fixture.Projector.Markers;
		var active1 = Assert.Single(entries1, e => e.Type == MarkerType.Objective);
		Assert.Equal(10f, active1.X);
		Assert.Equal(20.8f, active1.Y);
		Assert.Equal(30f, active1.Z);
		Assert.Single(entries1, e => e.SourceNodeKey == "spawn:leaf-1");

		fixture.LiveState.RenderStatesByCandidateKey["spawn:leaf-1"] =
			new MarkerLiveRenderState(
				MarkerLiveStatus.DeadWithCorpse,
				livePosition: (14f, 24.8f, 34f),
				respawnSeconds: 30f,
				unlockReason: null);
		fixture.Projector.Project();

		var entries2 = fixture.Projector.Markers;
		var dead2 = Assert.Single(entries2, e => e.SourceNodeKey == "spawn:leaf-1");
		Assert.Equal(MarkerType.DeadSpawn, dead2.Type);
		Assert.Equal(14f, dead2.X);
		Assert.Equal(24.8f, dead2.Y);
		Assert.Equal(34f, dead2.Z);
		Assert.DoesNotContain(entries2, e => e.SourceNodeKey == "spawn:leaf-1" && e.Type == MarkerType.Objective);

		fixture.LiveState.RenderStatesByCandidateKey["spawn:leaf-1"] =
			new MarkerLiveRenderState(
				MarkerLiveStatus.Alive,
				livePosition: (40f, 50.8f, 60f),
				respawnSeconds: 0f,
				unlockReason: null);

		fixture.Projector.Project();
		var entries3 = fixture.Projector.Markers;
		var active3 = Assert.Single(entries3, e => e.Type == MarkerType.Objective);

		Assert.Equal(40f, active3.X);
		Assert.Equal(50.8f, active3.Y);
		Assert.Equal(60f, active3.Z);
		Assert.Single(entries3, e => e.SourceNodeKey == "spawn:leaf-1");
		Assert.DoesNotContain(entries3, e => e.Type == MarkerType.DeadSpawn);
	}
}
