using System.IO;
using UnityEngine;

public class TileScreenshotter
{
    private const bool DryRun = false;
    
    private const string OutputRoot = null;
    
    private const float CameraHeight = 1000f;
    private const float AreaWorldSize = 512f;
    private const int TilePixelSize = 256;
    private const int BaseTilesPerAxis = 2;
    private const int ZoomLevels = 3;

    public static void Run()
    {
        UnityEngine.Time.timeScale = 0f;
        
        Camera cam = Camera.main;

        if (DryRun)
        {
            var z = ZoomLevels - 1;
            var tilesPerAxis = BaseTilesPerAxis << z;
            var unitsPerTile = AreaWorldSize / tilesPerAxis;

            cam.orthographic = true;
            cam.nearClipPlane = 0.1f;
            cam.farClipPlane = 2000f;
            cam.transform.position = new Vector3(AreaWorldSize / 2f, CameraHeight, AreaWorldSize / 2f);
            cam.transform.rotation = Quaternion.Euler(90f, 0f, 0f);
            cam.orthographicSize = AreaWorldSize / 2f;

            var outlineY = CameraHeight / 2;
            var parent = new GameObject("TileOutlines");

            for (var x = 0; x < tilesPerAxis; x++)
            {
                for (var y = 0; y < tilesPerAxis; y++)
                {
                    var centerX = unitsPerTile * (x + 0.5f);
                    var centerZ = unitsPerTile * (y + 0.5f);
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

                    GameObject textGO = new GameObject($"TileText_{x}_{y}");
                    textGO.transform.parent = parent.transform;
                    textGO.transform.position = new Vector3(centerX, outlineY + 5f, centerZ);

                    var leafletX = x;
                    var leafletY = -(y + 1);

                    var textMesh = textGO.AddComponent<TextMesh>();
                    textMesh.text = $"z={z}\n{leafletX},{leafletY}";
                    textMesh.fontSize = 64;
                    textMesh.characterSize = unitsPerTile / 64f;
                    textMesh.anchor = TextAnchor.MiddleCenter;
                    textMesh.alignment = TextAlignment.Center;
                    textMesh.color = Color.white;
                    textGO.transform.rotation = Quaternion.Euler(90f, 0f, 0f);
                }
            }

            UnityEngine.Debug.Log("Dry run: drew tile outlines and set camera to view the full area, with tile indices.");
        }
        else
        {
            if (OutputRoot == null)
            {
                UnityEngine.Debug.LogError("OutputRoot is null, cannot run screenshotter.");
                return;
            }
            
            for (var z = 0; z < ZoomLevels; z++)
            {
                var tilesPerAxis = BaseTilesPerAxis << z;
                var unitsPerTile = AreaWorldSize / tilesPerAxis;

                cam.orthographic = true;
                cam.nearClipPlane = 0.1f;
                cam.farClipPlane = 2000f;

                var rt = new RenderTexture(TilePixelSize, TilePixelSize, 24);
                var tex = new Texture2D(TilePixelSize, TilePixelSize, TextureFormat.RGB24, false);

                for (var x = 0; x < tilesPerAxis; x++)
                {
                    for (var y = 0; y < tilesPerAxis; y++)
                    {
                        var centerX = unitsPerTile * (x + 0.5f);
                        var centerZ = unitsPerTile * (y + 0.5f);

                        cam.transform.position = new Vector3(centerX, CameraHeight, centerZ);
                        cam.transform.rotation = Quaternion.Euler(90f, 0f, 0f);
                        cam.orthographicSize = unitsPerTile / 2f;

                        var leafletX = x;
                        var leafletY = -(y + 1);

                        var dir = $"{OutputRoot}/{z}/{leafletX}";
                        Directory.CreateDirectory(dir);
                        var path = $"{dir}/{leafletY}.jpg";

                        if (File.Exists(path))
                        {
                            UnityEngine.Debug.Log($"Tile already exists, skipping: {path}");
                            continue;
                        }

                        cam.targetTexture = rt;
                        cam.Render();

                        RenderTexture.active = rt;
                        tex.ReadPixels(new Rect(0, 0, TilePixelSize, TilePixelSize), 0, 0);
                        tex.Apply();
                        var bytes = tex.EncodeToJPG(85);
                        File.WriteAllBytes(path, bytes);
                        RenderTexture.active = null;
                        UnityEngine.Debug.Log($"Saved tile: {path}");
                    }
                }

                cam.targetTexture = null;
                UnityEngine.Object.DestroyImmediate(rt);
                UnityEngine.Object.DestroyImmediate(tex);

                UnityEngine.Debug.Log($"Zoom level {z} complete.");
            }

            UnityEngine.Debug.Log("Screenshot run complete.");
        }
    }
}