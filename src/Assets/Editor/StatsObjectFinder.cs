using UnityEngine;
using UnityEditor;
using System.Collections.Generic;
using System.Linq;

public class StatsObjectFinder : EditorWindow
{
    private Vector2 scrollPosition;
    private string searchString = "";
    private List<(GameObject obj, int level, float baseHP, string npcName, int? maxDrops, int? maxNonCommonDrops)> objectsWithStats = 
        new List<(GameObject obj, int level, float baseHP, string npcName, int? maxDrops, int? maxNonCommonDrops)>();
    private int minimumLevel = 0;

    private enum SortField
    {
        Name,
        NPCName,
        Level,
        HP,
        Effort,
        MaxDrops,
        MaxNonCommonDrops
    }

    private SortField sortField = SortField.Name;
    private bool sortAscending = true;

    [MenuItem("Tools/Find Objects With Stats")]
    public static void ShowWindow()
    {
        GetWindow<StatsObjectFinder>("NPC Stats Finder");
    }

    private void OnGUI()
    {
        EditorGUILayout.BeginHorizontal();
        GUI.SetNextControlName("SearchField");
        searchString = EditorGUILayout.TextField("Search:", searchString);
        if (GUILayout.Button("Clear", GUILayout.Width(60)))
        {
            searchString = "";
            GUI.FocusControl("SearchField");
        }
        if (GUILayout.Button("Refresh", GUILayout.Width(60)))
        {
            FindObjectsWithStats();
        }
        EditorGUILayout.EndHorizontal();

        EditorGUILayout.BeginHorizontal();
        int newMinLevel = EditorGUILayout.IntField("Minimum Level:", minimumLevel);
        if (newMinLevel != minimumLevel)
        {
            minimumLevel = Mathf.Max(0, newMinLevel);
        }
        EditorGUILayout.EndHorizontal();

        var filteredObjects = objectsWithStats;

        if (!string.IsNullOrEmpty(searchString))
        {
            filteredObjects = filteredObjects.FindAll(item => 
                item.obj.name.ToLower().Contains(searchString.ToLower()) ||
                item.npcName.ToLower().Contains(searchString.ToLower()));
        }

        if (minimumLevel > 0)
        {
            filteredObjects = filteredObjects.FindAll(item => item.level >= minimumLevel);
        }

        filteredObjects = SortObjects(filteredObjects).ToList();

        EditorGUILayout.BeginHorizontal();
        EditorGUILayout.LabelField("NPC Prefabs with Stats:", EditorStyles.boldLabel);
        EditorGUILayout.LabelField($"Total: {filteredObjects.Count}", EditorStyles.boldLabel, GUILayout.Width(100));
        EditorGUILayout.EndHorizontal();

        EditorGUILayout.BeginHorizontal("box");
        if (GUILayout.Button("Name", EditorStyles.miniButtonLeft, GUILayout.Width(170)))
            ToggleSort(SortField.Name);
        if (GUILayout.Button("NPC Name", EditorStyles.miniButtonMid, GUILayout.Width(120)))
            ToggleSort(SortField.NPCName);
        if (GUILayout.Button("Level", EditorStyles.miniButtonMid, GUILayout.Width(70)))
            ToggleSort(SortField.Level);
        if (GUILayout.Button("Base HP", EditorStyles.miniButtonMid, GUILayout.Width(80)))
            ToggleSort(SortField.HP);
        if (GUILayout.Button("Effort", EditorStyles.miniButtonMid, GUILayout.Width(80)))
            ToggleSort(SortField.Effort);
        if (GUILayout.Button("Max Drops", EditorStyles.miniButtonMid, GUILayout.Width(80)))
            ToggleSort(SortField.MaxDrops);
        if (GUILayout.Button("Max Non-Common", EditorStyles.miniButtonRight, GUILayout.Width(100)))
            ToggleSort(SortField.MaxNonCommonDrops);
        EditorGUILayout.EndHorizontal();

        scrollPosition = EditorGUILayout.BeginScrollView(scrollPosition);

        foreach (var (obj, level, baseHP, npcName, maxDrops, maxNonCommonDrops) in filteredObjects)
        {
            EditorGUILayout.BeginHorizontal("box");
            EditorGUILayout.ObjectField(obj, typeof(GameObject), true, GUILayout.Width(170));
            EditorGUILayout.LabelField(npcName, GUILayout.Width(120));
            EditorGUILayout.LabelField($"Level: {level}", GUILayout.Width(70));
            EditorGUILayout.LabelField($"Base HP: {baseHP}", GUILayout.Width(80));
            EditorGUILayout.LabelField($"Effort: {baseHP / level:F2}", GUILayout.Width(80));
            EditorGUILayout.LabelField(maxDrops.HasValue ? maxDrops.ToString() : "-", GUILayout.Width(80));
            EditorGUILayout.LabelField(maxNonCommonDrops.HasValue ? maxNonCommonDrops.ToString() : "-", GUILayout.Width(100));
            EditorGUILayout.EndHorizontal();
        }

        EditorGUILayout.EndScrollView();
    }

    private void ToggleSort(SortField field)
    {
        if (sortField == field)
            sortAscending = !sortAscending;
        else
        {
            sortField = field;
            sortAscending = true;
        }
    }

    private IEnumerable<(GameObject obj, int level, float baseHP, string npcName, int? maxDrops, int? maxNonCommonDrops)> 
        SortObjects(List<(GameObject obj, int level, float baseHP, string npcName, int? maxDrops, int? maxNonCommonDrops)> objects)
    {
        return sortField switch
        {
            SortField.Name => sortAscending 
                ? objects.OrderBy(x => x.obj.name)
                : objects.OrderByDescending(x => x.obj.name),

            SortField.NPCName => sortAscending
                ? objects.OrderBy(x => x.npcName)
                : objects.OrderByDescending(x => x.npcName),

            SortField.Level => sortAscending
                ? objects.OrderBy(x => x.level)
                : objects.OrderByDescending(x => x.level),

            SortField.HP => sortAscending
                ? objects.OrderBy(x => x.baseHP)
                : objects.OrderByDescending(x => x.baseHP),

            SortField.Effort => sortAscending
                ? objects.OrderBy(x => x.baseHP / x.level)
                : objects.OrderByDescending(x => x.baseHP / x.level),

            SortField.MaxDrops => sortAscending
                ? objects.OrderBy(x => x.maxDrops ?? -1)
                : objects.OrderByDescending(x => x.maxDrops ?? -1),

            SortField.MaxNonCommonDrops => sortAscending
                ? objects.OrderBy(x => x.maxNonCommonDrops ?? -1)
                : objects.OrderByDescending(x => x.maxNonCommonDrops ?? -1),

            _ => objects
        };
    }

    private void FindObjectsWithStats()
    {
        objectsWithStats.Clear();

        string[] guids = AssetDatabase.FindAssets("t:GameObject");
        foreach (string guid in guids)
        {
            string path = AssetDatabase.GUIDToAssetPath(guid);
            GameObject prefab = AssetDatabase.LoadAssetAtPath<GameObject>(path);

            if (prefab != null)
            {
                Stats stats = prefab.GetComponent<Stats>();
                Character character = prefab.GetComponent<Character>();
                NPC npc = prefab.GetComponent<NPC>();
                LootTable lootTable = prefab.GetComponent<LootTable>();
                SimPlayer simPlayer = prefab.GetComponent<SimPlayer>();
                
                if (stats != null && character != null && npc != null && simPlayer == null)
                {
                    int? maxDrops = lootTable?.MaxNumberDrops;
                    int? maxNonCommonDrops = lootTable?.MaxNonCommonDrops;
                    
                    objectsWithStats.Add((
                        prefab, 
                        stats.Level, 
                        stats.BaseHP, 
                        npc.NPCName,
                        maxDrops,
                        maxNonCommonDrops
                    ));
                }
            }
        }
    }

    private void OnEnable()
    {
        FindObjectsWithStats();
    }
}