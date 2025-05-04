#nullable enable

using System;
using System.IO; // Added for Path operations
using System.Threading.Tasks;
using UnityEditor;
using UnityEngine;
using Database; // Assuming ItemDBRecord is in this namespace
using SQLite; // Added for SQLite connection

public class WikiComparatorWindow : EditorWindow
{
    // --- Configuration (copied from ItemWikiGenerator for consistency) ---
    private const string EXPORTER_PREFS_KEY_DB_PATH = "Erenshor_DatabaseExporter_OutputPath";
    private const string DEFAULT_DB_FILENAME = "Erenshor.sqlite";
    // --- End Configuration ---

    private string _itemIdToCompare = "Charm_of_The_Shield"; // Default example
    private string _statusMessage = "Enter an Item ID and click Compare.";
    private string? _onlineWikiText;
    private string? _localWikiText;
    private Vector2 _scrollPosOnline;
    private Vector2 _scrollPosLocal;
    private bool _isComparing = false;
    private string _fullDbPathDisplay = ""; // To display the resolved path

    [MenuItem("Tools/Wiki/Wiki Comparator")] // Updated menu path for consistency
    public static void ShowWindow()
    {
        WikiComparatorWindow window = GetWindow<WikiComparatorWindow>("Wiki Comparator");
        window.UpdateResolvedPath(); // Calculate path when window opens
        window.minSize = new Vector2(600, 400); // Increased min size for better layout
    }

    void OnEnable()
    {
        UpdateResolvedPath(); // Also update path when script reloads
    }

    // Gets the default path (relative to project root)
    private string GetDefaultDatabasePath()
    {
        // Assumes the DB is in the project root, adjust if needed
        return Path.GetFullPath(Path.Combine(Application.dataPath, "..", DEFAULT_DB_FILENAME));
    }

    void UpdateResolvedPath()
    {
        // Read the path from EditorPrefs, using the default path as a fallback
        string savedPath = EditorPrefs.GetString(EXPORTER_PREFS_KEY_DB_PATH, GetDefaultDatabasePath());
        _fullDbPathDisplay = Path.GetFullPath(savedPath); // Ensure it's a full path for display/use
    }


    private void OnGUI()
    {
        EditorGUILayout.LabelField("Compare Local Item WikiString with Online Wiki Page", EditorStyles.boldLabel);
        EditorGUILayout.Space();

        // Display the resolved database path and check existence
        GUILayout.Label("Database Path (Shared with Exporter):", EditorStyles.boldLabel);
        EditorGUILayout.HelpBox(_fullDbPathDisplay, MessageType.None);

        bool dbExists = File.Exists(_fullDbPathDisplay);
        if (!dbExists)
        {
            EditorGUILayout.HelpBox($"Database file not found!\nPlease ensure the export has run via 'Tools > Database > Export Database' and the path is correctly set there.", MessageType.Error);
        }
        EditorGUILayout.Space();


        _itemIdToCompare = EditorGUILayout.TextField("Item ID (Wiki Page Name)", _itemIdToCompare);

        EditorGUI.BeginDisabledGroup(_isComparing || !dbExists); // Also disable if DB doesn't exist
        if (GUILayout.Button(_isComparing ? "Comparing..." : "Compare Wiki Page"))
        {
            // Fire off the async task without awaiting it in OnGUI
            CompareItemAsync();
        }
        EditorGUI.EndDisabledGroup();

        EditorGUILayout.Space();
        EditorGUILayout.LabelField("Status:", EditorStyles.boldLabel); // Added bold label for status
        // Use HelpBox for status for better visibility and potential icons
        EditorGUILayout.HelpBox(_statusMessage, _isComparing ? MessageType.Info : (_localWikiText != null && _onlineWikiText != null ? MessageType.Info : MessageType.None) );
        EditorGUILayout.Space();

        if (!string.IsNullOrEmpty(_onlineWikiText) || !string.IsNullOrEmpty(_localWikiText))
        {
            EditorGUILayout.BeginHorizontal();

            // --- Online Text ---
            EditorGUILayout.BeginVertical(GUILayout.ExpandWidth(true));
            EditorGUILayout.LabelField("Online Wiki Text (Raw)", EditorStyles.boldLabel);
            _scrollPosOnline = EditorGUILayout.BeginScrollView(_scrollPosOnline, EditorStyles.helpBox, GUILayout.ExpandHeight(true)); // Added style
            // Use TextArea for multiline display, make it read-only
            EditorGUILayout.TextArea(_onlineWikiText ?? "N/A", EditorStyles.textArea, GUILayout.ExpandHeight(true)); // Added style
            EditorGUILayout.EndScrollView();
            EditorGUILayout.EndVertical();

            // --- Local Text ---
            EditorGUILayout.BeginVertical(GUILayout.ExpandWidth(true));
            EditorGUILayout.LabelField("Local WikiString (Raw)", EditorStyles.boldLabel);
            _scrollPosLocal = EditorGUILayout.BeginScrollView(_scrollPosLocal, EditorStyles.helpBox, GUILayout.ExpandHeight(true)); // Added style
            // Use TextArea for multiline display, make it read-only
            EditorGUILayout.TextArea(_localWikiText ?? "N/A", EditorStyles.textArea, GUILayout.ExpandHeight(true)); // Added style
            EditorGUILayout.EndScrollView();
            EditorGUILayout.EndVertical();

            EditorGUILayout.EndHorizontal();
        }
    }

    private async void CompareItemAsync()
    {
        if (string.IsNullOrWhiteSpace(_itemIdToCompare))
        {
            _statusMessage = "Please enter an Item ID.";
            _onlineWikiText = null;
            _localWikiText = null;
            Repaint();
            return;
        }

        // Re-check DB existence before proceeding
        if (!File.Exists(_fullDbPathDisplay))
        {
             _statusMessage = "Database file not found. Cannot perform comparison.";
             _onlineWikiText = null;
             _localWikiText = null;
             Repaint();
             return;
        }


        if (_isComparing) return; // Prevent concurrent comparisons

        _isComparing = true;
        _statusMessage = "Finding local item data in database...";
        _onlineWikiText = null;
        _localWikiText = null;
        Repaint(); // Update UI to show "Comparing..." and clear results

        try
        {
            // --- Step 1: Find the local ItemDBRecord from the database ---
            ItemDBRecord? itemRecord = FindItemRecord(_itemIdToCompare); // Now uses DB lookup

            if (itemRecord == null)
            {
                _statusMessage = $"Error: Item with ID '{_itemIdToCompare}' not found in the database '{Path.GetFileName(_fullDbPathDisplay)}'.";
                _isComparing = false;
                Repaint();
                return;
            }

            _localWikiText = itemRecord.WikiString; // Store local text for display
            _statusMessage = "Fetching and comparing with online wiki...";
            Repaint();

            // --- Step 2: Perform the comparison ---
            string wikiPageName = itemRecord.Id; // Use the ID from the record
            string baseUrl = $"https://erenshor.wiki.gg/wiki/{Uri.EscapeDataString(wikiPageName)}";

            WikiComparator comparator = new WikiComparator();
            (bool areEqual, string? onlineText, string? localText) result = await comparator.CompareWikiStringAsync(baseUrl, itemRecord.WikiString);

            // --- Step 3: Display results ---
            _onlineWikiText = result.onlineText;
            // _localWikiText is already set from itemRecord

            if (result.onlineText == null)
            {
                _statusMessage = "Comparison failed: Could not retrieve or parse online wiki text.";
            }
            else if (result.areEqual)
            {
                _statusMessage = "Match: Local WikiString matches the online version (normalized).";
            }
            else
            {
                _statusMessage = "Difference detected (after normalizing line endings).";
            }
        }
        catch (SQLiteException sqlEx) // Catch specific SQLite errors
        {
             _statusMessage = $"Database Error: {sqlEx.Message}. Ensure the DB exists and is not locked.";
             Debug.LogError($"SQLite Error during Wiki Comparison: {sqlEx}");
        }
        catch (Exception ex)
        {
            _statusMessage = $"An error occurred: {ex.Message}";
            Debug.LogError($"Wiki Comparison Error: {ex}");
        }
        finally
        {
            _isComparing = false;
            Repaint(); // Update UI with final status and text results
        }
    }

    /// <summary>
    /// Finds an ItemDBRecord by its ID by querying the SQLite database.
    /// </summary>
    /// <param name="itemId">The ID of the item to find.</param>
    /// <returns>The ItemDBRecord if found, otherwise null.</returns>
    private ItemDBRecord? FindItemRecord(string itemId)
    {
        if (!File.Exists(_fullDbPathDisplay))
        {
            Debug.LogError($"Database file not found at path: {_fullDbPathDisplay}");
            return null;
        }

        SQLiteConnection? db = null;
        try
        {
            // Connect in ReadOnly mode
            db = new SQLiteConnection(_fullDbPathDisplay, SQLiteOpenFlags.ReadOnly);

            // Query the Items table for the specific item ID
            // Using FindWithQuery for potentially better performance with Primary Key
            // Or use FirstOrDefault if FindWithQuery isn't suitable or available
            // return db.FindWithQuery<ItemDBRecord>("SELECT * FROM Items WHERE Id = ?", itemId);
            return db.Table<ItemDBRecord>().FirstOrDefault(item => item.Id == itemId);
        }
        catch (SQLiteException ex)
        {
            Debug.LogError($"SQLite error querying for item ID '{itemId}': {ex.Message}\n{ex.StackTrace}");
            _statusMessage = $"Database Query Error: {ex.Message}"; // Update status for user
            return null;
        }
        catch (Exception ex)
        {
             Debug.LogError($"General error querying for item ID '{itemId}': {ex.Message}\n{ex.StackTrace}");
             _statusMessage = $"Error: {ex.Message}"; // Update status for user
             return null;
        }
        finally
        {
            // Ensure the database connection is closed
            db?.Close();
            db?.Dispose();
        }
    }
}
