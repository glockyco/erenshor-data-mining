#nullable enable

using System;
using System.IO;
using UnityEditor;
using UnityEngine;
using SQLite;
using Database; // Explicitly use the Database namespace for ItemDBRecord
using Erenshor.Editor.WikiUtils; // Use the new namespace for WikiComparator

namespace Erenshor.Editor.WikiUtils // Enclose window class in the namespace
{
    public class WikiComparatorWindow : EditorWindow
    {
        // --- Configuration (copied from ItemWikiGenerator for consistency) ---
        private const string EXPORTER_PREFS_KEY_DB_PATH = "Erenshor_DatabaseExporter_OutputPath";
        private const string DEFAULT_DB_FILENAME = "Erenshor.sqlite";
        // --- End Configuration ---

        private string _itemIdToCompare = ""; // Default is empty, set from DB in OnEnable
        private string _statusMessage = "Enter an Item ID (Wiki Page Name) and click Compare.";
        private MessageType _statusMessageType = MessageType.Info;
        // These will now hold the specific templates being compared or status messages
        private string? _displayOnlineText;
        private string? _displayLocalText;
        private Vector2 _scrollPosOnline;
        private Vector2 _scrollPosLocal;
        private bool _isComparing = false;
        private string _fullDbPathDisplay = ""; // To display the resolved DB path

        [MenuItem("Tools/Wiki/Wiki Comparator")] // Consistent menu path
        public static void ShowWindow()
        {
            WikiComparatorWindow window = GetWindow<WikiComparatorWindow>("Wiki Comparator");
            window.minSize = new Vector2(600, 400); // Set minimum size
            // UpdateResolvedPath and SetDefaultItemIdFromDb are called in OnEnable
        }

        void OnEnable()
        {
            UpdateResolvedPath(); // Calculate path when script reloads/window enabled
            SetDefaultItemIdFromDb(); // Attempt to set default ID from DB
        }

        // Gets the default path (relative to project root)
        private string GetDefaultDatabasePath()
        {
            // Assumes the DB is in the project root
            return Path.GetFullPath(Path.Combine(Application.dataPath, "..", DEFAULT_DB_FILENAME));
        }

        void UpdateResolvedPath()
        {
            // Read the path from EditorPrefs, using the default path as a fallback
            string savedPath = EditorPrefs.GetString(EXPORTER_PREFS_KEY_DB_PATH, GetDefaultDatabasePath());
            _fullDbPathDisplay = Path.GetFullPath(savedPath); // Ensure it's a full path
        }

        /// <summary>
        /// Attempts to find the first item with a non-empty WikiString in the DB
        /// and sets its Id (Primary Key) as the default value for the input field.
        /// </summary>
        private void SetDefaultItemIdFromDb()
        {
            if (!File.Exists(_fullDbPathDisplay))
            {
                Debug.LogWarning($"[WikiComparatorWindow] Database not found at {_fullDbPathDisplay}. Cannot set default Item ID.");
                _statusMessage = "Database not found. Cannot set default Item ID.";
                _statusMessageType = MessageType.Warning;
                return;
            }

            SQLiteConnection? db = null;
            try
            {
                db = new SQLiteConnection(_fullDbPathDisplay, SQLiteOpenFlags.ReadOnly);
                // Find the first item that has a WikiString value.
                var firstItemWithWiki = db.Table<ItemDBRecord>().FirstOrDefault(item => !string.IsNullOrEmpty(item.WikiString));

                if (firstItemWithWiki != null)
                {
                    // Set the default value to the Id (Primary Key)
                    _itemIdToCompare = firstItemWithWiki.Id;
                    _statusMessage = $"Defaulting to first found Item ID '{_itemIdToCompare}'. Enter the exact Wiki Page Name (Item ID) to compare.";
                    _statusMessageType = MessageType.Info;
                    Debug.Log($"[WikiComparatorWindow] Set default Item ID input to '{firstItemWithWiki.Id}'.");
                }
                else
                {
                    _statusMessage = "No items with WikiStrings found in DB. Please enter an Item ID manually.";
                    _statusMessageType = MessageType.Warning;
                    Debug.LogWarning("[WikiComparatorWindow] No items with non-empty WikiString found in the database.");
                }
            }
            catch (Exception ex)
            {
                _statusMessage = "Error reading database to find default item.";
                _statusMessageType = MessageType.Error;
                Debug.LogError($"[WikiComparatorWindow] Error reading database to find default item: {ex.Message}\n{ex.StackTrace}");
            }
            finally
            {
                db?.Close();
                db?.Dispose();
            }
            Repaint(); // Update the UI
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

            // Input field label clarifies that the Wiki Page Name (usually Item.Id) is needed
            _itemIdToCompare = EditorGUILayout.TextField("Item ID (Wiki Page Name)", _itemIdToCompare);

            EditorGUI.BeginDisabledGroup(_isComparing || !dbExists); // Disable button if comparing or DB missing
            if (GUILayout.Button(_isComparing ? "Comparing..." : "Compare Wiki Page"))
            {
                // Fire off the async task without awaiting it in OnGUI
                CompareItemAsync();
            }
            EditorGUI.EndDisabledGroup();

            EditorGUILayout.Space();
            EditorGUILayout.LabelField("Status:", EditorStyles.boldLabel);
            // Use HelpBox for status for better visibility
            EditorGUILayout.HelpBox(_statusMessage, _statusMessageType);
            EditorGUILayout.Space();

            // Display text areas only if there's text to show from the comparison result
            if (!string.IsNullOrEmpty(_displayOnlineText) || !string.IsNullOrEmpty(_displayLocalText))
            {
                EditorGUILayout.BeginHorizontal();

                // --- Local Text (Specific Template or Message) --- LEFT SIDE ---
                EditorGUILayout.BeginVertical(GUILayout.ExpandWidth(true));
                EditorGUILayout.LabelField("Local WikiString (Relevant Template)", EditorStyles.boldLabel);
                _scrollPosLocal = EditorGUILayout.BeginScrollView(_scrollPosLocal, EditorStyles.helpBox, GUILayout.ExpandHeight(true));
                // Use read-only TextArea for multiline display
                EditorGUILayout.TextArea(_displayLocalText ?? "N/A", EditorStyles.textArea, GUILayout.ExpandHeight(true));
                EditorGUILayout.EndScrollView();
                EditorGUILayout.EndVertical();

                // --- Online Text (Specific Template or Message) --- RIGHT SIDE ---
                EditorGUILayout.BeginVertical(GUILayout.ExpandWidth(true));
                EditorGUILayout.LabelField("Online Wiki Text (Relevant Template)", EditorStyles.boldLabel);
                _scrollPosOnline = EditorGUILayout.BeginScrollView(_scrollPosOnline, EditorStyles.helpBox, GUILayout.ExpandHeight(true));
                // Use read-only TextArea for multiline display
                EditorGUILayout.TextArea(_displayOnlineText ?? "N/A", EditorStyles.textArea, GUILayout.ExpandHeight(true));
                EditorGUILayout.EndScrollView();
                EditorGUILayout.EndVertical();

                EditorGUILayout.EndHorizontal();
            }
        }

        private async void CompareItemAsync()
        {
            // Use the value currently in the text field as the Item ID for lookup
            string itemIdToLookup = _itemIdToCompare;

            if (string.IsNullOrWhiteSpace(itemIdToLookup))
            {
                _statusMessage = "Please enter an Item ID (Wiki Page Name).";
                _statusMessageType = MessageType.Warning;
                _displayOnlineText = null;
                _displayLocalText = null;
                Repaint();
                return;
            }

            // Re-check DB existence before proceeding
            if (!File.Exists(_fullDbPathDisplay))
            {
                _statusMessage = "Database file not found. Cannot perform comparison.";
                _statusMessageType = MessageType.Error;
                _displayOnlineText = null;
                _displayLocalText = null;
                Repaint();
                return;
            }

            if (_isComparing) return; // Prevent concurrent comparisons

            _isComparing = true;
            _statusMessage = $"Finding local item data in database for ID: {itemIdToLookup}...";
            _statusMessageType = MessageType.Info;
            _displayOnlineText = null; // Clear previous results
            _displayLocalText = null;  // Clear previous results
            Repaint(); // Update UI to show "Comparing..."

            ItemDBRecord? itemRecord = null; // Define here to use in finally block if needed

            try
            {
                // --- Step 1: Find the local ItemDBRecord from the database ---
                itemRecord = FindItemRecord(itemIdToLookup);

                if (itemRecord == null)
                {
                    // FindItemRecord already updated the status message and logged an error
                    _isComparing = false; // Ensure flag is reset
                    Repaint();
                    return; // Exit early
                }

                // Store raw local string temporarily, but display text will be updated later
                string? rawLocalWikiString = itemRecord.WikiString;
                _displayLocalText = "<Pending Comparison>"; // Placeholder while fetching

                _statusMessage = "Fetching and comparing with online wiki...";
                _statusMessageType = MessageType.Info;
                Repaint();

                // --- Step 2: Perform the comparison ---
                // Use the Item Name for the URL, assuming it matches the wiki page name convention
                string wikiPageName = itemRecord.ItemName.Replace(" ", "_"); // Basic space replacement
                string baseUrl = $"https://erenshor.wiki.gg/wiki/{Uri.EscapeDataString(wikiPageName)}";

                WikiComparator comparator = new WikiComparator();
                // Pass the raw local string to the comparator
                var result = await comparator.CompareWikiStringAsync(baseUrl, rawLocalWikiString);

                // --- Step 3: Display results ---
                // Update display text fields with the specific templates or messages from the result
                _displayOnlineText = result.DisplayOnlineText;
                _displayLocalText = result.DisplayLocalText;

                // Determine final status message and type based on result
                if (result.AreEqual)
                {
                    // Check if ErrorMessage provides context (e.g., local string was empty)
                    // Note: ErrorMessage is null on a successful match now.
                    if (_displayLocalText != null && _displayLocalText.StartsWith("<")) // Check if local text is a status message
                    {
                         _statusMessage = $"Match: {_displayLocalText}"; // e.g., Match: <Local WikiString is empty>
                         _statusMessageType = MessageType.Info;
                    }
                    else
                    {
                        _statusMessage = $"Match: Local template for '{itemRecord.Id}' matches the corresponding online tier.";
                        _statusMessageType = MessageType.Info;
                    }
                }
                else // Not equal
                {
                    // Use the specific error message from the comparator result, which now includes parameter diffs
                    _statusMessage = $"Comparison Failed for '{itemRecord.Id}': {result.ErrorMessage ?? "Unknown reason"}";
                    // Use Error type for fetch failures or missing tiers, Warning for content mismatch
                    if (result.ErrorMessage != null && (result.ErrorMessage.Contains("missing online") || result.ErrorMessage.Contains("Fetch Failed") || result.ErrorMessage.Contains("Internal error")))
                    {
                         _statusMessageType = MessageType.Error;
                    }
                    else
                    {
                        _statusMessageType = MessageType.Warning; // Likely a content mismatch with details
                    }
                }
            }
            catch (SQLiteException sqlEx) // Catch specific SQLite errors during FindItemRecord or elsewhere
            {
                _statusMessage = $"Database Error: {sqlEx.Message}. Ensure the DB exists and is not locked.";
                _statusMessageType = MessageType.Error;
                _displayOnlineText = null; // Clear display on error
                _displayLocalText = null;
                Debug.LogError($"[WikiComparatorWindow] SQLite Error during Wiki Comparison: {sqlEx}");
            }
            catch (Exception ex) // Catch unexpected errors during the process
            {
                _statusMessage = $"An unexpected error occurred: {ex.Message}";
                _statusMessageType = MessageType.Error;
                _displayOnlineText = null; // Clear display on error
                _displayLocalText = null;
                Debug.LogError($"[WikiComparatorWindow] Wiki Comparison Error: {ex}");
            }
            finally
            {
                _isComparing = false;
                Repaint(); // Update UI with final status and text results
            }
        }

        /// <summary>
        /// Finds an ItemDBRecord by its ID (Primary Key) by querying the SQLite database.
        /// Updates status message and logs errors internally if issues occur.
        /// </summary>
        /// <param name="itemId">The ID (Primary Key) of the item to find.</param>
        /// <returns>The ItemDBRecord if found, otherwise null.</returns>
        private ItemDBRecord? FindItemRecord(string itemId)
        {
            // Path existence checked before calling this method in CompareItemAsync

            SQLiteConnection? db = null;
            try
            {
                // Connect in ReadOnly mode
                db = new SQLiteConnection(_fullDbPathDisplay, SQLiteOpenFlags.ReadOnly);

                // Query the Items table for the specific item ID (Primary Key)
                var record = db.Table<ItemDBRecord>().FirstOrDefault(item => item.Id == itemId);

                if (record == null)
                {
                    // Update status directly here since we return null
                    _statusMessage = $"Error: Item with ID '{itemId}' not found in the database '{Path.GetFileName(_fullDbPathDisplay)}'.";
                    _statusMessageType = MessageType.Error;
                    Debug.LogError($"[WikiComparatorWindow] { _statusMessage }");
                }

                return record;
            }
            catch (SQLiteException ex)
            {
                 // Update status directly here since we return null
                _statusMessage = $"Database Query Error: {ex.Message}";
                _statusMessageType = MessageType.Error;
                Debug.LogError($"[WikiComparatorWindow] SQLite error querying for item ID '{itemId}': {ex.Message}\n{ex.StackTrace}");
                return null;
            }
            catch (Exception ex)
            {
                 // Update status directly here since we return null
                _statusMessage = $"Error querying database: {ex.Message}";
                _statusMessageType = MessageType.Error;
                Debug.LogError($"[WikiComparatorWindow] General error querying for item ID '{itemId}': {ex.Message}\n{ex.StackTrace}");
                return null;
            }
            finally
            {
                // Ensure the database connection is closed and disposed
                db?.Close();
                db?.Dispose();
            }
        }
    }
}
