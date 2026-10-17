using System.Collections;
using UnityEngine;

// Only external surfaces are replaced. The listener, rows and catalog parser are linked production code.
namespace SQLite
{
    public class TableAttribute(string name) : Attribute { }

    public class PrimaryKeyAttribute : Attribute { }

    public sealed class SQLiteConnection
    {
        private readonly Dictionary<Type, IList> _rows = new();
        public List<string> Operations { get; } = new();

        public void CreateTable<T>()
        {
            Operations.Add("create:" + typeof(T).Name);
            _rows.TryAdd(typeof(T), new List<T>());
        }

        public void DeleteAll<T>()
        {
            Operations.Add("delete:" + typeof(T).Name);
            _rows[typeof(T)].Clear();
        }

        public void InsertAll<T>(IEnumerable<T> rows)
        {
            Operations.Add("insert:" + typeof(T).Name);
            foreach (var row in rows)
                _rows[typeof(T)].Add(row);
        }

        public void RunInTransaction(Action action)
        {
            Operations.Add("transaction");
            action();
        }

        public T[] Rows<T>() =>
            _rows.TryGetValue(typeof(T), out var rows)
                ? rows.Cast<T>().ToArray()
                : Array.Empty<T>();
    }
}

namespace UnityEngine
{
    [AttributeUsage(AttributeTargets.Field)]
    public sealed class SerializeField : Attribute { }

    public class Object
    {
        public string name;
    }

    public class Component : Object
    {
        public GameObject gameObject;

        public T GetComponent<T>()
            where T : Component => gameObject.GetComponent<T>();
    }

    public class Behaviour : Component
    {
        public bool enabled = true;
        public bool isActiveAndEnabled => enabled && gameObject.activeInHierarchy;
    }

    public class MonoBehaviour : Behaviour { }

    public sealed class Transform
    {
        public Vector3 position;
    }

    public struct Vector3
    {
        public float x,
            y,
            z;
    }

    public sealed class Scene
    {
        public string name = "Reliquary";
        public bool Valid = true;

        public bool IsValid() => Valid;
    }

    public sealed class GameObject : Object
    {
        private readonly List<Component> _components = new();
        private readonly List<GameObject> _children = new();
        private GameObject _parent;
        public Scene scene = new();
        public Transform transform = new();
        public GameObject Parent
        {
            get => _parent;
            set
            {
                _parent?._children.Remove(this);
                _parent = value;
                _parent?._children.Add(this);
            }
        }
        public bool activeSelf = true;
        public bool activeInHierarchy => activeSelf && (Parent?.activeInHierarchy ?? true);
        public bool IsPrefab;
        public string FixtureObjectKey;

        public T Add<T>(T component)
            where T : Component
        {
            component.gameObject = this;
            component.name = name;
            _components.Add(component);
            return component;
        }

        public T GetComponent<T>()
            where T : Component => _components.OfType<T>().FirstOrDefault();

        public T GetComponentInChildren<T>(bool includeInactive)
            where T : Component
        {
            if (includeInactive || activeInHierarchy)
            {
                var own = GetComponent<T>();
                if (own != null)
                    return own;
                foreach (var child in _children)
                {
                    var candidate = child.GetComponentInChildren<T>(includeInactive);
                    if (candidate != null)
                        return candidate;
                }
            }
            return null;
        }

        public Component[] GetComponents(Type type) =>
            _components.Where(type.IsInstanceOfType).ToArray();
    }
}

namespace UnityEditor
{
    public static class PrefabUtility
    {
        public static bool IsPartOfPrefabAsset(GameObject host) => host.IsPrefab;
    }
}

public interface IAssetScanListener<T>
{
    void OnAssetFound(T asset);
    void OnScanFinished();
}

public sealed class Item : UnityEngine.Object
{
    public string FixtureKey;
}

public sealed class Quest : UnityEngine.Object
{
    public string FixtureKey;
}

public sealed class Character : MonoBehaviour
{
    public string FixtureKey;
}

public sealed class SpawnPoint : MonoBehaviour
{
    public bool canSpawn = true;
}

public sealed class Zoneline : MonoBehaviour
{
    public string FixtureKey;
}

public sealed class CharacterStableKeyResolver
{
    public string GetStableKey(Character character) => character.FixtureKey;
}

public static class StableKeyGenerator
{
    public static string ForQuest(Quest quest) => quest.FixtureKey;

    public static string ForItem(Item item) => item.FixtureKey;
}

public sealed class ActivationTarget
{
    public string Kind { get; set; }
    public string Key { get; set; }
    public string Scene { get; set; }
    public string ObjectName { get; set; }
    public bool IsEnabled { get; set; }
}

public sealed class ActivationTargetResolver
{
    // Explicit identity/target inputs isolate the listener from placement-key generation and traversal.
    public Dictionary<SpawnPoint, string> SpawnKeys { get; } = new();
    public Dictionary<GameObject, ActivationTarget[]> Subjects { get; } = new();
    public List<SpawnPoint> SpawnRequests { get; } = new();
    public List<(GameObject Host, bool Enabling)> ResolveRequests { get; } = new();

    public static string ObjectKey(GameObject host) =>
        host.FixtureObjectKey
        ?? throw new InvalidOperationException("Unregistered fixture object identity");

    public string GetStableKey(SpawnPoint spawn)
    {
        SpawnRequests.Add(spawn);
        return SpawnKeys[spawn];
    }

    public string GetStableKey(Zoneline line) => line.FixtureKey;

    public IEnumerable<ActivationTarget> Resolve(GameObject host, bool enabling)
    {
        ResolveRequests.Add((host, enabling));
        return Subjects[host];
    }
}

// Public fields retain the exact types required by the closed production constructor contract.
// No shipped lifecycle, account, quest-completion or persistence methods are modeled or invoked.
public sealed class ShiverEvent : MonoBehaviour
{
    public GameObject FirstKio,
        Kio,
        Hider,
        Phantom,
        WarmFlame;
    public List<GameObject> WelcomeCrew = new(),
        SpawnTriggers = new();
}

public sealed class MemorySphere : MonoBehaviour
{
    public GameObject Memory;
    public Item RequiredInInventory;
}

public sealed class SivTorchLight : MonoBehaviour
{
    public GameObject BreakWall;
}

public sealed class ShiveringAngel : MonoBehaviour { }

public sealed class ShiveringPhantomWardListener : MonoBehaviour
{
    public Character ward1,
        ward2;
}

public sealed class FernallaFight : MonoBehaviour
{
    public GameObject RestoredFernalla;
    public SpawnPoint FernSpawnPoint;
}

public sealed class SolunaFight : MonoBehaviour
{
    public GameObject RestoredSoluna;
    public SpawnPoint SolunaSpawn;
}

public sealed class BraxFightEvent : MonoBehaviour
{
    public GameObject GodBraxRestored;
    public SpawnPoint BraxSpawn;
}

public sealed class VithArena : MonoBehaviour
{
    public GameObject RestoredVitheo;
}

public sealed class NPCAliveListener : MonoBehaviour
{
    public SpawnPoint SpawnPoint;
    public List<GameObject> DespawnIfAlive = new(),
        SpawnIfAlive = new();
}

public sealed class MorphTrigger : MonoBehaviour
{
    public List<GameObject> Enable = new(),
        Disable = new();
}

public sealed class PietyTrigger : MonoBehaviour
{
    public Quest RequiredQuest;
    public List<GameObject> Guardians = new();
}

public sealed class NPCShoutListener : MonoBehaviour
{
    public Quest TriggerQuest;
    public bool UseEssentialSpawnsToBlockThisInstance;
}

public sealed class ReliquaryFiend : MonoBehaviour { }

public sealed class ReliqDisableFiendSpawn : MonoBehaviour { }

public sealed class FernallaPortalBoss : MonoBehaviour
{
    public GameObject Ward1,
        Ward2,
        Ward3;
}

public sealed class AngelScript : MonoBehaviour
{
    public GameObject TheBellwains;
}

public sealed class PlanningTable : MonoBehaviour
{
    public GameObject Soluna,
        Hidden,
        Ripper,
        Silkengrass,
        Braxonian,
        Windwashed;
    public GameObject BraxPort,
        FernPort,
        VithPort,
        SolPort;
}

public sealed class ReliqPortalListener : MonoBehaviour
{
    public Zoneline ReliqZL;
    public GameObject ReliqPort;
}
