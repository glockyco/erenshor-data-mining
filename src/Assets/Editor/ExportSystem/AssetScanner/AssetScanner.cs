using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using Debug = UnityEngine.Debug;
using Object = UnityEngine.Object;

public class AssetScanner
{
    private readonly Dictionary<Type, HashSet<object>> _nullListeners = new();
    private readonly Dictionary<Type, HashSet<object>> _gameObjectListeners = new();
    private readonly Dictionary<Type, HashSet<object>> _componentListeners = new();
    private readonly Dictionary<Type, HashSet<object>> _scriptableObjectListeners = new();

    public void RegisterNullListener(IAssetScanListener<Object> listener)
    {
        RegisterListener(_nullListeners, listener);
    }

    public void RegisterGameObjectListener(IAssetScanListener<GameObject> listener)
    {
        RegisterListener(_gameObjectListeners, listener);
    }

    public void RegisterComponentListener<T>(IAssetScanListener<T> listener) where T : Component
    {
        RegisterListener(_componentListeners, listener);
    }

    public void RegisterScriptableObjectListener<T>(IAssetScanListener<T> listener) where T : ScriptableObject
    {
        RegisterListener(_scriptableObjectListeners, listener);
    }

    private void RegisterListener<T>(Dictionary<Type, HashSet<object>> map, IAssetScanListener<T> listener)
        where T : Object
    {
        var type = typeof(T);
        if (!map.TryGetValue(type, out var set))
        {
            set = new HashSet<object>();
            map[type] = set;
        }
        set.Add(listener);
    }

    private void InvokeListenerMethod(object listenerObj, string methodName)
    {
        listenerObj.GetType().GetMethod(methodName)?.Invoke(listenerObj, null);
    }

    public IEnumerator ScanAllAssetsCoroutine(
        Func<bool> cancelRequested = null,
        Action<AssetScanProgress> progressCallback = null)
    {
        const float maxFrameTimeMs = 10f;
        Stopwatch stopwatch = new Stopwatch();

        // --- Notify Scan Started ---
        foreach (var listenerMap in new[] { _nullListeners, _scriptableObjectListeners, _componentListeners })
        {
            foreach (var listenerObj in listenerMap.SelectMany(kvp => kvp.Value))
            {
                InvokeListenerMethod(listenerObj, "OnScanStarted");
            }
        }

        // --- ScriptableObjects ---
        if (_scriptableObjectListeners.Count > 0)
        {
            var assets = new List<ScriptableObject>(Resources.LoadAll<ScriptableObject>(""));

            var guids = AssetDatabase.FindAssets("t:Class");
            foreach (var guid in guids)
            {
                var path = AssetDatabase.GUIDToAssetPath(guid);
                var asset = AssetDatabase.LoadAssetAtPath<Class>(path);
                if (asset != null)
                {
                    assets.Add(asset);
                }
            }

            int total = assets.Count;
            int current = 0;
            stopwatch.Restart();
            foreach (var asset in assets)
            {
                if (cancelRequested != null && cancelRequested())
                {
                    yield break;
                }
                current++;
                progressCallback?.Invoke(new AssetScanProgress
                {
                    Phase = "ScriptableObjects",
                    Current = current,
                    Total = total,
                });
                if (asset == null) continue;
                var assetType = asset.GetType();
                foreach (var kvp in _scriptableObjectListeners)
                {
                    if (cancelRequested != null && cancelRequested())
                    {
                        yield break;
                    }
                    if (kvp.Key.IsAssignableFrom(assetType))
                    {
                        foreach (var listenerObj in kvp.Value)
                        {
                            try
                            {
                                var listenerType = listenerObj.GetType();
                                var method = listenerType.GetMethod("OnAssetFound");
                                if (method != null)
                                {
                                    method.Invoke(listenerObj, new object[] { asset });
                                }
                            }
                            catch (Exception ex)
                            {
                                Debug.LogError($"ScriptableObject listener error: {ex}");
                            }
                        }
                    }
                    if (stopwatch.ElapsedMilliseconds >= maxFrameTimeMs)
                    {
                        stopwatch.Restart();
                        yield return null;
                    }
                }
            }
        }

        // --- Prefabs ---
        if (_componentListeners.Count > 0)
        {
            var prefabGuids = AssetDatabase.FindAssets("t:Prefab");
            int prefabTotal = prefabGuids.Length;
            int prefabCurrent = 0;
            stopwatch.Restart();
            foreach (var guid in prefabGuids)
            {
                if (cancelRequested != null && cancelRequested())
                    yield break;
                prefabCurrent++;
                var path = AssetDatabase.GUIDToAssetPath(guid);
                var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(path);
                progressCallback?.Invoke(new AssetScanProgress
                {
                    Phase = "Prefabs",
                    Current = prefabCurrent,
                    Total = prefabTotal,
                });
                if (prefab != null)
                {
                    foreach (var _ in ScanGameObjectsAndComponentsInHierarchy(
                        prefab, stopwatch, maxFrameTimeMs, cancelRequested, progressCallback,
                        "Prefabs", prefabCurrent, prefabTotal, false))
                    {
                        yield return null;
                    }
                }
            }
        }

        // --- Scenes ---
        if (_gameObjectListeners.Count > 0 || _componentListeners.Count > 0)
        {
            var scenePaths = EditorBuildSettings.scenes;
            int total = scenePaths.Length;
            int current = 0;
            foreach (var scene in scenePaths)
            {
                if (cancelRequested != null && cancelRequested())
                    yield break;
                current++;
                progressCallback?.Invoke(new AssetScanProgress
                {
                    Phase = "Scenes",
                    Current = current,
                    Total = total,
                });
                var sceneObj = EditorSceneManager.OpenScene(scene.path, OpenSceneMode.Single);
                var rootObjects = sceneObj.GetRootGameObjects();
                foreach (var root in rootObjects)
                {
                    foreach (var _ in ScanGameObjectsAndComponentsInHierarchy(
                        root, stopwatch, maxFrameTimeMs, cancelRequested, progressCallback,
                        "Scenes", current, total, true))
                    {
                        yield return null;
                    }
                }
            }
        }

        // --- Notify Scan Finished ---
        foreach (var listenerMap in new[] { _nullListeners, _gameObjectListeners, _scriptableObjectListeners, _componentListeners })
        {
            foreach (var listenerObj in listenerMap.SelectMany(kvp => kvp.Value))
            {
                InvokeListenerMethod(listenerObj, "OnScanFinished");
            }
        }
    }

    private IEnumerable<object> ScanGameObjectsAndComponentsInHierarchy(
        GameObject root,
        Stopwatch stopwatch,
        float maxFrameTimeMs,
        Func<bool> cancelRequested,
        Action<AssetScanProgress> progressCallback,
        string parentPhase,
        int parentCurrent,
        int parentTotal,
        bool notifyGameObjectListeners)
    {
        if (root == null)
        {
            yield break;
        }

        Stack<GameObject> stack = new Stack<GameObject>();
        stack.Push(root);

        while (stack.Count > 0)
        {
            if (cancelRequested != null && cancelRequested())
            {
                yield break;
            }

            var go = stack.Pop();

            // Notify GameObject listeners
            if (notifyGameObjectListeners)
            {
                var goType = go.GetType();
                foreach (var kvp in _gameObjectListeners)
                {
                    if (kvp.Key.IsAssignableFrom(goType))
                    {
                        foreach (var listenerObj in kvp.Value)
                        {
                            if (listenerObj == null)
                            {
                                continue;
                            }
                            try
                            {
                                var listenerType = listenerObj.GetType();
                                var method = listenerType.GetMethod("OnAssetFound");
                                if (method != null)
                                {
                                    method.Invoke(listenerObj, new object[] { go });
                                }
                            }
                            catch (Exception ex)
                            {
                                Debug.LogError($"GameObject listener error: {ex}");
                            }
                        }
                    }
                }
            }

            // Notify Component listeners
            var components = go.GetComponents<Component>();
            foreach (var comp in components)
            {
                if (comp == null)
                {
                    continue;
                }

                var compType = comp.GetType();
                foreach (var kvp in _componentListeners)
                {
                    if (kvp.Key.IsAssignableFrom(compType))
                    {
                        foreach (var listenerObj in kvp.Value)
                        {
                            if (listenerObj == null)
                            {
                                continue;
                            }
                            try
                            {
                                var listenerType = listenerObj.GetType();
                                var method = listenerType.GetMethod("OnAssetFound");
                                if (method != null)
                                {
                                    method.Invoke(listenerObj, new object[] { comp });
                                }
                            }
                            catch (Exception ex)
                            {
                                Debug.LogError($"Component listener error: {ex}");
                            }
                        }
                    }
                }
            }

            progressCallback?.Invoke(new AssetScanProgress
            {
                Phase = parentPhase,
                Current = parentCurrent,
                Total = parentTotal,
            });

            if (stopwatch.ElapsedMilliseconds >= maxFrameTimeMs)
            {
                stopwatch.Restart();
                yield return null;
            }

            foreach (Transform child in go.transform)
            {
                if (child != null && child.gameObject != null)
                {
                    stack.Push(child.gameObject);
                }
            }
        }
    }
}
