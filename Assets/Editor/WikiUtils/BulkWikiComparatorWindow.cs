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
    private const float DETAIL_VIEW_MIN_HEIGHT = 150f; // Minimum height for the detail view area
    private const float DETAIL_VIEW_MAX_HEIGHT_RATIO = 0.5f; // Max height ratio of window for detail view

    [MenuItem("Tools/Wiki/Bulk Wiki Comparator")]
    public static void ShowWindow()
    {
        BulkWikiComparatorWindow window = GetWindow<BulkWikiComparatorWindow>("Bulk Wiki Comparator");
        window.minSize = new Vector2(800, 500); // Increased min height slightly
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
        _treeView.OnSelectionChangedCallback +=
            OnTreeViewSelectionChanged; // Use the callback to update selection state

        // Set initial sort, but apply it after data load
        if (_multiColumnHeaderState != null && _multiColumnHeaderState.sortedColumns.Length > 0)
        {
            int sortedColumnIndex = _multiColumnHeaderState.sortedColumns[0];
            // Correctly get ascending state from the column itself in the state
            bool ascending = _multiColumnHeaderState.columns[sortedColumnIndex].sortedAscending;
            multiColumnHeader.SetSorting(sortedColumnIndex, ascending);
        }
        else
        {
            multiColumnHeader.SetSorting(1, true); // Default sort: ItemID Ascending
        }
    }

    void InitializeSearchField()
    {
        _searchField ??= new SearchField();
    }

    // --- GUI Drawing ---

    private void OnGUI()
    {
        // Wrap everything in a vertical layout
        EditorGUILayout.BeginVertical();

        // Draw controls first
        DrawTopControls(); // Uses GUILayout internally

        // Then draw the TreeView, allocating space for it
        DrawTreeView(); // Uses GUILayoutUtility.GetRect

        // Finally, draw the DetailView below the TreeView if an item is selected
        DrawDetailView(); // Uses GUILayout internally

        EditorGUILayout.EndVertical();
    }

    private void DrawTopControls()
    {
        // This part remains largely the same, using GUILayout for vertical stacking
        EditorGUILayout.LabelField("Bulk Compare Local Item WikiStrings with Online Wiki Pages",
            EditorStyles.boldLabel);
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
            bool canCompareSelected =
                canCompareAll && _currentSelectionIds.Any(); // Enable only if items are selected and not busy
            EditorGUI.BeginDisabledGroup(!canCompareSelected);
            if (GUILayout.Button($"Compare Selected ({_currentSelectionIds.Count})", GUILayout.Height(30)))
            {
                List<ComparisonResultItem> selectedItems = _comparisonResults
                    .Where(item => _currentSelectionIds.Contains(item.id))
                    .ToList();
                CompareItemsAsync(selectedItems); // Compare only selected items
            }

            EditorGUI.EndDisabledGroup();

            GUILayout.FlexibleSpace();

            // --- Cancel Button ---
            if (_isComparing)
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
            // Use GUILayout version of SearchField
            string currentSearch = _searchField.OnToolbarGUI(_treeView.searchString);
            if (currentSearch != _treeView.searchString)
            {
                _treeView.searchString = currentSearch;
                // TreeView's BuildRows handles filtering, no explicit reload needed here for search
            }
        }

        EditorGUILayout.Space(); // Space before TreeView
    }

    private void DrawTreeView()
    {
        // Determine GUILayout options based on whether the detail view is visible
        GUILayoutOption heightOption = (_selectedItem != null)
            ? GUILayout.MinHeight(position.height * (1f - DETAIL_VIEW_MAX_HEIGHT_RATIO) - 200) // Leave space for controls and detail view
            : GUILayout.ExpandHeight(true); // Expand fully if detail view is hidden


        // Use GUILayoutUtility.GetRect for flexible height allocation
        Rect treeViewRect = GUILayoutUtility.GetRect(
            GUIContent.none,
            GUIStyle.none, // Use GUILayout's default style behavior
            GUILayout.ExpandWidth(true),
            heightOption // Use the calculated height option
        );

        // Draw the TreeView within the allocated rectangle
        _treeView?.OnGUI(treeViewRect);
    }

    private void DrawDetailView()
    {
        // Only draw this section if a single item is selected
        if (_selectedItem == null)
        {
            return; // Don't draw anything if no item is selected
        }

        // Use GUILayout for the detail section below the TreeView
        EditorGUILayout.Space(); // Space between TreeView and DetailView
        EditorGUILayout.LabelField($"Details for: {_selectedItem.ItemName} ({_selectedItem.ItemId})",
            EditorStyles.boldLabel);

        // Calculate max height for detail view based on window size
        float maxDetailHeight = position.height * DETAIL_VIEW_MAX_HEIGHT_RATIO;

        // Use a horizontal scope for side-by-side text areas
        // Request a minimum height and allow expansion up to the max height
        using (EditorGUILayout.HorizontalScope scope = new EditorGUILayout.HorizontalScope(
                   GUILayout.MinHeight(DETAIL_VIEW_MIN_HEIGHT),
                   GUILayout.MaxHeight(maxDetailHeight), // Add MaxHeight constraint
                   GUILayout.ExpandHeight(true))) // Allow vertical expansion within constraints
        {
            // --- Local Text ---
            EditorGUILayout.BeginVertical(GUILayout.ExpandWidth(true));
            EditorGUILayout.LabelField("Local WikiString (Relevant Template)", EditorStyles.miniBoldLabel);
            _scrollPosLocal =
                EditorGUILayout.BeginScrollView(_scrollPosLocal, EditorStyles.helpBox, GUILayout.ExpandHeight(true));

            // Use ReadOnly TextArea for better scroll handling within GUILayout
            string localText = _selectedItem.DisplayLocalText ?? "N/A";
            EditorGUI.BeginDisabledGroup(true); // Make TextArea read-only
            EditorGUILayout.TextArea(localText, EditorStyles.textArea, GUILayout.ExpandHeight(true), GUILayout.ExpandWidth(true));
            EditorGUI.EndDisabledGroup();

            EditorGUILayout.EndScrollView();
            EditorGUILayout.EndVertical();

            // --- Online Text ---
            EditorGUILayout.BeginVertical(GUILayout.ExpandWidth(true));
            EditorGUILayout.LabelField("Online Wiki Text (Relevant Template)", EditorStyles.miniBoldLabel);
            _scrollPosOnline =
                EditorGUILayout.BeginScrollView(_scrollPosOnline, EditorStyles.helpBox, GUILayout.ExpandHeight(true));

            // Use ReadOnly TextArea
            string onlineText = _selectedItem.DisplayOnlineText ?? "N/A";
            EditorGUI.BeginDisabledGroup(true); // Make TextArea read-only
            EditorGUILayout.TextArea(onlineText, EditorStyles.textArea, GUILayout.ExpandHeight(true), GUILayout.ExpandWidth(true));
            EditorGUI.EndDisabledGroup();

            EditorGUILayout.EndScrollView();
            EditorGUILayout.EndVertical();
        }
    }


    // --- Initial List Loading ---
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
        _currentSelectionIds.Clear();
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
                        .Select(item => new ItemDBRecord
                            { Id = item.Id, ItemName = item.ItemName, WikiString = item.WikiString })
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
                    // Apply sorting *after* data is loaded and set
                    if (_treeView?.multiColumnHeader != null)
                    {
                        OnSortingChanged(_treeView.multiColumnHeader);
                    }

                    _treeView?.Reload(); // Reload after sorting potentially changed the order
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
            EditorApplication.delayCall += () =>
            {
                _summaryMessage = "Item list loading cancelled.";
                _isListLoading = false;
                Repaint();
            };
        }
        catch (Exception ex)
        {
            Debug.LogError($"[BulkWikiComparator] Unexpected error during initial list loading setup: {ex}");
            EditorApplication.delayCall += () =>
            {
                _summaryMessage = $"Error loading list: {ex.Message}";
                _isListLoading = false;
                Repaint();
            };
        }
        finally
        {
            // Ensure flag is reset if an exception occurred before delayCall setup
            if (_isListLoading)
            {
                EditorApplication.delayCall += () =>
                {
                    if (_isListLoading)
                    {
                        _isListLoading = false;
                        Repaint();
                    }
                };
            }
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
            _summaryMessage =
                "Cannot start comparison: List loading, already comparing, or no items selected/provided.";
            Repaint();
            return;
        }

        _isComparing = true;
        _progress = 0f;
        _progressMessage = "Preparing comparison...";
        _summaryMessage = $"Starting comparison for {itemsToCompare.Count} item(s)...";
        Repaint();

        // Reset status ONLY for the items being compared
        foreach (var item in itemsToCompare)
        {
            item.Status = ComparisonStatus.Pending;
            item.Details = "Pending comparison...";
            item.DisplayOnlineText = "<Pending>";
            // Reset local display text based on original content
            string initialLocalDisplayText;
            if (string.IsNullOrWhiteSpace(item.LocalWikiString))
            {
                initialLocalDisplayText = "<Local WikiString is empty>";
            }
            else if (!item.LocalWikiString.Contains("{{Fancy-armor") &&
                     !item.LocalWikiString.Contains("{{Fancy-weapon"))
            {
                initialLocalDisplayText = "<No Fancy-armor/weapon template found in local WikiString>";
            }
            else
            {
                initialLocalDisplayText = item.LocalWikiString;
            }

            item.DisplayLocalText = initialLocalDisplayText;
        }

        _treeView?.Reload(); // Show reset state for selected items

        _cancellationTokenSource?.Dispose();
        _cancellationTokenSource = new CancellationTokenSource();
        var token = _cancellationTokenSource.Token;

        await RunComparisonLogicAsync(itemsToCompare, token);
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
        // Use local counters for this run
        int runMatchCount = 0;
        int runMismatchCount = 0;
        int runErrorCount = 0;
        int runLocalEmptyCount = 0;
        int runMissingCount = 0; // Counter for the new 'Missing' status

        try
        {
            using (var semaphore = new SemaphoreSlim(MAX_CONCURRENT_TASKS))
            {
                List<Task> comparisonTasks = new List<Task>();

                foreach (var resultItem in itemsToRun)
                {
                    if (token.IsCancellationRequested) break;

                    await semaphore.WaitAsync(token);

                    if (string.IsNullOrEmpty(resultItem.LocalWikiString))
                    {
                        resultItem.Status = ComparisonStatus.Error;
                        resultItem.Details = "Internal Error: Local WikiString was unexpectedly empty.";
                        Interlocked.Increment(ref runErrorCount);
                        semaphore.Release();
                        Interlocked.Increment(ref processedCount);
                        continue;
                    }

                    comparisonTasks.Add(Task.Run(async () =>
                    {
                        try
                        {
                            if (token.IsCancellationRequested) return;

                            string wikiPageName = resultItem.ItemName.Replace(" ", "_");
                            string baseUrl = $"https://erenshor.wiki.gg/wiki/{Uri.EscapeDataString(wikiPageName)}";
                            var result = await comparator.CompareWikiStringAsync(baseUrl, resultItem.LocalWikiString);

                            resultItem.DisplayOnlineText = result.DisplayOnlineText;
                            resultItem.DisplayLocalText = result.DisplayLocalText;
                            // Set details based on ErrorMessage first, then fallback to Match/Mismatch status
                            resultItem.Details = result.ErrorMessage ?? (result.AreEqual ? "Match" : "Mismatch");


                            if (token.IsCancellationRequested) return;

                            // Determine status based on result
                            if (result.AreEqual)
                            {
                                // Check if it was a match because local was empty/no template
                                if (result.DisplayLocalText != null && result.DisplayLocalText.StartsWith("<"))
                                {
                                    resultItem.Status = ComparisonStatus.LocalEmpty;
                                    Interlocked.Increment(ref runLocalEmptyCount);
                                }
                                else // Includes the Tier 0 special case handled in comparator (where AreEqual is true)
                                {
                                    resultItem.Status = ComparisonStatus.Match;
                                    Interlocked.Increment(ref runMatchCount);
                                }
                            }
                            else // Not Equal
                            {
                                // Check for specific error messages
                                if (result.ErrorMessage != null && result.ErrorMessage.Contains("Page not found on wiki"))
                                {
                                    // Page itself is missing
                                    resultItem.Status = ComparisonStatus.Missing;
                                    Interlocked.Increment(ref runMissingCount);
                                }
                                else if (result.ErrorMessage != null &&
                                         (result.ErrorMessage.Contains("Fetch Failed") ||
                                          result.ErrorMessage.Contains("Internal error") ||
                                          result.ErrorMessage.Contains("HTTP Error") ||
                                          result.ErrorMessage.Contains("Network error") ||
                                          result.ErrorMessage.Contains("timed out") ||
                                          result.ErrorMessage.Contains("Could not parse")))
                                {
                                     // Network, parsing, or other fetch errors
                                    resultItem.Status = ComparisonStatus.Error;
                                    Interlocked.Increment(ref runErrorCount);
                                }
                                else // All other non-equal cases are Mismatches (content diff, tier missing online, etc.)
                                {
                                    resultItem.Status = ComparisonStatus.Mismatch;
                                    Interlocked.Increment(ref runMismatchCount);
                                    // The Details field already contains the specific mismatch reason from ErrorMessage
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

                            // Update progress less frequently to avoid excessive Repaint calls
                            if (currentProcessed % 10 == 0 || currentProcessed == totalItemsToCompare)
                            {
                                EditorApplication.delayCall += () =>
                                {
                                    if (!_isComparing || token.IsCancellationRequested)
                                        return; // Check flags again in delayCall
                                    _progress = (float)currentProcessed / totalItemsToCompare;
                                    _progressMessage =
                                        $"Compared {currentProcessed} of {totalItemsToCompare} items in current run...";
                                    _treeView?.Reload(); // Reload needed to show status updates
                                    Repaint();
                                };
                            }
                        }
                    }, token));
                }

                await Task.WhenAll(comparisonTasks);
            }

            EditorApplication.delayCall += () =>
            {
                string completionScope = (totalItemsToCompare == _comparisonResults.Count) ? "all" : "selected";
                if (token.IsCancellationRequested)
                {
                    _summaryMessage =
                        $"Comparison of {completionScope} items cancelled after processing {processedCount} item(s).";
                }
                else
                {
                    // Update summary message to include 'Missing' count
                    _summaryMessage =
                        $"Comparison of {totalItemsToCompare} {completionScope} item(s) complete. Results -> " +
                        $"Matches: {runMatchCount} | Mismatches: {runMismatchCount} | Missing: {runMissingCount} | " +
                        $"Local Empty: {runLocalEmptyCount} | Errors: {runErrorCount}";
                    _progress = 1.0f;
                    _progressMessage = "Comparison Finished.";
                }

                _treeView?.Reload(); // Final reload to ensure all statuses are shown
                Repaint();
            };
        }
        catch (OperationCanceledException)
        {
            EditorApplication.delayCall += () =>
            {
                _summaryMessage = "Comparison cancelled.";
                Repaint();
            };
        }
        catch (Exception ex)
        {
            Debug.LogError($"[BulkWikiComparator] Unexpected error during comparison run: {ex}");
            EditorApplication.delayCall += () =>
            {
                _summaryMessage = $"An unexpected error occurred: {ex.Message}";
                Repaint();
            };
        }
        finally
        {
            EditorApplication.delayCall += () =>
            {
                _isComparing = false;
                _cancellationTokenSource?.Dispose();
                _cancellationTokenSource = null;
                Repaint();
            };
        }
    }


    private void InitializeResultsList(List<ItemDBRecord> items)
    {
        _comparisonResults = items.Select((item, index) =>
        {
            string initialLocalDisplayText;
            if (string.IsNullOrWhiteSpace(item.WikiString))
            {
                initialLocalDisplayText = "<Local WikiString is empty>";
            }
            else if (!item.WikiString.Contains("{{Fancy-armor") && !item.WikiString.Contains("{{Fancy-weapon"))
            {
                initialLocalDisplayText = "<No Fancy-armor/weapon template found in local WikiString>";
            }
            else
            {
                initialLocalDisplayText = item.WikiString;
            }

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
        // Reload is called within SortItems
    }

    private void OnTreeViewSelectionChanged(IList<int> selectedIds)
    {
        _currentSelectionIds = selectedIds.ToList();

        if (_treeView == null || selectedIds.Count != 1)
        {
            _selectedItem = null;
        }
        else
        {
            _selectedItem = _treeView.GetItemById(selectedIds[0]);
        }

        // No need to clear scroll positions here, keep them for better UX
        Repaint(); // Redraw to update detail view and button states
    }
}

// --- TreeView Data Structures ---

public enum ComparisonStatus
{
    Pending,
    Match,
    Mismatch,
    Missing, // Item/Page exists locally but page not found online (404)
    LocalEmpty, // Special case: Local WikiString was empty or had no template
    Error // Fetch error, parse error, other non-404 network errors etc.
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
        Reload();
    }

    public void SetResults(List<ComparisonResultItem> resultsData)
    {
        _resultsData = resultsData;
        // Reload should be called by the window after setting results and potentially sorting
    }

    public ComparisonResultItem? GetItemById(int id)
    {
        return _resultsData.FirstOrDefault(item => item.id == id);
    }


    protected override TreeViewItem BuildRoot()
    {
        var root = new TreeViewItem { id = -1, depth = -1, displayName = "Root" };
        // Use the current _resultsData directly if it's not null
        var allItems = _resultsData?.Cast<TreeViewItem>().ToList() ?? new List<TreeViewItem>();
        SetupParentsAndChildrenFromDepths(root, allItems);
        return root;
    }

    protected override IList<TreeViewItem> BuildRows(TreeViewItem root)
    {
        // Get the base rows (either all items or sorted items)
        var rows = base.BuildRows(root);

        // Apply search filtering if necessary
        if (!string.IsNullOrEmpty(searchString) && rows != null)
        {
            // Filter the already potentially sorted rows
            var filteredRows = rows
                .Where(item => item is ComparisonResultItem resultItem && DoesItemMatchSearch(resultItem, searchString))
                .ToList();
            return filteredRows;
        }

        return rows ?? new List<TreeViewItem>(); // Return base rows or empty list
    }


    private bool DoesItemMatchSearch(ComparisonResultItem item, string search)
    {
        if (string.IsNullOrEmpty(search)) return true; // No search term means match all
        search = search.ToLowerInvariant();
        // Check against relevant fields
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
            // No need to CenterRectUsingSingleLineHeight for standard LabelFields

            int column = args.GetColumn(i);

            // Apply color coding for specific statuses
            Color originalColor = GUI.color;
            switch(item.Status)
            {
                case ComparisonStatus.Mismatch:
                    GUI.color = new Color(1f, 0.8f, 0.8f); // Light red
                    break;
                case ComparisonStatus.Missing:
                    GUI.color = new Color(1f, 1f, 0.8f); // Light yellow
                    break;
                case ComparisonStatus.Error:
                    GUI.color = new Color(0.9f, 0.9f, 0.9f); // Light gray
                    break;
                case ComparisonStatus.LocalEmpty:
                     GUI.color = new Color(0.8f, 0.9f, 1f); // Light blue
                     break;
                 // Add other cases if needed, e.g., Match, Pending
                 // case ComparisonStatus.Match: GUI.color = Color.green; break;
            }


            switch ((ColumnID)column)
            {
                case ColumnID.Status:
                    // Draw status text instead of icon
                    EditorGUI.LabelField(cellRect, item.Status.ToString());
                    break;

                case ColumnID.ItemID:
                    // Use default LabelField which handles vertical centering
                    EditorGUI.LabelField(cellRect, item.ItemId);
                    break;

                case ColumnID.ItemName:
                    EditorGUI.LabelField(cellRect, item.ItemName);
                    break;

                case ColumnID.Details:
                    // Use miniLabel for potentially long text, it handles clipping
                    EditorGUI.LabelField(cellRect, item.Details, EditorStyles.miniLabel);
                    break;
            }
             GUI.color = originalColor; // Restore original color
        }
    }

    // Method no longer needed
    // private Texture2D GetStatusIcon(ComparisonStatus status) { ... }

    protected override void SelectionChanged(IList<int> selectedIds)
    {
        base.SelectionChanged(selectedIds);
        OnSelectionChangedCallback?.Invoke(selectedIds);
    }

    protected override void KeyEvent()
    {
        // Basic key events like up/down arrow for selection are handled by base
        base.KeyEvent();
    }


    public static MultiColumnHeaderState CreateMultiColumnHeaderState()
    {
        var columns = new[]
        {
            new MultiColumnHeaderState.Column
            {
                // Use text header instead of icon
                headerContent = new GUIContent("Status"),
                contextMenuText = "Status", headerTextAlignment = TextAlignment.Left, // Align left like other text
                // Adjust width for text
                width = 70, minWidth = 60, maxWidth = 100, autoResize = false, allowToggleVisibility = false,
                canSort = true,
                sortedAscending = true
            },
            new MultiColumnHeaderState.Column
            {
                headerContent = new GUIContent("Item ID"), headerTextAlignment = TextAlignment.Left,
                width = 150, minWidth = 100, autoResize = true, allowToggleVisibility = true, canSort = true,
                sortedAscending = true // Default sort for this column
            },
            new MultiColumnHeaderState.Column
            {
                headerContent = new GUIContent("Item Name"), headerTextAlignment = TextAlignment.Left,
                width = 200, minWidth = 100, autoResize = true, allowToggleVisibility = true, canSort = true,
                sortedAscending = true
            },
            new MultiColumnHeaderState.Column
            {
                headerContent = new GUIContent("Details / Error"), headerTextAlignment = TextAlignment.Left,
                width = 350, minWidth = 150, autoResize = true, allowToggleVisibility = true, canSort = true,
                sortedAscending = true
            }
        };

        System.Diagnostics.Debug.Assert(columns.Length == Enum.GetValues(typeof(ColumnID)).Length,
            "Column count mismatch");

        var state = new MultiColumnHeaderState(columns);
        return state;
    }

    public void SortItems(int columnIndex, bool ascending)
    {
        if (_resultsData == null || !_resultsData.Any()) return;

        Comparison<ComparisonResultItem> comparer;
        switch ((ColumnID)columnIndex)
        {
            case ColumnID.Status: comparer = (a, b) => a.Status.CompareTo(b.Status); break;
            case ColumnID.ItemID: comparer = (a, b) => EditorUtility.NaturalCompare(a.ItemId, b.ItemId); break;
            case ColumnID.ItemName:
                comparer = (a, b) => string.Compare(a.ItemName, b.ItemName, StringComparison.OrdinalIgnoreCase); break;
            case ColumnID.Details:
                comparer = (a, b) => string.Compare(a.Details, b.Details, StringComparison.OrdinalIgnoreCase); break;
            default: return;
        }

        _resultsData.Sort((a, b) => ascending ? comparer(a, b) : comparer(b, a));
        Reload(); // Reload the TreeView to reflect the sorted data
    }
}
