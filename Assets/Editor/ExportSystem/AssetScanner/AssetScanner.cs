using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using Debug = UnityEngine.Debug;
using Object = UnityEngine.Object;

public static class AssetScanner
{
    private static readonly Dictionary<Type, HashSet<object>> ComponentListeners = new();
    private static readonly Dictionary<Type, HashSet<object>> ScriptableObjectListeners = new();

    public static void RegisterComponentListener<T>(IAssetScanListener<T> listener) where T : Component
    {
        RegisterListener(ComponentListeners, listener);
    }

    public static void RegisterScriptableObjectListener<T>(IAssetScanListener<T> listener) where T : ScriptableObject
    {
        RegisterListener(ScriptableObjectListeners, listener);
    }

    private static void RegisterListener<T>(Dictionary<Type, HashSet<object>> map, IAssetScanListener<T> listener)
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

    public static IEnumerator ScanAllAssetsCoroutine(
        Func<bool> cancelRequested = null,
        Action<AssetScanProgress> progressCallback = null)
    {
        const float maxFrameTimeMs = 10f;
        Stopwatch stopwatch = new Stopwatch();

        // --- ScriptableObjects ---
        if (ScriptableObjectListeners.Count > 0)
        {
            var scriptableGuids = AssetDatabase.FindAssets("t:ScriptableObject");
            int total = scriptableGuids.Length;
            int current = 0;
            stopwatch.Restart();
            foreach (var guid in scriptableGuids)
            {
                if (cancelRequested != null && cancelRequested())
                {
                    yield break;
                }

                current++;
                var path = AssetDatabase.GUIDToAssetPath(guid);
                var asset = AssetDatabase.LoadAssetAtPath<ScriptableObject>(path);
                progressCallback?.Invoke(new AssetScanProgress
                {
                    Phase = "ScriptableObjects",
                    Current = current,
                    Total = total,
                });

                if (asset == null) continue;
                var assetType = asset.GetType();
                foreach (var kvp in ScriptableObjectListeners)
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
                                // Use reflection to call the correct generic method
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

                if (stopwatch.ElapsedMilliseconds >= maxFrameTimeMs)
                {
                    stopwatch.Restart();
                    yield return null;
                }
            }
        }

        if (ComponentListeners.Count > 0)
        {
            // --- Prefabs ---
            var prefabGuids = AssetDatabase.FindAssets("t:Prefab");
            int prefabTotal = prefabGuids.Length;
            int prefabCurrent = 0;
            stopwatch.Restart();
            foreach (var guid in prefabGuids)
            {
                if (cancelRequested != null && cancelRequested())
                {
                    yield break;
                }

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

                if (stopwatch.ElapsedMilliseconds >= maxFrameTimeMs)
                {
                    stopwatch.Restart();
                    yield return null;
                }
            }

            // --- Scenes ---
            var sceneGuids = AssetDatabase.FindAssets("t:Scene");
            int sceneTotal = sceneGuids.Length;
            int sceneCurrent = 0;
            foreach (var guid in sceneGuids)
            {
                if (cancelRequested != null && cancelRequested())
                {
                    yield break;
                }

                sceneCurrent++;
                var path = AssetDatabase.GUIDToAssetPath(guid);
                var scene = EditorSceneManager.OpenScene(path, OpenSceneMode.Additive);

                var rootObjects = scene.GetRootGameObjects();

                foreach (var rootObj in rootObjects)
                {
                    progressCallback?.Invoke(new AssetScanProgress
                    {
                        Phase = "Scenes",
                        Current = sceneCurrent,
                        Total = sceneTotal,
                    });

                    foreach (var _ in ScanComponentsInHierarchy(
                                 rootObj, stopwatch, maxFrameTimeMs, cancelRequested, progressCallback,
                                 "Scenes", sceneCurrent, sceneTotal))
                    {
                        yield return null;
                    }
                }

                EditorSceneManager.CloseScene(scene, true);

                if (stopwatch.ElapsedMilliseconds >= maxFrameTimeMs)
                {
                    stopwatch.Restart();
                    yield return null;
                }
            }
        }
    }

    private static IEnumerable<object> ScanComponentsInHierarchy(
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
            foreach (var kvp in ComponentListeners)
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
