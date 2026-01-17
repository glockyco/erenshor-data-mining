using UnityEngine;
using UnityEditor;
using UnityEditor.SceneManagement;
using System.Collections.Generic;
using UnityEngine.SceneManagement;

public class SceneScriptSearchWindow : EditorWindow
{
    [MenuItem("Tools/Search Scripts in All Scenes")]
    public static void ShowWindow()
    {
        GetWindow<SceneScriptSearchWindow>("All Scenes Script Search");
    }

    private MonoScript targetScript;
    private Vector2 scrollPosition;
    private List<ScriptReference> foundReferences = new List<ScriptReference>();
    private bool searchInPrefabs = true;
    private bool searchInScenes = true;

    private class ScriptReference
    {
        public string AssetPath;
        public string ObjectPath;
        public bool IsPrefab;
    }

    private void OnGUI()
    {
        EditorGUILayout.LabelField("Find script references across all scenes", EditorStyles.boldLabel);

        targetScript = (MonoScript)EditorGUILayout.ObjectField("Script to find:", targetScript, typeof(MonoScript), false);

        EditorGUILayout.Space();
        searchInScenes = EditorGUILayout.Toggle("Search in Scenes", searchInScenes);
        searchInPrefabs = EditorGUILayout.Toggle("Search in Prefabs", searchInPrefabs);

        if (GUILayout.Button("Search") && targetScript != null)
        {
            foundReferences.Clear();
            SearchForScriptReferences();
        }

        DisplayResults();
    }

    private void DisplayResults()
    {
        if (foundReferences.Count > 0)
        {
            EditorGUILayout.Space();
            EditorGUILayout.LabelField($"Found {foundReferences.Count} references:", EditorStyles.boldLabel);

            scrollPosition = EditorGUILayout.BeginScrollView(scrollPosition);

            foreach (var reference in foundReferences)
            {
                EditorGUILayout.BeginHorizontal();

                string label = reference.IsPrefab ?
                    $"Prefab: {reference.AssetPath}" :
                    $"Scene: {reference.AssetPath} → {reference.ObjectPath}";

                EditorGUILayout.LabelField(label);

                if (GUILayout.Button("Select", GUILayout.Width(60)))
                {
                    Selection.activeObject = AssetDatabase.LoadAssetAtPath<Object>(reference.AssetPath);
                }

                EditorGUILayout.EndHorizontal();
            }

            EditorGUILayout.EndScrollView();
        }
    }

    private void SearchForScriptReferences()
    {
        // Store the current scene so we can return to it
        string currentScenePath = EditorSceneManager.GetActiveScene().path;
        bool sceneIsDirty = EditorSceneManager.GetActiveScene().isDirty;

        if (sceneIsDirty)
        {
            bool save = EditorUtility.DisplayDialog(
                "Save Current Scene?",
                "The current scene has unsaved changes. Save before proceeding?",
                "Save", "Don't Save");

            if (save)
            {
                EditorSceneManager.SaveOpenScenes();
            }
        }

        try
        {
            System.Type scriptType = targetScript.GetClass();

            // Search in prefabs
            if (searchInPrefabs)
            {
                string[] prefabGuids = AssetDatabase.FindAssets("t:Prefab");
                int prefabCount = prefabGuids.Length;

                for (int i = 0; i < prefabCount; i++)
                {
                    string prefabPath = AssetDatabase.GUIDToAssetPath(prefabGuids[i]);
                    EditorUtility.DisplayProgressBar("Searching Prefabs",
                        $"Checking {prefabPath}", (float)i / prefabCount);

                    GameObject prefab = AssetDatabase.LoadAssetAtPath<GameObject>(prefabPath);
                    Component[] components = prefab.GetComponentsInChildren(scriptType, true);

                    if (components.Length > 0)
                    {
                        foundReferences.Add(new ScriptReference {
                            AssetPath = prefabPath,
                            ObjectPath = "",
                            IsPrefab = true
                        });
                    }
                }
            }

            // Search in scenes
            if (searchInScenes)
            {
                string[] sceneGuids = AssetDatabase.FindAssets("t:Scene");
                int sceneCount = sceneGuids.Length;

                for (int i = 0; i < sceneCount; i++)
                {
                    string scenePath = AssetDatabase.GUIDToAssetPath(sceneGuids[i]);
                    EditorUtility.DisplayProgressBar("Searching Scenes",
                        $"Checking {scenePath}", (float)i / sceneCount);

                    Scene scene = EditorSceneManager.OpenScene(scenePath, OpenSceneMode.Single);

                    MonoBehaviour[] scripts = GameObject.FindObjectsOfType(scriptType, true) as MonoBehaviour[];
                    foreach (MonoBehaviour script in scripts)
                    {
                        foundReferences.Add(new ScriptReference {
                            AssetPath = scenePath,
                            ObjectPath = GetGameObjectPath(script.gameObject),
                            IsPrefab = false
                        });
                    }
                }
            }
        }
        finally
        {
            EditorUtility.ClearProgressBar();

            // Return to the original scene
            if (!string.IsNullOrEmpty(currentScenePath))
            {
                EditorSceneManager.OpenScene(currentScenePath);
            }
        }
    }

    private string GetGameObjectPath(GameObject obj)
    {
        string path = obj.name;
        Transform parent = obj.transform.parent;

        while (parent != null)
        {
            path = parent.name + "/" + path;
            parent = parent.parent;
        }

        return path;
    }
}
