using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using UnityEngine.SceneManagement;

public class TileScreenshotter
{
    public class TileShotterSettings
    {
        public bool DryRun { get; set; } = true;

        public string OutputRoot { get; set; } = null;

        public float CameraHeight { get; set; } = 1000f;
        public int ZoomLevels { get; set; } = 3;
        public int OriginX { get; set; } = 0;
        public int OriginY { get; set; } = 0;
        public int BaseTilesX { get; set; } = 2;
        public int BaseTilesY { get; set; } = 2;
        public int TilePixelSize { get; set; } = 256;
        public float TileWorldSize { get; set; } = 256f;
        public Action<int> PreProcess { get; set; }
        public Action<int> PostProcess { get; set; }
    }

    private static readonly Dictionary<string, TileScreenshotter.TileShotterSettings> SceneConfigs =
        new Dictionary<string, TileScreenshotter.TileShotterSettings>
        {
            {
                "Blight", new TileShotterSettings
                {
                    DryRun = false,
                    ZoomLevels = 3,
                    BaseTilesX = 4,
                    BaseTilesY = 4,
                }
            },
            {
                "Brake", new TileShotterSettings
                {
                    ZoomLevels = 3,
                    BaseTilesX = 2,
                    BaseTilesY = 2,
                }
            },
            {
                "FernallaField", new TileShotterSettings
                {
                    ZoomLevels = 3,
                    BaseTilesX = 6,
                    BaseTilesY = 6,
                }
            },
            {
                "Hidden", new TileShotterSettings
                {
                    ZoomLevels = 4,
                    OriginX = -200,
                    OriginY = -300,
                    BaseTilesX = 2,
                    BaseTilesY = 2,
                }
            },
            {
                "Loomingwood", new TileShotterSettings
                {
                    ZoomLevels = 3,
                    BaseTilesX = 4,
                    BaseTilesY = 4,
                    PreProcess = (zoomLevel) =>
                    {
                        if (zoomLevel == 0)
                        {
                            string[] treeNames =
                            {
                                "SM_Env_Tree_Giant_01_LOD2 (35)",
                                "SM_Env_Tree_Giant_01_LOD2 (36)",
                                "SM_Env_Tree_Giant_01_LOD2 (37)",
                                "SM_Env_Tree_Giant_01_LOD2 (38)",
                                "SM_Env_Tree_Giant_01_LOD2 (39)"
                            };
                            foreach (var treeName in treeNames)
                            {
                                var obj = GameObject.Find(treeName);
                                obj?.SetActive(false);
                            }
                        }
                        else if (zoomLevel == 1)
                        {
                            var allGameObjects = UnityEngine.Object.FindObjectsOfType<GameObject>();
                            foreach (var go in allGameObjects)
                            {
                                var name = go.name.ToLower();
                                if (name.Contains("tree_giant"))
                                {
                                    go.SetActive(false);
                                }
                            }
                        }
                    }
                }
            }
        };

    public static void Run()
    {
        var sceneName = SceneManager.GetActiveScene().name;
        if (SceneConfigs.TryGetValue(sceneName, out var settings))
        {
            Debug.Log($"Using scene config for {sceneName}: {settings}");
        }
        else
        {
            settings = new TileShotterSettings();
            Debug.Log($"No scene config found for {sceneName}, using default settings.");
        }

        Run(settings);
    }

    public static void Run(TileShotterSettings settings)
    {
        Time.timeScale = 0f;

        Camera cam = Camera.main;
        Scene scene = SceneManager.GetActiveScene();

        if (settings.DryRun)
        {
            var z = settings.ZoomLevels - 1;
            var tilesX = settings.BaseTilesX << z;
            var tilesY = settings.BaseTilesY << z;
            var unitsPerTile = settings.TileWorldSize / (1 << z); // Adjust if you want tile size to decrease with zoom

            cam.orthographic = true;
            cam.nearClipPlane = 0.1f;
            cam.farClipPlane = 2000f;

            // Center camera over the tiling area
            var areaWidth = tilesX * unitsPerTile;
            var areaHeight = tilesY * unitsPerTile;
            cam.transform.position = new Vector3(settings.OriginX + areaWidth / 2f, settings.CameraHeight, settings.OriginY + areaHeight / 2f);
            cam.transform.rotation = Quaternion.Euler(90f, 0f, 0f);
            cam.orthographicSize = Mathf.Max(areaWidth, areaHeight) / 2f;

            var outlineY = settings.CameraHeight / 2;
            var parent = new GameObject("TileOutlines");

            for (var x = 0; x < tilesX; x++)
            {
                for (var y = 0; y < tilesY; y++)
                {
                    var centerX = settings.OriginX + unitsPerTile * (x + 0.5f);
                    var centerZ = settings.OriginY + unitsPerTile * (y + 0.5f);
                    var half = unitsPerTile / 2f;

                    var corners = new Vector3[5]
                    {
                        new Vector3(centerX - half, outlineY, centerZ - half),
                        new Vector3(centerX + half, outlineY, centerZ - half),
                        new Vector3(centerX + half, outlineY, centerZ + half),
                        new Vector3(centerX - half, outlineY, centerZ + half),
                        new Vector3(centerX - half, outlineY, centerZ - half)
                    };

                    var go = new GameObject($"TileOutline_{x}_{y}");
                    go.transform.parent = parent.transform;
                    var lr = go.AddComponent<LineRenderer>();
                    lr.positionCount = 5;
                    lr.SetPositions(corners);
                    lr.startWidth = lr.endWidth = 2f;
                    lr.material = new Material(Shader.Find("Sprites/Default"));
                    lr.startColor = lr.endColor = Color.red;
                    lr.useWorldSpace = true;

                    GameObject textObject = new GameObject($"TileText_{x}_{y}");
                    textObject.transform.parent = parent.transform;
                    textObject.transform.position = new Vector3(centerX, outlineY + 5f, centerZ);

                    var leafletX = x;
                    var leafletY = -(y + 1);

                    var textMesh = textObject.AddComponent<TextMesh>();
                    textMesh.text = $"z={z}\n{leafletX},{leafletY}";
                    textMesh.fontSize = 64;
                    textMesh.characterSize = unitsPerTile / 64f;
                    textMesh.anchor = TextAnchor.MiddleCenter;
                    textMesh.alignment = TextAlignment.Center;
                    textMesh.color = Color.white;
                    textObject.transform.rotation = Quaternion.Euler(90f, 0f, 0f);
                }
            }

            Debug.Log("Dry run: drew tile outlines and set camera to view the full area, with tile indices.");
        }
        else
        {
            if (settings.OutputRoot == null)
            {
                Debug.LogError("OutputRoot is null, cannot run screenshotter.");
                return;
            }

            for (var z = 0; z < settings.ZoomLevels; z++)
            {
                settings.PreProcess?.Invoke(z);

                var tilesX = settings.BaseTilesX << z;
                var tilesY = settings.BaseTilesY << z;
                var unitsPerTile = settings.TileWorldSize / (1 << z);

                cam.orthographic = true;
                cam.nearClipPlane = 0.1f;
                cam.farClipPlane = 2000f;

                var rt = new RenderTexture(settings.TilePixelSize, settings.TilePixelSize, 24);
                var tex = new Texture2D(settings.TilePixelSize, settings.TilePixelSize, TextureFormat.RGB24, false);

                for (var x = 0; x < tilesX; x++)
                {
                    for (var y = 0; y < tilesY; y++)
                    {
                        var centerX = settings.OriginX + unitsPerTile * (x + 0.5f);
                        var centerZ = settings.OriginY + unitsPerTile * (y + 0.5f);

                        cam.transform.position = new Vector3(centerX, settings.CameraHeight, centerZ);
                        cam.transform.rotation = Quaternion.Euler(90f, 0f, 0f);
                        cam.orthographicSize = unitsPerTile / 2f;

                        var leafletX = x;
                        var leafletY = -(y + 1);

                        var dir = $"{settings.OutputRoot}/{scene.name}/{z}/{leafletX}";
                        Directory.CreateDirectory(dir);
                        var path = $"{dir}/{leafletY}.jpg";

                        if (File.Exists(path))
                        {
                            Debug.Log($"Tile already exists, skipping: {path}");
                            continue;
                        }

                        cam.targetTexture = rt;
                        cam.Render();

                        RenderTexture.active = rt;
                        tex.ReadPixels(new Rect(0, 0, settings.TilePixelSize, settings.TilePixelSize), 0, 0);
                        tex.Apply();
                        var bytes = tex.EncodeToJPG(85);
                        File.WriteAllBytes(path, bytes);
                        RenderTexture.active = null;
                        Debug.Log($"Saved tile: {path}");
                    }
                }

                cam.targetTexture = null;
                UnityEngine.Object.DestroyImmediate(rt);
                UnityEngine.Object.DestroyImmediate(tex);

                settings.PostProcess?.Invoke(z);

                Debug.Log($"Zoom level {z} complete.");
            }

            Debug.Log("Screenshot run complete.");
        }
    }
}
