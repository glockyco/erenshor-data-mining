using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using UnityEngine.SceneManagement;

public class TileScreenshotter
{
    public class TileShotterSettings
    {
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
                "Azure", new TileShotterSettings
                {
                    ZoomLevels = 4,
                    OriginX = -32,
                    OriginY = 0,
                    BaseTilesX = 2,
                    BaseTilesY = 3,
                    PreProcess = (zoomLevel) =>
                    {
                        if (zoomLevel == 1)
                        {
                            string[] treeNames =
                            {
                                "SM_Tree_Pine_Small_01 (3)",
                                "SM_Tree_Pine_Small_01 (4)",
                                "SM_Tree_Pine_Small_01 (5)",
                            };
                            foreach (var treeName in treeNames)
                            {
                                var obj = GameObject.Find(treeName);
                                obj?.SetActive(false);
                            }
                        }
                    }
                }
            },
            {
                "Azynthi", new TileShotterSettings
                {
                    ZoomLevels = 4,
                    OriginX = 145,
                    OriginY = 130,
                    BaseTilesX = 3,
                    BaseTilesY = 3,
                    PreProcess = (zoomLevel) =>
                    {
                        if (zoomLevel == 0)
                        {
                            var obj = GameObject.Find("SM_Tree_Generic_Giant_01_LOD_01 (1)");
                            obj?.SetActive(false);
                        }
                        else if (zoomLevel == 1)
                        {
                            foreach (GameObject obj in SceneManager.GetActiveScene().GetRootGameObjects())
                            {
                                if (obj.transform.position.x > 650f || obj.transform.position.y < 115f) continue;
                                if (!obj.name.StartsWith("SM_") && !obj.name.ToLower().Contains("torch") && !obj.name.ToLower().Contains("fire")) continue;
                                if (obj.name.StartsWith("SM_Bld_Base_Floor_Combined")) continue;
                                
                                obj.SetActive(false);
                            }
                        }
                        else if (zoomLevel == 3)
                        {
                            foreach (GameObject obj in SceneManager.GetActiveScene().GetRootGameObjects())
                            {
                                if (obj.transform.position.x > 650f || obj.transform.position.y < 105f) continue;
                                if (!obj.name.StartsWith("SM_") && !obj.name.ToLower().Contains("torch") && !obj.name.ToLower().Contains("fire")) continue;
                                
                                obj.SetActive(false);
                            }
                        }
                    }
                }
            },
            {
                "AzynthiClear", new TileShotterSettings
                {
                    ZoomLevels = 4,
                    OriginX = 145,
                    OriginY = 130,
                    BaseTilesX = 3,
                    BaseTilesY = 3,
                    PreProcess = (zoomLevel) =>
                    {
                        if (zoomLevel == 0)
                        {
                            var obj = GameObject.Find("SM_Tree_Generic_Giant_01_LOD_01 (1)");
                            obj?.SetActive(false);
                        }
                        else if (zoomLevel == 1)
                        {
                            foreach (GameObject obj in SceneManager.GetActiveScene().GetRootGameObjects())
                            {
                                if (obj.transform.position.x > 650f || obj.transform.position.y < 115f) continue;
                                if (!obj.name.StartsWith("SM_") && !obj.name.ToLower().Contains("torch") && !obj.name.ToLower().Contains("fire")) continue;
                                if (obj.name.StartsWith("SM_Bld_Base_Floor_Combined")) continue;
                                
                                obj.SetActive(false);
                            }
                        }
                        else if (zoomLevel == 3)
                        {
                            foreach (GameObject obj in SceneManager.GetActiveScene().GetRootGameObjects())
                            {
                                if (obj.transform.position.x > 650f || obj.transform.position.y < 105f) continue;
                                if (!obj.name.StartsWith("SM_") && !obj.name.ToLower().Contains("torch") && !obj.name.ToLower().Contains("fire")) continue;
                                
                                obj.SetActive(false);
                            }
                        }
                    }
                }
            },
            {
                "Blight", new TileShotterSettings
                {
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
                "Braxonian", new TileShotterSettings
                {
                    ZoomLevels = 3,
                    OriginX = -128,
                    OriginY = 0,
                    BaseTilesX = 5,
                    BaseTilesY = 6,
                    PreProcess = (zoomLevel) =>
                    {
                        if (zoomLevel == 1)
                        {
                            string[] treeNames =
                            {
                                "SM_Env_Rock_Cliff_03 (51)",
                                "SM_Env_Rock_Cliff_03 (65)",
                            };
                            foreach (var treeName in treeNames)
                            {
                                var obj = GameObject.Find(treeName);
                                obj?.SetActive(false);
                            }
                        }
                    }
                }
            },
            {
                "Duskenlight", new TileShotterSettings
                {
                    ZoomLevels = 3,
                    OriginX = 0,
                    OriginY = 0,
                    BaseTilesX = 7,
                    BaseTilesY = 4,
                    PreProcess = (zoomLevel) =>
                    {
                        if (zoomLevel == 0)
                        {
                            var obj = GameObject.Find("SM_Env_Rock_Cliff_03 (58)");
                            obj?.SetActive(false);
                        }
                    }
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
                                "SM_Env_Tree_Giant_01_LOD2 (39)",
                                "SM_Env_Rock_Cliff_03 (75)",
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
            },
            {
                "Malaroth", new TileShotterSettings
                {
                    ZoomLevels = 3,
                    OriginX = 0,
                    OriginY = 0,
                    BaseTilesX = 5,
                    BaseTilesY = 4,
                    PreProcess = (zoomLevel) =>
                    {
                        if (zoomLevel == 0)
                        {
                            string[] objectNames =
                            {
                                "SM_Env_Dirt_Cliff_06 (31)",
                                "SM_Env_Dirt_Cliff_06 (25)",
                                "SM_Env_Dirt_Cliff_06 (28)",
                                "SM_Env_Dirt_Cliff_06 (26)",
                                "SM_Env_Dirt_Cliff_06 (27)",
                                "SM_Env_Rock_Cliff_01 (23)",
                                "SM_Env_Dirt_Cliff_06 (30)",
                            };
                            foreach (var objectName in objectNames)
                            {
                                var obj = GameObject.Find(objectName);
                                obj?.SetActive(false);
                            }
                        }
                    }
                }
            },
            {
                "Ripper", new TileShotterSettings
                {
                    ZoomLevels = 3,
                    OriginX = 0,
                    OriginY = 0,
                    BaseTilesX = 4,
                    BaseTilesY = 3,
                    PreProcess = (zoomLevel) =>
                    {
                        if (zoomLevel == 1)
                        {
                            foreach (GameObject obj in SceneManager.GetActiveScene().GetRootGameObjects())
                            {
                                if ((obj.name.StartsWith("SM_") || obj.name.ToLower().Contains("torch")) && obj.transform.position.y > 145f)
                                {
                                    obj.SetActive(false);
                                }
                                string[] objNames =
                                {
                                    "SM_Env_Tree_Large_02_LOD2",
                                    "SM_Env_Tree_Large_02_LOD2 (2)",
                                    "SM_Env_Tree_Giant_02_LOD1 (1)",
                                    "SM_Env_Tree_Giant_02_LOD1",
                                    "SM_Env_Tree_Large_02_LOD2 (1)",
                                };
                                if (objNames.Contains(obj.name))
                                {
                                    obj.SetActive(false);
                                }
                            }
                        }
                        else if (zoomLevel == 2)
                        {
                            foreach (GameObject obj in SceneManager.GetActiveScene().GetRootGameObjects())
                            {
                                if ((obj.name.StartsWith("SM_") || obj.name.ToLower().Contains("torch")) && obj.transform.position.y > 135f)
                                {
                                    obj.SetActive(false);
                                }
                                if (obj.name.StartsWith("SM_Prop_Beam_03"))
                                {
                                    obj.SetActive(false);
                                }
                            }
                        }
                    }
                }
            },
            {
                "Rottenfoot", new TileShotterSettings
                {
                    ZoomLevels = 3,
                    OriginX = 0,
                    OriginY = 0,
                    BaseTilesX = 4,
                    BaseTilesY = 4,
                    PreProcess = (zoomLevel) =>
                    {
                        if (zoomLevel == 0)
                        {
                            string[] treeNames =
                            {
                                "SM_Env_Tree_Swamp_02_LOD2 (1)",
                                "SM_Env_Tree_Swamp_03_LOD1",
                                "SM_Env_Tree_Swamp_03_LOD1 (5)",
                            };
                            foreach (var treeName in treeNames)
                            {
                                var obj = GameObject.Find(treeName);
                                obj?.SetActive(false);
                            }
                        }
                        else if (zoomLevel == 1)
                        {
                            string[] treeNames =
                            {
                                "SM_Env_Tree_Swamp_02 (13)",
                                "SM_Env_Tree_Swamp_02_LOD2",
                                "SM_Env_Tree_Swamp_03 (17)",
                            };
                            foreach (var treeName in treeNames)
                            {
                                var obj = GameObject.Find(treeName);
                                obj?.SetActive(false);
                            }
                        }
                    }
                }
            },
            {
                "SaltedStrand", new TileShotterSettings {
                    ZoomLevels = 3,
                    OriginX = -64,
                    OriginY = 0,
                    BaseTilesX = 4,
                    BaseTilesY = 3,
                    PreProcess = (zoomLevel) =>
                    {
                        if (zoomLevel == 1)
                        {
                            var obj = GameObject.Find("TFF_Rock_Large_05A (3)");
                            obj?.SetActive(false);
                        }
                    }
                }
            },
            {
                "Silkengrass", new TileShotterSettings
                {
                    ZoomLevels = 3,
                    OriginX = -32,
                    OriginY = 0,
                    BaseTilesX = 5,
                    BaseTilesY = 6,
                    PreProcess = (zoomLevel) =>
                    {
                        if (zoomLevel == 1)
                        {
                            var obj = GameObject.Find("SM_Env_Tree_Giant_02_LOD2");
                            obj?.SetActive(false);
                        }
                    }
                }
            },
            {
                "Soluna", new TileShotterSettings
                {
                    ZoomLevels = 3,
                    OriginX = 0,
                    OriginY = 0,
                    BaseTilesX = 4,
                    BaseTilesY = 4,
                }
            },
            {
                "Stowaway", new TileShotterSettings
                {
                    ZoomLevels = 4,
                    OriginX = 135,
                    OriginY = 225,
                    BaseTilesX = 3,
                    BaseTilesY = 2,
                    PreProcess = (zoomLevel) =>
                    {
                        if (zoomLevel == 1)
                        {
                            string[] treeNames =
                            {
                                "TFF_Rock_Large_03A",
                                "TFF_Rock_Large_03A (1)",
                                "TFF_Rock_Large_05A (15)",
                                "TFF_Rock_Large_05A (16)",
                                "TFF_Rock_Large_05A (18)",
                                "TFF_Rock_Large_06A (8)",
                                "TFF_Rock_Large_06A (9)",
                                "TFF_Rock_Large_06A (11)",
                                "TFF_Rock_Large_06A (10)",
                                "TFF_Oak_Tree_01C_LOD_1 (4)",
                                "TFF_Oak_Tree_01C_LOD_1 (5)",
                                "TFF_Pine_Tree_02A (13)"
                            };
                            foreach (var treeName in treeNames)
                            {
                                var obj = GameObject.Find(treeName);
                                obj?.SetActive(false);
                            }
                        }
                    }
                }
            },
            {
                "Tutorial", new TileShotterSettings
                {
                    ZoomLevels = 4,
                    OriginX = -192,
                    OriginY = -192,
                    BaseTilesX = 2,
                    BaseTilesY = 2,
                    PreProcess = (zoomLevel) =>
                    {
                        if (zoomLevel == 0)
                        {
                            foreach (GameObject obj in SceneManager.GetActiveScene().GetRootGameObjects())
                            {
                                if (obj.name.StartsWith("SM_Env_Ceiling_Stone_Flat_06"))
                                {
                                    obj.SetActive(false);
                                }
                                if (obj.name.StartsWith("SM_Env_Cave_Roof_01_DoubleSided"))
                                {
                                    obj.SetActive(false);
                                }
                                if (obj.name.StartsWith("SM_Env_Cave_Large_01 ("))
                                {
                                    obj.SetActive(false);
                                }
                            }
                        }
                        else if (zoomLevel == 3)
                        {
                            foreach (GameObject obj in SceneManager.GetActiveScene().GetRootGameObjects())
                            {
                                if (obj.name.Contains("Occuphage"))
                                {
                                    obj.SetActive(false);
                                }
                                if (obj.transform.position.x > 75f && obj.transform.position.y > 0f && obj.transform.position.z > 100f)
                                {
                                    if (obj.name.StartsWith("SM_"))
                                    {
                                        obj.SetActive(false);
                                    }
                                }
                            }
                        }
                    }
                }
            },
            {
                "Vitheo", new TileShotterSettings {
                    ZoomLevels = 4,
                    BaseTilesX = 2,
                    BaseTilesY = 2,
                    PreProcess = (zoomLevel) =>
                    {
                        if (zoomLevel == 1)
                        {
                            var obj = GameObject.Find("TFF_Oak_Tree_01A (1)");
                            obj?.SetActive(false);
                        }
                    }
                }
            },
            {
                "Windwashed", new TileShotterSettings
                {
                    ZoomLevels = 3,
                    OriginX = 190,
                    OriginY = -128,
                    BaseTilesX = 4,
                    BaseTilesY = 4,
                }
            },
        };

    public static void Run(bool dryRun = true)
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

        Run(settings, dryRun);
    }

    public static void Run(TileShotterSettings settings, bool dryRun = true)
    {
        Time.timeScale = 0f;

        Camera cam = Camera.main;
        Scene scene = SceneManager.GetActiveScene();

        if (dryRun)
        {
            var z = settings.ZoomLevels - 1;
            var tilesX = settings.BaseTilesX << z;
            var tilesY = settings.BaseTilesY << z;
            var unitsPerTile = settings.TileWorldSize / (1 << z); // Adjust if you want tile size to decrease with zoom

            cam.orthographic = true;
            cam.nearClipPlane = 0.1f;
            cam.farClipPlane = 2000f;
            cam.useOcclusionCulling = false;

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
                cam.useOcclusionCulling = false;

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
