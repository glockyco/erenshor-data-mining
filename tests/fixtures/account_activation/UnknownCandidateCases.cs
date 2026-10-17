using System.Reflection;
using UnityEngine;

internal sealed class CandidateFieldFixture : MonoBehaviour
{
    [SerializeField]
    private Character PrivateActor;

    [SerializeField]
    private GameObject PrivateActorGroup;
    private Character RuntimeActor;

    [NonSerialized]
    public Character NonSerializedActor;
    public readonly Character ReadonlyActor;
    public static Character StaticActor;
    public Component SelfComponent;
    public Component UnrelatedComponent;
    public List<Component> ComponentLinks;
    public List<Character> ActorReferences;

    public CandidateFieldFixture(
        Character actor,
        GameObject group,
        Component self,
        Component unrelated
    )
    {
        PrivateActor = RuntimeActor = NonSerializedActor = ReadonlyActor = StaticActor = actor;
        PrivateActorGroup = group;
        SelfComponent = self;
        UnrelatedComponent = unrelated;
        ComponentLinks = [self, unrelated];
        ActorReferences = [null, actor];
    }
}

internal sealed class SimPlayer : MonoBehaviour
{
    [SerializeField]
    private Character Myself;

    public void BindHost() => Myself = GetComponent<Character>();
}

internal static class UnknownCandidateCases
{
    public static object Capture(DynamicSpawnCatalog catalog)
    {
        var host = new GameObject { name = "discovery-host" };
        var ownActor = host.Add(new Character { FixtureKey = "character:self" });
        var selfComponent = host.Add(new Component());
        var unrelatedHost = new GameObject { name = "unrelated-component-host" };
        var unrelated = unrelatedHost.Add(new Component());
        var inactiveChild = new GameObject
        {
            name = "foreign-actor",
            Parent = unrelatedHost,
            activeSelf = false,
        };
        var foreignActor = inactiveChild.Add(new Character { FixtureKey = "character:foreign" });
        var fields = host.Add(
            new CandidateFieldFixture(foreignActor, unrelatedHost, selfComponent, unrelated)
        );
        var candidates = typeof(CandidateFieldFixture)
            .GetFields(
                BindingFlags.Instance
                    | BindingFlags.Static
                    | BindingFlags.Public
                    | BindingFlags.NonPublic
            )
            .Where(field => field.DeclaringType == typeof(CandidateFieldFixture))
            .Select(field =>
            {
                bool serialized = UnknownSpawnCandidateResolver.IsSerializedField(field);
                var entry = catalog.Classify(nameof(CandidateFieldFixture), field.Name);
                var actor =
                    serialized && entry.Classification == DynamicSpawnClassification.Unknown
                        ? UnknownSpawnCandidateResolver.Resolve(field.GetValue(fields))
                        : null;
                return new
                {
                    field = field.Name,
                    serialized,
                    actor = actor?.FixtureKey,
                };
            })
            .ToArray();
        var cache = host.Add(new SimPlayer());
        cache.BindHost();
        var cacheField = typeof(SimPlayer).GetField(
            "Myself",
            BindingFlags.Instance | BindingFlags.NonPublic
        );
        var cacheValue = cacheField.GetValue(cache);
        UnknownSpawnCandidateResolver.ValidateHostCharacterCache(host, cacheValue);
        UnknownSpawnCandidateResolver.ValidateHostCharacterCache(host, null);
        string foreignCacheError = null;
        try
        {
            UnknownSpawnCandidateResolver.ValidateHostCharacterCache(host, foreignActor);
        }
        catch (InvalidOperationException exception)
        {
            foreignCacheError = exception.Message;
        }
        string missingHostError = null;
        try
        {
            UnknownSpawnCandidateResolver.ValidateHostCharacterCache(new GameObject(), null);
        }
        catch (InvalidOperationException exception)
        {
            missingHostError = exception.Message;
        }
        return new
        {
            candidates,
            selfCache = new
            {
                serialized = UnknownSpawnCandidateResolver.IsSerializedField(cacheField),
                classification = catalog
                    .Classify(nameof(SimPlayer), cacheField.Name)
                    .Classification.ToString(),
                actualHost = ReferenceEquals(cacheValue, ownActor),
                foreignCacheError,
                missingHostError,
            },
        };
    }
}
