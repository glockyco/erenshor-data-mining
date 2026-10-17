// Only the Unity identity/component and SQLite API surfaces are substituted.
public interface IAssetScanListener<T> { }

public sealed class Character : UnityEngine.Component
{
    public string StableKey = "character:fixture";
}

public sealed class CharacterRecord { }

public sealed class MiningNode : UnityEngine.Component { }

public sealed class ItemRecord { }

public sealed class ForeignKeyAttribute(Type type, string field) : Attribute
{
    public Type RecordType { get; } = type;
    public string Field { get; } = field;
}

public sealed class CharacterStableKeyResolver
{
    public string GetStableKey(Character character) => character.StableKey;
}

public static class ActivationTargetResolver
{
    // Object identity is supplied by the fixture. Identity generation is not under test.
    public static string ObjectKey(UnityEngine.GameObject target) => target.ObjectKey;
}

public sealed class GameManager
{
    public List<Item> CommonWorldItems = new();
}

namespace UnityEngine
{
    public readonly struct Scene(bool valid)
    {
        public bool IsValid() => valid;

        public string name => "FixtureZone";
    }

    public class GameObject
    {
        public string name = "fixture host";
        public Scene scene = new(true);
        public string ObjectKey = "object:fixture:host[0]";
        public bool IsPrefabAsset;
        public string AssetGuid;
        public long LocalId;
        public bool Unloaded;
        private readonly List<Component> _components = new();

        public T Add<T>(T component)
            where T : Component
        {
            component.gameObject = this;
            _components.Add(component);
            return component;
        }

        public T[] GetComponents<T>()
            where T : Component
        {
            if (Unloaded)
                throw new InvalidOperationException("Scene object was unloaded");
            return _components.OfType<T>().ToArray();
        }
    }

    public class Component
    {
        public GameObject gameObject;
        public bool enabled = true;
        private static int _nextInstanceId;
        private readonly int _instanceId = ++_nextInstanceId;
        public Transform transform = new();

        public int GetInstanceID() => _instanceId;

        public T GetComponent<T>()
            where T : Component => GetComponents<T>().FirstOrDefault();

        public T[] GetComponents<T>()
            where T : Component => gameObject.GetComponents<T>();
    }

    public sealed class Transform
    {
        public string name = "";
        public Vector3 position;
    }

    public readonly record struct Vector3(float x, float y, float z);

    public static class Debug
    {
        public static void Log(string message) { }

        public static void LogWarning(string message) { }
    }
}

namespace UnityEditor
{
    public static class PrefabUtility
    {
        public static bool IsPartOfPrefabAsset(UnityEngine.GameObject target) =>
            target.IsPrefabAsset;
    }

    public static class AssetDatabase
    {
        public static bool TryGetGUIDAndLocalFileIdentifier(
            UnityEngine.GameObject target,
            out string guid,
            out long id
        )
        {
            guid = target.AssetGuid;
            id = target.LocalId;
            return guid != null;
        }
    }
}

namespace SQLite
{
    public sealed class TableAttribute(string name) : Attribute { }

    public sealed class PrimaryKeyAttribute : Attribute { }

    public sealed class IndexedAttribute : Attribute
    {
        public string Name { get; set; } = "";
        public int Order { get; set; }
        public bool Unique { get; set; }
    }

    public sealed class SQLiteConnection
    {
        private readonly Dictionary<Type, object> _rows = new();
        public int Transactions { get; private set; }

        public void CreateTable<T>() { }

        public void DeleteAll<T>() => _rows[typeof(T)] = new List<T>();

        public void InsertAll<T>(IEnumerable<T> rows) => _rows[typeof(T)] = rows.ToList();

        public void RunInTransaction(Action action)
        {
            Transactions++;
            action();
        }

        public List<T> Rows<T>() =>
            _rows.TryGetValue(typeof(T), out var rows) ? (List<T>)rows : new();
    }
}
