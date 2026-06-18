namespace AdventureGuide.State;

/// <summary>
/// Browser-like back/forward navigation history for quest guide pages.
/// Uses a list with cursor index for simple max-size eviction.
/// Designed as a foundation for future page types beyond quests.
/// </summary>
public sealed class NavigationHistory
{
    public enum PageType { Quest }

    public readonly struct PageRef
    {
        public readonly PageType Type;
        public readonly string Key;

        public PageRef(PageType type, string key)
        {
            Type = type;
            Key = key;
        }
    }

    private readonly List<PageRef> _pages = new();
    private int _cursor = -1; // points at current page
    private int _maxSize;

    public NavigationHistory(int maxSize = 100)
    {
        _maxSize = maxSize;
    }

    public bool CanGoBack => _cursor > 0;
    public bool CanGoForward => _cursor < _pages.Count - 1;
    public int MaxSize { get => _maxSize; set => _maxSize = Math.Max(1, value); }

    /// <summary>
    /// Navigate to a new page. Truncates any forward history and
    /// evicts oldest entries if over max size.
    /// </summary>
    public void Navigate(PageRef page)
    {
        // Don't push duplicate of current page
        if (_cursor >= 0 && _cursor < _pages.Count)
        {
            var current = _pages[_cursor];
            if (current.Type == page.Type && current.Key == page.Key)
                return;
        }

        // Truncate forward history
        if (_cursor < _pages.Count - 1)
            _pages.RemoveRange(_cursor + 1, _pages.Count - _cursor - 1);

        _pages.Add(page);
        _cursor = _pages.Count - 1;

        // Evict oldest if over max size
        while (_pages.Count > _maxSize)
        {
            _pages.RemoveAt(0);
            _cursor--;
        }
    }

    /// <summary>Go back. Returns the previous page.</summary>
    public PageRef? Back()
    {
        if (!CanGoBack) return null;
        _cursor--;
        return _pages[_cursor];
    }

    /// <summary>Go forward. Returns the next page.</summary>
    public PageRef? Forward()
    {
        if (!CanGoForward) return null;
        _cursor++;
        return _pages[_cursor];
    }

    public void Clear()
    {
        _pages.Clear();
        _cursor = -1;
    }
}
