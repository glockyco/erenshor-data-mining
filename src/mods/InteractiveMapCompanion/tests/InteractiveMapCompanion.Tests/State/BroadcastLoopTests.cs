using InteractiveMapCompanion.Config;
using InteractiveMapCompanion.Entities;
using InteractiveMapCompanion.Server;
using InteractiveMapCompanion.State;
using Newtonsoft.Json.Linq;
using Xunit;

namespace InteractiveMapCompanion.Tests.State;

public class BroadcastLoopTests
{
    private sealed class FakeEntityTracker : IEntityTracker
    {
        public IReadOnlyList<EntityData> Entities { get; set; } = [];
        public int GetTrackedEntitiesCalls { get; private set; }
        public Exception? ExceptionToThrow { get; set; }

        public IReadOnlyList<EntityData> GetTrackedEntities()
        {
            GetTrackedEntitiesCalls++;
            if (ExceptionToThrow is not null)
                throw ExceptionToThrow;

            return Entities;
        }
    }

    private sealed class FakeWebSocketServer : IWebSocketServer
    {
        public List<string> BroadcastedMessages { get; } = [];
        public List<string> BroadcastAttempts { get; } = [];
        public Queue<Exception> BroadcastExceptions { get; } = new();
        public int ClientCount { get; set; } = 1;

        public void Start() { }

        public void Stop() { }

        public void Broadcast(string message)
        {
            BroadcastAttempts.Add(message);
            if (BroadcastExceptions.Count > 0)
                throw BroadcastExceptions.Dequeue();

            BroadcastedMessages.Add(message);
        }

        public void Dispose() { }
    }

    private sealed class FakeBroadcastConfig : IBroadcastConfig
    {
        public int UpdateInterval { get; set; } = 100;
    }

    private static BroadcastLoop CreateBroadcastLoop(
        FakeEntityTracker? tracker = null,
        FakeWebSocketServer? server = null,
        FakeBroadcastConfig? config = null,
        Action<string>? log = null
    ) =>
        new(
            tracker ?? new FakeEntityTracker(),
            server ?? new FakeWebSocketServer(),
            config ?? new FakeBroadcastConfig(),
            log
        );

    private static JObject ParseMessage(FakeWebSocketServer server, int index) =>
        JObject.Parse(server.BroadcastedMessages[index]);

    private static JObject ParseAttempt(FakeWebSocketServer server, int index) =>
        JObject.Parse(server.BroadcastAttempts[index]);

    [Fact]
    public void Tick_StrictlyBeforeInterval_DoesNotBroadcast()
    {
        var server = new FakeWebSocketServer();
        var loop = CreateBroadcastLoop(server: server);

        loop.Tick(0.099f);

        Assert.Empty(server.BroadcastedMessages);
    }

    [Fact]
    public void Tick_AtExactInterval_BroadcastsState()
    {
        var server = new FakeWebSocketServer();
        var loop = CreateBroadcastLoop(server: server);
        var before = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();

        loop.Tick(0.1f);

        var after = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
        var message = ParseMessage(server, 0);
        Assert.Equal("stateUpdate", message["type"]?.Value<string>());
        Assert.Equal(JTokenType.String, message["zone"]?.Type);
        Assert.Equal("", message["zone"]?.Value<string>());
        Assert.Equal(JTokenType.Integer, message["timestamp"]?.Type);
        Assert.InRange(message["timestamp"]!.Value<long>(), before, after);
        Assert.Equal(JTokenType.Array, message["entities"]?.Type);
        Assert.Empty(message["entities"]!);
    }

    [Fact]
    public void Tick_AccumulatedFragments_BroadcastOnceAtInterval()
    {
        var server = new FakeWebSocketServer();
        var loop = CreateBroadcastLoop(server: server);

        loop.Tick(0.03f);
        loop.Tick(0.03f);
        loop.Tick(0.03f);
        Assert.Empty(server.BroadcastedMessages);

        loop.Tick(0.03f);

        Assert.Single(server.BroadcastedMessages);
        Assert.Equal("stateUpdate", ParseMessage(server, 0)["type"]?.Value<string>());
    }

    [Fact]
    public void Tick_NoClients_ShortCircuitsBeforeTracker()
    {
        var tracker = new FakeEntityTracker();
        var server = new FakeWebSocketServer { ClientCount = 0 };
        var loop = CreateBroadcastLoop(tracker: tracker, server: server);

        loop.Tick(0.1f);

        Assert.Equal(0, tracker.GetTrackedEntitiesCalls);
        Assert.Empty(server.BroadcastAttempts);
    }

    [Fact]
    public void Tick_StatePayloadContainsCompleteEntitiesAndOmitsNullOptionalValues()
    {
        var tracker = new FakeEntityTracker
        {
            Entities =
            [
                new EntityData(
                    Id: 42,
                    EntityType: "npc",
                    Name: "Goblin",
                    Position: [1.25f, -2.5f, 3.75f],
                    Rotation: 90.5f,
                    Level: 12,
                    Rarity: "rare",
                    CharacterClass: "Warrior",
                    Owner: "Player"
                ),
                new EntityData(
                    Id: 7,
                    EntityType: "pet",
                    Name: "Wolf",
                    Position: [0f, 1f, 2f],
                    Rotation: 15f
                ),
            ],
        };
        var server = new FakeWebSocketServer();
        var loop = CreateBroadcastLoop(tracker: tracker, server: server);

        loop.Tick(0.1f);

        var message = ParseMessage(server, 0);
        var entities = (JArray)message["entities"]!;
        Assert.Equal(2, entities.Count);

        var complete = (JObject)entities[0]!;
        Assert.Equal(42, complete["id"]?.Value<int>());
        Assert.Equal("npc", complete["entityType"]?.Value<string>());
        Assert.Equal("Goblin", complete["name"]?.Value<string>());
        Assert.Equal(1.25f, complete["position"]?[0]?.Value<float>());
        Assert.Equal(-2.5f, complete["position"]?[1]?.Value<float>());
        Assert.Equal(3.75f, complete["position"]?[2]?.Value<float>());
        Assert.Equal(90.5f, complete["rotation"]?.Value<float>());
        Assert.Equal(12, complete["level"]?.Value<int>());
        Assert.Equal("rare", complete["rarity"]?.Value<string>());
        Assert.Equal("Warrior", complete["characterClass"]?.Value<string>());
        Assert.Equal("Player", complete["owner"]?.Value<string>());

        var nullOptionals = (JObject)entities[1]!;
        Assert.Equal(7, nullOptionals["id"]?.Value<int>());
        Assert.Equal("pet", nullOptionals["entityType"]?.Value<string>());
        Assert.Equal("Wolf", nullOptionals["name"]?.Value<string>());
        Assert.Equal(0f, nullOptionals["position"]?[0]?.Value<float>());
        Assert.Equal(1f, nullOptionals["position"]?[1]?.Value<float>());
        Assert.Equal(2f, nullOptionals["position"]?[2]?.Value<float>());
        Assert.Equal(15f, nullOptionals["rotation"]?.Value<float>());
        Assert.Null(nullOptionals["level"]);
        Assert.Null(nullOptionals["rarity"]);
        Assert.Null(nullOptionals["characterClass"]);
        Assert.Null(nullOptionals["owner"]);
    }

    [Fact]
    public void OnSceneLoaded_FirstZone_SendsStateWithoutZoneChange()
    {
        var server = new FakeWebSocketServer();
        var loop = CreateBroadcastLoop(server: server);

        loop.OnSceneLoaded("FirstZone");

        Assert.Single(server.BroadcastedMessages);
        var state = ParseMessage(server, 0);
        Assert.Equal("stateUpdate", state["type"]?.Value<string>());
        Assert.Equal("FirstZone", state["zone"]?.Value<string>());
    }

    [Fact]
    public void OnSceneLoaded_SameZone_SendsStateWithoutZoneChange()
    {
        var server = new FakeWebSocketServer();
        var loop = CreateBroadcastLoop(server: server);

        loop.OnSceneLoaded("SameZone");
        server.BroadcastedMessages.Clear();

        loop.OnSceneLoaded("SameZone");

        Assert.Single(server.BroadcastedMessages);
        Assert.Equal("stateUpdate", ParseMessage(server, 0)["type"]?.Value<string>());
    }

    [Fact]
    public void OnSceneLoaded_ChangedZone_SendsZoneChangeBeforeStateWithExactZones()
    {
        var server = new FakeWebSocketServer();
        var loop = CreateBroadcastLoop(server: server);

        loop.OnSceneLoaded("FirstZone");
        server.BroadcastedMessages.Clear();
        var before = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();

        loop.OnSceneLoaded("SecondZone");

        var after = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
        Assert.Equal(2, server.BroadcastedMessages.Count);
        var zoneChange = ParseMessage(server, 0);
        Assert.Equal("zoneChange", zoneChange["type"]?.Value<string>());
        Assert.Equal("FirstZone", zoneChange["previousZone"]?.Value<string>());
        Assert.Equal("SecondZone", zoneChange["zone"]?.Value<string>());
        Assert.Equal(JTokenType.Integer, zoneChange["timestamp"]?.Type);
        Assert.InRange(zoneChange["timestamp"]!.Value<long>(), before, after);

        var state = ParseMessage(server, 1);
        Assert.Equal("stateUpdate", state["type"]?.Value<string>());
        Assert.Equal("SecondZone", state["zone"]?.Value<string>());
    }

    [Fact]
    public void OnSceneLoaded_NoClients_ShortCircuitsBeforeTracker()
    {
        var tracker = new FakeEntityTracker();
        var server = new FakeWebSocketServer { ClientCount = 0 };
        var loop = CreateBroadcastLoop(tracker: tracker, server: server);

        loop.OnSceneLoaded("TestZone");

        Assert.Equal(0, tracker.GetTrackedEntitiesCalls);
        Assert.Empty(server.BroadcastAttempts);
    }

    [Fact]
    public void Stop_PreventsTickAndSceneBroadcasts_AndRepeatedStopIsInert()
    {
        var server = new FakeWebSocketServer();
        var loop = CreateBroadcastLoop(server: server);

        loop.Tick(0.1f);
        loop.Stop();
        loop.Stop();
        loop.Tick(0.1f);
        loop.OnSceneLoaded("StoppedZone");

        Assert.Single(server.BroadcastedMessages);
        Assert.Single(server.BroadcastAttempts);
    }

    [Fact]
    public void TrackerException_DoesNotEscape_AndLogsExactStateContext()
    {
        var tracker = new FakeEntityTracker
        {
            ExceptionToThrow = new InvalidOperationException("tracker failed"),
        };
        var server = new FakeWebSocketServer();
        var logs = new List<string>();
        var loop = CreateBroadcastLoop(tracker: tracker, server: server, log: logs.Add);

        var exception = Record.Exception(() => loop.Tick(0.1f));

        Assert.Null(exception);
        Assert.Empty(server.BroadcastedMessages);
        Assert.Equal(["Error broadcasting state: tracker failed"], logs);
    }

    [Fact]
    public void ServerException_DoesNotEscape_AndLogsExactStateContext()
    {
        var tracker = new FakeEntityTracker();
        var server = new FakeWebSocketServer();
        server.BroadcastExceptions.Enqueue(new InvalidOperationException("server failed"));
        var logs = new List<string>();
        var loop = CreateBroadcastLoop(tracker: tracker, server: server, log: logs.Add);

        var exception = Record.Exception(() => loop.Tick(0.1f));

        Assert.Null(exception);
        Assert.Single(server.BroadcastAttempts);
        Assert.Empty(server.BroadcastedMessages);
        Assert.Equal(["Error broadcasting state: server failed"], logs);
    }

    [Fact]
    public void FailedZoneChangeSend_StillAttemptsStateUpdate_AndLogsExactZoneContext()
    {
        var tracker = new FakeEntityTracker();
        var server = new FakeWebSocketServer();
        var logs = new List<string>();
        var loop = CreateBroadcastLoop(tracker: tracker, server: server, log: logs.Add);

        loop.OnSceneLoaded("FirstZone");
        server.BroadcastExceptions.Enqueue(new InvalidOperationException("zone send failed"));
        server.BroadcastAttempts.Clear();
        server.BroadcastedMessages.Clear();
        logs.Clear();

        var exception = Record.Exception(() => loop.OnSceneLoaded("SecondZone"));

        Assert.Null(exception);
        Assert.Equal(2, server.BroadcastAttempts.Count);
        Assert.Equal("zoneChange", ParseAttempt(server, 0)["type"]?.Value<string>());
        Assert.Equal("FirstZone", ParseAttempt(server, 0)["previousZone"]?.Value<string>());
        Assert.Equal("SecondZone", ParseAttempt(server, 0)["zone"]?.Value<string>());
        Assert.Equal("stateUpdate", ParseAttempt(server, 1)["type"]?.Value<string>());
        Assert.Single(server.BroadcastedMessages);
        Assert.Equal("stateUpdate", ParseMessage(server, 0)["type"]?.Value<string>());
        Assert.Equal(["Error sending zone change: zone send failed"], logs);
    }
}
