using System.Collections;
using System.Collections.Generic;
using UnityEditor;

[InitializeOnLoad]
public static class EditorCoroutineRunner
{
    private static readonly List<IEnumerator> Coroutines = new();

    static EditorCoroutineRunner()
    {
        EditorApplication.update += Update;
    }

    public static void StartCoroutine(IEnumerator routine)
    {
        Coroutines.Add(routine);
    }

    private static void Update()
    {
        for (int i = Coroutines.Count - 1; i >= 0; i--)
        {
            if (!Coroutines[i].MoveNext())
            {
                Coroutines.RemoveAt(i);
            }
        }
    }
}
