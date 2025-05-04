using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using UnityEditor;
using UnityEditor.IMGUI.Controls;
using UnityEngine;
using SQLite;

public class BulkWikiComparatorWindow : EditorWindow
{
    // --- Configuration ---
    private const string EXPORTER_PREFS_KEY_DB_PATH = "Erenshor_DatabaseExporter_OutputPath";
    private const string DEFAULT_DB_FILENAME = "Erenshor.sqlite";
    private const int MAX_CONCURRENT_TASKS = 10; // Made constant for easier configuration

    // TreeView state
    [SerializeField] private TreeViewState? _treeViewState;
    [SerializeField] private MultiColumnHeaderState? _multiColumnHeaderState;
    private BulkComparisonTreeView? _treeView;
    private SearchField? _searchField;

    // Window state
    private string _fullDbPathDisplay = "";
    private bool _isComparing = false;
    private bool _isListLoading = false;
    private float _progress = 0f;
    private string _progressMessage = "";
    private string _summaryMessage = "Initializing...";
    private CancellationTokenSource? _cancellationTokenSource;
    private List<ComparisonResultItem> _comparisonResults = new List<ComparisonResultItem>();
    private List<int> _currentSelectionIds = new List<int>(); // Store current selection IDs

    // Detail view state
    private ComparisonResultItem? _selectedItem = null; // Still useful for single-item detail view
    private Vector2 _scrollPosLocal;
    private Vector2 _scrollPosOnline;

    [MenuItem("Tools/Wiki/Bulk Wiki Comparator")]
    public static void ShowWindow()
    {
        BulkWikiComparatorWindow window = GetWindow<BulkWikiComparatorWindow>("Bulk Wiki Comparator");
        window.minSize = new Vector2(800, 500);
    }

    // --- Initialization and Path Handling ---

    void OnEnable()
    {
        UpdateResolvedPath();
        InitializeTreeView();
        InitializeSearchField();
        LoadInitialItemListAsync();
    }

    void OnDisable()
    {
        _cancellationTokenSource?.Cancel();
        _cancellationTokenSource?.Dispose();
        _cancellationTokenSource = null;
    }

    private string GetDefaultDatabasePath()
    {
        return Path.GetFullPath(Path.Combine(Application.dataPath, "..", DEFAULT_DB_FILENAME));
    }

    void UpdateResolvedPath()
    {
        string savedPath = EditorPrefs.GetString(EXPORTER_PREFS_KEY_DB_PATH, GetDefaultDatabasePath());
        _fullDbPathDisplay = Path.GetFullPath(savedPath);
    }

    void InitializeTreeView()
    {
        _treeViewState ??= new TreeViewState();
        var headerState = BulkComparisonTreeView.CreateMultiColumnHeaderState();
        if (MultiColumnHeaderState.CanOverwriteSerializedFields(_multiColumnHeaderState, headerState))
        {
            MultiColumnHeaderState.OverwriteSerializedFields(_multiColumnHeaderState, headerState);
        }
        _multiColumnHeaderState = headerState;

        var multiColumnHeader = new MultiColumnHeader(headerState);
        multiColumnHeader.sortingChanged += OnSortingChanged;

        _treeView = new BulkComparisonTreeView(_treeViewState, multiColumnHeader, _comparisonResults);
        _treeView.OnSelectionChangedCallback += OnTreeViewSelectionChanged; // Use the callback to update selection state

        multiColumnHeader.SetSorting(1, true);
    }

    void InitializeSearchField()
    {
        _searchField ??= new SearchField();
    }

    // --- GUI Drawing ---

    private void OnGUI()
    {
        DrawTopControls();
        DrawTreeView();
        DrawDetailView();
    }

    private void DrawTopControls()
    {
        EditorGUILayout.LabelField("Bulk Compare Local Item WikiStrings with Online Wiki Pages", EditorStyles.boldLabel);
        EditorGUILayout.Space();

        GUILayout.Label("Database Path (Shared with Exporter):", EditorStyles.boldLabel);
        EditorGUILayout.HelpBox(_fullDbPathDisplay, MessageType.None);

        bool dbExists = File.Exists(_fullDbPathDisplay);
        if (!dbExists)
        {
            EditorGUILayout.HelpBox($"Database file not found! Ensure export has run.", MessageType.Error);
        }

        EditorGUILayout.Space();

        // Action Buttons
        using (new EditorGUILayout.HorizontalScope())
        {
            // --- Compare All Button ---
            bool canCompareAll = dbExists && !_isComparing && !_isListLoading && _comparisonResults.Any();
            EditorGUI.BeginDisabledGroup(!canCompareAll);
            string compareAllText = _isComparing ? "Comparing..." : "Compare All";
             if (_isListLoading) compareAllText = "Loading List...";
            if (GUILayout.Button(compareAllText, GUILayout.Height(30)))
            {
                CompareItemsAsync(_comparisonResults); // Compare all items
            }
            EditorGUI.EndDisabledGroup();

            // --- Compare Selected Button ---
            bool canCompareSelected = canCompareAll && _currentSelectionIds.Any(); // Enable only if items are selected and not busy
            EditorGUI.BeginDisabledGroup(!canCompareSelected);
            if (GUILayout.Button($"Compare Selected ({_currentSelectionIds.Count})", GUILayout.Height(30)))
            {
                // Get the actual ComparisonResultItem objects for the selected IDs
                List<ComparisonResultItem> selectedItems = _comparisonResults
                    .Where(item => _currentSelectionIds.Contains(item.id))
                    .ToList();
                CompareItemsAsync(selectedItems); // Compare only selected items
            }
            EditorGUI.EndDisabledGroup();

            // Flexible space to push Cancel button to the right
            GUILayout.FlexibleSpace();

            // --- Cancel Button ---
            if (_isComparing) // Show cancel only during actual comparison
            {
                if (GUILayout.Button("Cancel", GUILayout.Width(80), GUILayout.Height(30)))
                {
                    _cancellationTokenSource?.Cancel();
                }
            }
        }

        // Progress Bar and Message
        if (_isComparing || _progress > 0)
        {
            EditorGUILayout.Space();
            Rect r = EditorGUILayout.GetControlRect(false, EditorGUIUtility.singleLineHeight);
            EditorGUI.ProgressBar(r, _progress, _progressMessage);
            EditorGUILayout.Space();
        }

        // Summary Message
        EditorGUILayout.LabelField("Status:", EditorStyles.boldLabel);
        EditorGUILayout.HelpBox(_summaryMessage, MessageType.Info);
        EditorGUILayout.Space();

        // Search Field
        if (_searchField != null && _treeView != null)
        {
            string currentSearch = _searchField.OnGUI(_treeView.searchString);
            if (currentSearch != _treeView.searchString)
            {
                _treeView.searchString = currentSearch;
            }
        }

        EditorGUILayout.Space();
    }

    private void DrawTreeView()
    {
        float detailViewHeight = _selectedItem != null ? Mathf.Max(200, position.height * 0.3f) : 0;
        Rect treeViewRect = GUILayoutUtility.GetRect(GUIContent.none, GUIStyle.none, GUILayout.ExpandWidth(true), GUILayout.ExpandHeight(true));
        if (detailViewHeight > 0)
        {
            treeViewRect.height -= (detailViewHeight + EditorGUIUtility.standardVerticalSpacing * 2);
        }
        _treeView?.OnGUI(treeViewRect);
    }

    private void DrawDetailView()
    {
        if (_selectedItem == null) return;
        // Detail view logic remains the same...
        EditorGUILayout.Space();
        EditorGUILayout.LabelField($"Details for: {_selectedItem.ItemName} ({_selectedItem.ItemId})", EditorStyles.boldLabel);
        using (EditorGUILayout.HorizontalScope scope = new EditorGUILayout.HorizontalScope(GUILayout.ExpandHeight(true)))
        {
            EditorGUILayout.BeginVertical(GUILayout.ExpandWidth(true));
            EditorGUILayout.LabelField("Local WikiString (Relevant Template)", EditorStyles.miniBoldLabel);
            _scrollPosLocal = EditorGUILayout.BeginScrollView(_scrollPosLocal, EditorStyles.helpBox, GUILayout.ExpandHeight(true));
            EditorGUILayout.TextArea(_selectedItem.DisplayLocalText ?? "N/A", EditorStyles.textArea, GUILayout.ExpandHeight(true));
            EditorGUILayout.EndScrollView();
            EditorGUILayout.EndVertical();

            EditorGUILayout.BeginVertical(GUILayout.ExpandWidth(true));
            EditorGUILayout.LabelField("Online Wiki Text (Relevant Template)", EditorStyles.miniBoldLabel);
            _scrollPosOnline = EditorGUILayout.BeginScrollView(_scrollPosOnline, EditorStyles.helpBox, GUILayout.ExpandHeight(true));
            EditorGUILayout.TextArea(_selectedItem.DisplayOnlineText ?? "N/A", EditorStyles.textArea, GUILayout.ExpandHeight(true));
            EditorGUILayout.EndScrollView();
            EditorGUILayout.EndVertical();
        }
    }


    // --- Initial List Loading ---
    // LoadInitialItemListAsync remains the same as before...
    private async void LoadInitialItemListAsync()
    {
        if (_isListLoading || _isComparing) return;

        if (!File.Exists(_fullDbPathDisplay))
        {
            _summaryMessage = "Database file not found. Cannot load item list.";
            _comparisonResults.Clear();
            _treeView?.SetResults(_comparisonResults);
            _treeView?.Reload();
            Repaint();
            return;
        }

        _isListLoading = true;
        _summaryMessage = "Loading item list from database...";
        _comparisonResults.Clear();
        _treeView?.SetResults(_comparisonResults);
        _treeView?.Reload();
        _selectedItem = null;
        _currentSelectionIds.Clear(); // Clear selection when reloading list
        Repaint();

        _cancellationTokenSource?.Dispose();
        _cancellationTokenSource = new CancellationTokenSource();
        var token = _cancellationTokenSource.Token;

        List<ItemDBRecord>? initialItems = null;
        string? dbError = null;

        try
        {
            await Task.Run(() =>
            {
                SQLiteConnection? db = null;
                try
                {
                    db = new SQLiteConnection(_fullDbPathDisplay, SQLiteOpenFlags.ReadOnly);
                    initialItems = db.Table<ItemDBRecord>()
                                     .Where(item => !string.IsNullOrEmpty(item.WikiString))
                                     .Select(item => new ItemDBRecord { Id = item.Id, ItemName = item.ItemName, WikiString = item.WikiString })
                                     .ToList();
                }
                catch (Exception ex)
                {
                    Debug.LogError($"[BulkWikiComparator] Error querying database for initial list: {ex}");
                    dbError = $"Database Query Error: {ex.Message}";
                    initialItems = null;
                }
                finally
                {
                    db?.Close();
                    db?.Dispose();
                }
            }, token);

            EditorApplication.delayCall += () =>
            {
                if (token.IsCancellationRequested)
                {
                    _summaryMessage = "Item list loading cancelled.";
                }
                else if (dbError != null)
                {
                    _summaryMessage = dbError;
                }
                else if (initialItems != null)
                {
                    InitializeResultsList(initialItems);
                    _treeView?.SetResults(_comparisonResults);
                    OnSortingChanged(_treeView.multiColumnHeader);
                    _treeView?.Reload();
                    _summaryMessage = initialItems.Any()
                        ? $"Ready. Found {initialItems.Count} items with WikiStrings to compare."
                        : "Ready. No items with WikiStrings found in the database.";
                }
                else
                {
                    _summaryMessage = "Failed to load items. Unknown error.";
                }

                _isListLoading = false;
                Repaint();
            };
        }
        catch (OperationCanceledException)
        {
            EditorApplication.delayCall += () => { _summaryMessage = "Item list loading cancelled."; _isListLoading = false; Repaint(); };
        }
        catch (Exception ex)
        {
            Debug.LogError($"[BulkWikiComparator] Unexpected error during initial list loading setup: {ex}");
            EditorApplication.delayCall += () => { _summaryMessage = $"Error loading list: {ex.Message}"; _isListLoading = false; Repaint(); };
        }
        finally
        {
             if (_isListLoading) { EditorApplication.delayCall += () => { if(_isListLoading) { _isListLoading = false; Repaint(); } }; }
        }
    }


    // --- Comparison Logic ---

    /// <summary>
    /// Starts the comparison process for a given list of items.
    /// </summary>
    /// <param name="itemsToCompare">The specific items to compare.</param>
    private async void CompareItemsAsync(IList<ComparisonResultItem> itemsToCompare)
    {
        if (_isListLoading || _isComparing || itemsToCompare == null || !itemsToCompare.Any())
        {
            _summaryMessage = "Cannot start comparison: List loading, already comparing, or no items selected/provided.";
            Repaint();
            return;
        }

        _isComparing = true;
        _progress = 0f;
        _progressMessage = "Preparing comparison...";
        _summaryMessage = $"Starting comparison for {itemsToCompare.Count} item(s)...";
        // Don't clear _selectedItem here, user might want to keep detail view open
        Repaint();

        // Reset status ONLY for the items being compared
        foreach (var item in itemsToCompare)
        {
            item.Status = ComparisonStatus.Pending;
            item.Details = "Pending comparison...";
            item.DisplayOnlineText = "<Pending>";
            item.DisplayLocalText = item.LocalWikiString; // Reset to original local string
             if (string.IsNullOrWhiteSpace(item.DisplayLocalText)) item.DisplayLocalText = "<Local WikiString is empty>";
             else if (!item.DisplayLocalText.Contains("{{Fancy-armor") && !item.DisplayLocalText.Contains("{{Fancy-weapon")) item.DisplayLocalText = "<No Fancy-armor/weapon template found in local WikiString>";
        }
        _treeView?.Reload(); // Show reset state for selected items

        _cancellationTokenSource?.Dispose();
        _cancellationTokenSource = new CancellationTokenSource();
        var token = _cancellationTokenSource.Token;

        // Run the core comparison logic
        await RunComparisonLogicAsync(itemsToCompare, token);

        // Final state reset is handled within RunComparisonLogicAsync's finally block
    }

    /// <summary>
    /// Contains the core asynchronous loop for comparing items against the wiki.
    /// </summary>
    /// <param name="itemsToRun">The list of items to process.</param>
    /// <param name="token">Cancellation token.</param>
    private async Task RunComparisonLogicAsync(IList<ComparisonResultItem> itemsToRun, CancellationToken token)
    {
        WikiComparator comparator = new WikiComparator();
        int totalItemsToCompare = itemsToRun.Count;
        int processedCount = 0;
        // Use local counters for this run, don't rely on window-level counters if multiple partial runs are possible
        int runMatchCount = 0;
        int runMismatchCount = 0;
        int runErrorCount = 0;
        int runLocalEmptyCount = 0;

        try
        {
            using (var semaphore = new SemaphoreSlim(MAX_CONCURRENT_TASKS))
            {
                List<Task> comparisonTasks = new List<Task>();

                foreach (var resultItem in itemsToRun) // Iterate only through the provided list
                {
                    if (token.IsCancellationRequested) break;

                    await semaphore.WaitAsync(token);

                    // Skip items that don't have a local WikiString (safety check)
                    if (string.IsNullOrEmpty(resultItem.LocalWikiString))
                    {
                        resultItem.Status = ComparisonStatus.Error;
                        resultItem.Details = "Internal Error: Local WikiString was unexpectedly empty.";
                        Interlocked.Increment(ref runErrorCount);
                        semaphore.Release();
                        Interlocked.Increment(ref processedCount);
                        continue;
                    }

                    comparisonTasks.Add(Task.Run(async () => // No need for <Task> here
                    {
                        try
                        {
                            if (token.IsCancellationRequested) return;

                            string wikiPageName = resultItem.ItemName.Replace(" ", "_");
                            string baseUrl = $"https://erenshor.wiki.gg/wiki/{Uri.EscapeDataString(wikiPageName)}";
                            var result = await comparator.CompareWikiStringAsync(baseUrl, resultItem.LocalWikiString);

                            resultItem.DisplayOnlineText = result.DisplayOnlineText;
                            resultItem.DisplayLocalText = result.DisplayLocalText;
                            resultItem.Details = result.ErrorMessage ?? (result.AreEqual ? "Match" : "Mismatch");

                            if (token.IsCancellationRequested) return;

                            if (result.AreEqual)
                            {
                                if (result.DisplayLocalText != null && result.DisplayLocalText.StartsWith("<"))
                                {
                                    resultItem.Status = ComparisonStatus.LocalEmpty;
                                    Interlocked.Increment(ref runLocalEmptyCount);
                                }
                                else
                                {
                                    resultItem.Status = ComparisonStatus.Match;
                                    Interlocked.Increment(ref runMatchCount);
                                }
                            }
                            else
                            {
                                if (result.ErrorMessage != null &&
                                    (result.ErrorMessage.Contains("missing online") ||
                                     result.ErrorMessage.Contains("Fetch Failed") ||
                                     result.ErrorMessage.Contains("Internal error") ||
                                     result.ErrorMessage.Contains("not found on wiki")))
                                {
                                    resultItem.Status = ComparisonStatus.Error;
                                    Interlocked.Increment(ref runErrorCount);
                                }
                                else
                                {
                                    resultItem.Status = ComparisonStatus.Mismatch;
                                    Interlocked.Increment(ref runMismatchCount);
                                }
                            }
                        }
                        catch (Exception ex)
                        {
                            Debug.LogError($"[BulkWikiComparator] Error comparing item {resultItem.ItemId}: {ex}");
                            resultItem.Status = ComparisonStatus.Error;
                            resultItem.Details = $"Unexpected Error: {ex.Message}";
                            Interlocked.Increment(ref runErrorCount);
                        }
                        finally
                        {
                            semaphore.Release();
                            int currentProcessed = Interlocked.Increment(ref processedCount);

                            if (currentProcessed % 5 == 0 || currentProcessed == totalItemsToCompare)
                            {
                                EditorApplication.delayCall += () =>
                                {
                                    if (!_isComparing) return;
                                    _progress = (float)currentProcessed / totalItemsToCompare;
                                    _progressMessage = $"Compared {currentProcessed} of {totalItemsToCompare} items in current run...";
                                    _treeView?.Reload();
                                    Repaint();
                                };
                            }
                        }
                    }, token));
                } // End foreach

                await Task.WhenAll(comparisonTasks);
            } // End using semaphore

            // Final summary update on main thread
            EditorApplication.delayCall += () =>
            {
                string completionScope = (totalItemsToCompare == _comparisonResults.Count) ? "all" : "selected";
                if (token.IsCancellationRequested)
                {
                    _summaryMessage = $"Comparison of {completionScope} items cancelled after processing {processedCount} item(s).";
                }
                else
                {
                    _summaryMessage = $"Comparison of {totalItemsToCompare} {completionScope} item(s) complete. Results -> Matches: {runMatchCount} | Mismatches: {runMismatchCount} | Local Empty: {runLocalEmptyCount} | Errors: {runErrorCount}";
                    _progress = 1.0f;
                    _progressMessage = "Comparison Finished.";
                }
                _treeView?.Reload();
                Repaint();
            };
        }
        catch (OperationCanceledException)
        {
            EditorApplication.delayCall += () => { _summaryMessage = "Comparison cancelled."; Repaint(); };
        }
        catch (Exception ex)
        {
            Debug.LogError($"[BulkWikiComparator] Unexpected error during comparison run: {ex}");
            EditorApplication.delayCall += () => { _summaryMessage = $"An unexpected error occurred: {ex.Message}"; Repaint(); };
        }
        finally
        {
            // Ensure state is reset regardless of how the process ended
            EditorApplication.delayCall += () =>
            {
                _isComparing = false; // Crucial: Reset the main comparison flag
                _cancellationTokenSource?.Dispose();
                _cancellationTokenSource = null;
                Repaint(); // Re-enable buttons etc.
            };
        }
    }


    // InitializeResultsList remains the same...
    private void InitializeResultsList(List<ItemDBRecord> items)
    {
        _comparisonResults = items.Select((item, index) =>
        {
             string initialLocalDisplayText;
             if (string.IsNullOrWhiteSpace(item.WikiString)) { initialLocalDisplayText = "<Local WikiString is empty>"; }
             else if (!item.WikiString.Contains("{{Fancy-armor") && !item.WikiString.Contains("{{Fancy-weapon")) { initialLocalDisplayText = "<No Fancy-armor/weapon template found in local WikiString>"; }
             else { initialLocalDisplayText = item.WikiString; }

             return new ComparisonResultItem(index)
             {
                 ItemId = item.Id, ItemName = item.ItemName, Status = ComparisonStatus.Pending,
                 Details = "Pending comparison...", LocalWikiString = item.WikiString,
                 DisplayLocalText = initialLocalDisplayText, DisplayOnlineText = "<Pending>"
             };
        }).ToList();
    }

    // --- TreeView Event Handlers ---

    private void OnSortingChanged(MultiColumnHeader multiColumnHeader)
    {
        if (_treeView == null || !_comparisonResults.Any()) return;
        var sortedColumns = multiColumnHeader.state.sortedColumns;
        if (sortedColumns.Length == 0) return;
        var sortedColumnIndex = sortedColumns[0];
        var ascending = multiColumnHeader.IsSortedAscending(sortedColumnIndex);
        _treeView.SortItems(sortedColumnIndex, ascending);
        _treeView.Reload();
    }

    private void OnTreeViewSelectionChanged(IList<int> selectedIds)
    {
        // Update the stored selection list
        _currentSelectionIds = selectedIds.ToList();

        // Update the single selected item for the detail view
        if (_treeView == null || selectedIds.Count != 1) // Show detail only for single selection
        {
            _selectedItem = null;
        }
        else
        {
            _selectedItem = _treeView.GetItemById(selectedIds[0]);
        }

        // Clear scroll positions when selection changes
        _scrollPosLocal = Vector2.zero;
        _scrollPosOnline = Vector2.zero;
        Repaint(); // Redraw to update button states and detail view
    }
}

// --- TreeView Data Structures ---

public enum ComparisonStatus
{
    Pending,
    Match,
    Mismatch,
    LocalEmpty, // Special case: Local WikiString was empty or had no template
    Error // Fetch error, parse error, item not found etc.
}

// Represents a single row in the TreeView
public class ComparisonResultItem : TreeViewItem
{
    public string ItemId { get; set; } = "";
    public string ItemName { get; set; } = "";
    public ComparisonStatus Status { get; set; } = ComparisonStatus.Pending;
    public string Details { get; set; } = ""; // Error message or mismatch details
    public string? LocalWikiString { get; set; } // Original local string
    public string? DisplayOnlineText { get; set; } // Text to display in detail view (online)
    public string? DisplayLocalText { get; set; } // Text to display in detail view (local)


    public ComparisonResultItem(int id) : base(id, 0) // id, depth
    {
    }
}

// --- TreeView Implementation ---

public class BulkComparisonTreeView : TreeView
{
    private List<ComparisonResultItem> _resultsData; // Reference to the main list

    // Column identifiers
    enum ColumnID
    {
        Status,
        ItemID,
        ItemName,
        Details
    }

    public Action<IList<int>>? OnSelectionChangedCallback { get; set; }


    public BulkComparisonTreeView(TreeViewState state, MultiColumnHeader multiColumnHeader,
        List<ComparisonResultItem> resultsData)
        : base(state, multiColumnHeader)
    {
        _resultsData = resultsData;
        showAlternatingRowBackgrounds = true;
        showBorder = true;
        multiColumnHeader.sortingChanged += (header) =>
        {
            /* Handled by window */
        }; // Sorting logic is in the window
        Reload();
    }

    public void SetResults(List<ComparisonResultItem> resultsData)
    {
        _resultsData = resultsData;
        // Don't Reload() here, let the caller decide when to reload (e.g., after populating or after sorting)
    }

    public ComparisonResultItem? GetItemById(int id)
    {
        // Find the item in our data source that corresponds to the TreeViewItem id
        return _resultsData.FirstOrDefault(item => item.id == id);
    }


    protected override TreeViewItem BuildRoot()
    {
        var root = new TreeViewItem { id = -1, depth = -1, displayName = "Root" };
        var allItems = new List<TreeViewItem>();

        if (_resultsData != null)
        {
            foreach (var resultItem in _resultsData)
            {
                // The ComparisonResultItem itself inherits from TreeViewItem
                allItems.Add(resultItem);
            }
        }

        SetupParentsAndChildrenFromDepths(root, allItems);
        return root;
    }

    protected override IList<TreeViewItem> BuildRows(TreeViewItem root)
    {
        // If search string is active, filter the data
        if (!string.IsNullOrEmpty(searchString))
        {
            var filteredData = _resultsData
                .Where(item => DoesItemMatchSearch(item, searchString))
                .Cast<TreeViewItem>() // Cast back to base type for BuildRows
                .ToList();

            // Need to rebuild the parent/child relationship for the filtered list
            // Since it's a flat list, just return the filtered items.
            // If there was hierarchy, SetupParentsAndChildrenFromDepths would be needed here.
            return filteredData;
        }
        else
        {
            // No search, return all items from the root
            return base.BuildRows(root); // Use default BuildRows if no search
        }
    }

    private bool DoesItemMatchSearch(ComparisonResultItem item, string search)
    {
        search = search.ToLowerInvariant();
        return item.ItemId.ToLowerInvariant().Contains(search) ||
               item.ItemName.ToLowerInvariant().Contains(search) ||
               item.Status.ToString().ToLowerInvariant().Contains(search) ||
               item.Details.ToLowerInvariant().Contains(search);
    }

    protected override void RowGUI(RowGUIArgs args)
    {
        var item = args.item as ComparisonResultItem;
        if (item == null) return;

        for (int i = 0; i < args.GetNumVisibleColumns(); ++i)
        {
            Rect cellRect = args.GetCellRect(i);
            CenterRectUsingSingleLineHeight(ref cellRect); // Adjust rect vertically for text

            int column = args.GetColumn(i);

            switch ((ColumnID)column)
            {
                case ColumnID.Status:
                    Texture2D statusIcon = GetStatusIcon(item.Status);
                    if (statusIcon != null)
                    {
                        // Center the icon vertically, keep it small
                        float iconSize = EditorGUIUtility.singleLineHeight;
                        Rect iconRect = new Rect(cellRect.x + 2, cellRect.y + (cellRect.height - iconSize) / 2,
                            iconSize, iconSize);
                        GUI.DrawTexture(iconRect, statusIcon, ScaleMode.ScaleToFit);
                    }

                    // Optionally draw status text next to icon if space allows
                    // EditorGUI.LabelField(new Rect(cellRect.x + iconSize + 4, cellRect.y, cellRect.width - iconSize - 4, cellRect.height), item.Status.ToString());
                    break;

                case ColumnID.ItemID:
                    EditorGUI.LabelField(cellRect, item.ItemId);
                    break;

                case ColumnID.ItemName:
                    EditorGUI.LabelField(cellRect, item.ItemName);
                    break;

                case ColumnID.Details:
                    // Use a style that handles clipping better for potentially long text
                    EditorGUI.LabelField(cellRect, item.Details, EditorStyles.miniLabel);
                    break;
            }
        }
    }

    private Texture2D GetStatusIcon(ComparisonStatus status)
    {
        switch (status)
        {
            case ComparisonStatus.Match:
                return EditorGUIUtility.IconContent("TestPassed").image as Texture2D;
            case ComparisonStatus.Mismatch:
                return EditorGUIUtility.IconContent("TestFailed").image as Texture2D;
            case ComparisonStatus.Error:
                return EditorGUIUtility.IconContent("TestIgnored").image as Texture2D; // Or "Error" icon
            case ComparisonStatus.LocalEmpty:
                return EditorGUIUtility.IconContent("Warning").image as Texture2D; // Indicate non-standard match
            case ComparisonStatus.Pending:
                return EditorGUIUtility.IconContent("WaitSpin00").image as Texture2D; // Animated pending icon
            default:
                return null;
        }
    }

    // Handle selection changes and notify the window
    protected override void SelectionChanged(IList<int> selectedIds)
    {
        base.SelectionChanged(selectedIds);
        OnSelectionChangedCallback?.Invoke(selectedIds);
    }

    // Allow focusing the TreeView via keyboard (e.g., from search field)
    protected override void KeyEvent()
    {
        if (Event.current.keyCode == KeyCode.Return && HasSelection())
        {
            // Optional: Define action on Enter key (e.g., open item details?)
        }
        else
        {
            base.KeyEvent();
        }
    }


    // Define columns
    public static MultiColumnHeaderState CreateMultiColumnHeaderState()
    {
        var columns = new[]
        {
            new MultiColumnHeaderState.Column
            {
                headerContent =
                    new GUIContent(EditorGUIUtility.IconContent("TestPassed").image,
                        "Status"), // Use icon for header too
                contextMenuText = "Status",
                headerTextAlignment = TextAlignment.Center,
                sortedAscending = true,
                sortingArrowAlignment = TextAlignment.Right,
                width = 40, minWidth = 40, maxWidth = 60,
                autoResize = false, allowToggleVisibility = false, canSort = true
            },
            new MultiColumnHeaderState.Column
            {
                headerContent = new GUIContent("Item ID"),
                headerTextAlignment = TextAlignment.Left,
                sortedAscending = true,
                sortingArrowAlignment = TextAlignment.Center,
                width = 150, minWidth = 100,
                autoResize = true, allowToggleVisibility = true, canSort = true
            },
            new MultiColumnHeaderState.Column
            {
                headerContent = new GUIContent("Item Name"),
                headerTextAlignment = TextAlignment.Left,
                sortedAscending = true,
                sortingArrowAlignment = TextAlignment.Center,
                width = 200, minWidth = 100,
                autoResize = true, allowToggleVisibility = true, canSort = true
            },
            new MultiColumnHeaderState.Column
            {
                headerContent = new GUIContent("Details / Error"),
                headerTextAlignment = TextAlignment.Left,
                sortedAscending = true,
                sortingArrowAlignment = TextAlignment.Left,
                width = 350, minWidth = 150,
                autoResize = true, allowToggleVisibility = true, canSort = true
            }
        };

        // Ensure column names match enum for safety, though indices are used here
        System.Diagnostics.Debug.Assert(columns.Length == Enum.GetValues(typeof(ColumnID)).Length,
            "Number of columns defined must match ColumnID enum.");

        var state = new MultiColumnHeaderState(columns);
        return state;
    }

    // Sorting Logic
    public void SortItems(int columnIndex, bool ascending)
    {
        if (_resultsData == null || !_resultsData.Any()) return;

        Comparison<ComparisonResultItem> comparer;

        switch ((ColumnID)columnIndex)
        {
            case ColumnID.Status:
                comparer = (a, b) => a.Status.CompareTo(b.Status);
                break;
            case ColumnID.ItemID:
                comparer = (a, b) =>
                    EditorUtility.NaturalCompare(a.ItemId,
                        b.ItemId); // Natural compare for IDs like "Item1", "Item10"
                break;
            case ColumnID.ItemName:
                comparer = (a, b) => string.Compare(a.ItemName, b.ItemName, StringComparison.OrdinalIgnoreCase);
                break;
            case ColumnID.Details:
                comparer = (a, b) => string.Compare(a.Details, b.Details, StringComparison.OrdinalIgnoreCase);
                break;
            default:
                return; // Unknown column
        }

        _resultsData.Sort((a, b) => ascending ? comparer(a, b) : comparer(b, a));

        // Important: After sorting the data source, you need to tell the TreeView to rebuild its internal representation.
        Reload();
    }
}
