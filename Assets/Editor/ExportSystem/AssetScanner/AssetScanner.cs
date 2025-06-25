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
    private readonly Dictionary<Type, HashSet<object>> _componentListeners = new();
    private readonly Dictionary<Type, HashSet<object>> _scriptableObjectListeners = new();

    public void RegisterNullListener(IAssetScanListener<Object> listener)
    {
        RegisterListener(_nullListeners, listener);
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
                    foreach (var _ in ScanComponentsInHierarchy(
                        prefab, stopwatch, maxFrameTimeMs, cancelRequested, progressCallback,
                        "Prefabs", prefabCurrent, prefabTotal))
                    {
                        yield return null;
                    }
                }
            }
        }

        // --- Scenes ---
        if (_componentListeners.Count > 0)
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
                    foreach (var _ in ScanComponentsInHierarchy(
                        root, stopwatch, maxFrameTimeMs, cancelRequested, progressCallback,
                        "Scenes", current, total))
                    {
                        yield return null;
                    }
                }
            }
        }

        // --- Notify Scan Finished ---
        foreach (var listenerMap in new[] { _nullListeners, _scriptableObjectListeners, _componentListeners })
        {
            foreach (var listenerObj in listenerMap.SelectMany(kvp => kvp.Value))
            {
                InvokeListenerMethod(listenerObj, "OnScanFinished");
            }
        }
    }

    private IEnumerable<object> ScanComponentsInHierarchy(
        GameObject root,
        Stopwatch stopwatch,
        float maxFrameTimeMs,
        Func<bool> cancelRequested,
        Action<AssetScanProgress> progressCallback,
        string parentPhase,
        int parentCurrent,
        int parentTotal)
    {
        if (root == null)
        {
            yield break;
        }

        var allComponents = root.GetComponentsInChildren<Component>(true);

        foreach (var comp in allComponents)
        {
            if (cancelRequested != null && cancelRequested())
            {
                yield break;
            }

            progressCallback?.Invoke(new AssetScanProgress
            {
                Phase = parentPhase,
                Current = parentCurrent,
                Total = parentTotal,
            });

            if (comp == null)
            {
                continue;
            }

            var compType = comp.GetType();
            foreach (var kvp in _componentListeners)
            {
                if (cancelRequested != null && cancelRequested())
                {
                    yield break;
                }

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

                if (stopwatch.ElapsedMilliseconds >= maxFrameTimeMs)
                {
                    stopwatch.Restart();
                    yield return null;
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
