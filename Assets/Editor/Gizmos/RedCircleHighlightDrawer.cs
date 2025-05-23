using UnityEngine;
using UnityEditor;
using System.Collections.Generic;

[InitializeOnLoad]
public static class RedCircleHighlightDrawer
{
    static RedCircleHighlightDrawer()
    {
        SceneView.duringSceneGui += OnSceneGUI;
    }

    static void OnSceneGUI(SceneView sceneView)
    {
        // Gather all selected objects with the RedCircleHighlight component
        var selected = Selection.gameObjects;
        List<(RedCircleHighlight, Transform)> highlights = new List<(RedCircleHighlight, Transform)>();

        foreach (var go in selected)
        {
            var highlight = go.GetComponent<RedCircleHighlight>();
            if (highlight != null)
                highlights.Add((highlight, go.transform));
        }

        // Draw all discs first
        foreach (var (highlight, t) in highlights)
        {
            Handles.color = Color.red;
            Handles.DrawSolidDisc(t.position, Vector3.up, highlight.radius);
        }

        // Draw all labels after all discs
        Handles.BeginGUI();
        foreach (var (highlight, t) in highlights)
        {
            Vector3 pos = t.position;
            string coordText = $"({(int)pos.x}, {(int)pos.y}, {(int)pos.z})";
            Vector3 labelWorldPos = t.position + Vector3.forward * (highlight.radius + highlight.labelOffset);
            Vector2 guiPoint = HandleUtility.WorldToGUIPoint(labelWorldPos);

            var style = new GUIStyle(EditorStyles.boldLabel)
            {
                alignment = TextAnchor.MiddleCenter,
                fontSize = 14,
                normal = { textColor = Color.black }
            };
            Vector2 size = style.CalcSize(new GUIContent(coordText));
            Rect rect = new Rect(guiPoint.x - size.x / 2, guiPoint.y - size.y / 2, size.x, size.y);

            int outline = 2;
            for (int dx = -outline; dx <= outline; dx++)
            {
                for (int dy = -outline; dy <= outline; dy++)
                {
                    if (dx == 0 && dy == 0) continue;
                    GUI.Label(new Rect(rect.x + dx, rect.y + dy, rect.width, rect.height), coordText, style);
                }
            }

            style.normal.textColor = Color.white;
            GUI.Label(rect, coordText, style);
        }
        Handles.EndGUI();
    }
}
