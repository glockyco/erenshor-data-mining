namespace UnityEngine;

public enum KeyCode
{
    None,
    J,
    K,
    L,
    P,
}

public static class Input
{
    public static bool GetKey(KeyCode key) => false;

    public static bool GetKeyDown(KeyCode key) => false;
}

public struct Vector3
{
    public float x;
    public float y;
    public float z;

    public Vector3(float x, float y, float z)
    {
        this.x = x;
        this.y = y;
        this.z = z;
    }
}

public class Object
{
    private static int _nextId;
    private readonly int _id = Interlocked.Increment(ref _nextId);
    public static List<Object> SceneObjects { get; } = [];

    public int GetInstanceID() => _id;

    public static T[] FindObjectsOfType<T>()
        where T : Object => SceneObjects.OfType<T>().ToArray();
}

public sealed class Transform
{
    public Vector3 position;
}

public sealed class GameObject
{
    public bool activeInHierarchy = true;
    public Transform transform { get; } = new();
    public Dictionary<Type, Component> Components { get; } = new();
}

public class Component : Object
{
    public GameObject gameObject { get; set; } = new();
    public Transform transform => gameObject.transform;

    public T? GetComponent<T>()
        where T : Component =>
        gameObject.Components.TryGetValue(typeof(T), out var component) ? (T)component : null;
}
