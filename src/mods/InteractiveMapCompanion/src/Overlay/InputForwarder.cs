using Steamworks;
using UnityEngine;

namespace InteractiveMapCompanion.Overlay;

/// <summary>
/// Translates Unity input events into Steam HTML Surface API calls, forwarding
/// mouse and keyboard interactions to the embedded browser.
///
/// Mouse coordinate mapping: Unity uses bottom-left origin; the browser surface
/// uses top-left origin. We transform via the browser content region's screen-space rect,
/// excluding the persistent Unity toolbar.
///
/// Input capture: when the overlay is visible and the cursor is over the panel,
/// we forward mouse button events to CEF. Keyboard input is forwarded when the
/// overlay is focused (after a click inside it). Toolbar clicks remain outside the
/// browser hit region and are handled exclusively by Unity UI.
///
/// Drag tracking: MouseMove continues to flow to CEF even when the cursor leaves
/// the panel during a drag, clamped to browser bounds. This ensures MouseUp is
/// always preceded by a MouseMove in the same frame, which some CEF builds require
/// to correctly process the release.
/// </summary>
internal sealed class InputForwarder
{
    private readonly RectTransform _contentRect;
    private readonly RectTransform _excludedRect;
    private readonly Action _goBack;
    private readonly Action _goForward;
    private int _browserWidth;
    private int _browserHeight;
    private int _lastMouseX;
    private int _lastMouseY;
    private bool _hasMousePosition;
    private bool _focused;

    // Tracks which buttons we sent MouseDown for, so every MouseDown has a
    // matching MouseUp even if the cursor left the panel between press and
    // release (e.g. panning the map).
    private readonly bool[] _buttonsDown = new bool[3];

    // True when at least one tracked button is currently held down. Used to
    // keep MouseMove flowing to CEF during drags that exit the panel boundary.
    private bool AnyButtonDown
    {
        get
        {
            foreach (bool b in _buttonsDown)
                if (b)
                    return true;
            return false;
        }
    }

    // Unity mouse button indices → Steam EHTMLMouseButton (buttons 0–2 only;
    // buttons 3 and 4 are the side buttons handled separately as GoBack/GoForward)
    private static readonly EHTMLMouseButton[] ButtonMap =
    [
        EHTMLMouseButton.eHTMLMouseButton_Left,
        EHTMLMouseButton.eHTMLMouseButton_Right,
        EHTMLMouseButton.eHTMLMouseButton_Middle,
    ];

    internal InputForwarder(
        RectTransform contentRect,
        RectTransform excludedRect,
        int browserWidth,
        int browserHeight,
        Action goBack,
        Action goForward
    )
    {
        _contentRect = contentRect;
        _excludedRect = excludedRect;
        _browserWidth = browserWidth;
        _browserHeight = browserHeight;
        _goBack = goBack;
        _goForward = goForward;
    }

    /// <summary>
    /// Call every frame when the overlay is visible and the browser is ready.
    /// </summary>
    internal void Tick(HHTMLBrowser browser)
    {
        bool mouseOver = IsMouseOverPanel(out Vector2 browserPos);

        ForwardMouseMove(browser, browserPos, mouseOver);
        ForwardMouseButtons(browser, mouseOver);
        ForwardMouseWheel(browser, mouseOver);
        ForwardKeyboard(browser);
    }

    private bool IsMouseOverPanel(out Vector2 browserPos)
    {
        if (
            RectTransformUtility.RectangleContainsScreenPoint(
                _excludedRect,
                Input.mousePosition,
                null
            )
        )
        {
            browserPos = Vector2.zero;
            return false;
        }

        if (
            RectTransformUtility.ScreenPointToLocalPointInRectangle(
                _contentRect,
                Input.mousePosition,
                null, // Screen Space Overlay canvas — no camera needed
                out Vector2 localPoint
            )
        )
        {
            Rect rect = _contentRect.rect;

            // localPoint is in local rect space: (0,0) = pivot, not corner.
            // Normalise to [0,1] across the rect, then flip Y for browser coords.
            float normX = (localPoint.x - rect.xMin) / rect.width;
            float normY = (localPoint.y - rect.yMin) / rect.height;

            bool inside = normX >= 0f && normX <= 1f && normY >= 0f && normY <= 1f;

            // Browser is top-left origin, so flip Y
            browserPos = new Vector2(normX * _browserWidth, (1f - normY) * _browserHeight);
            return inside;
        }

        browserPos = Vector2.zero;
        return false;
    }

    private void ForwardMouseMove(HHTMLBrowser browser, Vector2 browserPos, bool mouseOver)
    {
        // Continue sending MouseMove while a button is held even if the cursor
        // has left the panel, clamping to browser bounds. This ensures MouseUp
        // is always preceded by MouseMove in the same frame.
        if (!mouseOver && !AnyButtonDown)
        {
            _hasMousePosition = false;
            return;
        }

        int x = (int)Mathf.Clamp(browserPos.x, 0f, _browserWidth - 1);
        int y = (int)Mathf.Clamp(browserPos.y, 0f, _browserHeight - 1);
        if (_hasMousePosition && x == _lastMouseX && y == _lastMouseY)
            return;

        SteamHTMLSurface.MouseMove(browser, x, y);
        _lastMouseX = x;
        _lastMouseY = y;
        _hasMousePosition = true;
    }

    private void ForwardMouseButtons(HHTMLBrowser browser, bool mouseOver)
    {
        for (int i = 0; i < ButtonMap.Length; i++)
        {
            if (Input.GetMouseButtonDown(i))
            {
                if (mouseOver)
                {
                    _focused = true;
                    // Guard against sending a second MouseDown without a
                    // matching MouseUp. This can happen when the input system
                    // is wrapped (e.g. UniverseLib) and fires GetMouseButtonDown
                    // twice for a single physical click.
                    if (!_buttonsDown[i])
                        SteamHTMLSurface.MouseDown(browser, ButtonMap[i]);
                    _buttonsDown[i] = true;
                }
                else
                {
                    // Toolbar and outside-overlay clicks both leave the HTML
                    // surface. Unity UI owns keyboard submit events while one
                    // of its toolbar buttons is selected.
                    _focused = false;
                }
            }

            if (Input.GetMouseButtonUp(i) && _buttonsDown[i])
            {
                SteamHTMLSurface.MouseUp(browser, ButtonMap[i]);
                _buttonsDown[i] = false;
            }
        }

        // Side mouse buttons: back (button 3) and forward (button 4).
        // These are not draggable — forward them as instant navigation commands.
        if (mouseOver && Input.GetMouseButtonDown(3))
            _goBack();

        if (mouseOver && Input.GetMouseButtonDown(4))
            _goForward();
    }

    private void ForwardMouseWheel(HHTMLBrowser browser, bool mouseOver)
    {
        if (!mouseOver)
            return;

        float scroll = Input.mouseScrollDelta.y;
        if (scroll != 0f)
        {
            // Clamp to ±3 notches per frame to prevent touchpad inertia from
            // scrolling the map multiple zoom steps in a single frame. 120 per
            // notch matches the WM_MOUSEWHEEL WHEEL_DELTA convention CEF expects.
            int delta = (int)(Mathf.Clamp(scroll, -3f, 3f) * 120f);
            SteamHTMLSurface.MouseWheel(browser, delta);
        }
    }

    private void ForwardKeyboard(HHTMLBrowser browser)
    {
        if (!_focused)
            return;

        // Alt+Left / Alt+Right → browser back / forward (Windows convention).
        // Cmd+Left / Cmd+Right → browser back / forward (macOS convention).
        // Both call GoBack/GoForward directly to avoid VK translation issues
        // through CrossOver and Wine.
        bool altDown =
            Input.GetKey(KeyCode.LeftAlt)
            || Input.GetKey(KeyCode.RightAlt)
            || Input.GetKey(KeyCode.LeftMeta)
            || Input.GetKey(KeyCode.RightMeta);
        if (altDown && Input.GetKeyDown(KeyCode.LeftArrow))
            _goBack();
        if (altDown && Input.GetKeyDown(KeyCode.RightArrow))
            _goForward();

        // Printable characters via Input.inputString, which handles IME composition,
        // dead keys, and platform differences. Skip \b (backspace) and \0 (null).
        foreach (char c in Input.inputString)
        {
            if (c != '\b' && c != '\0')
                SteamHTMLSurface.KeyChar(browser, c, EHTMLKeyModifiers.k_eHTMLKeyModifier_None);
        }
    }

    /// <summary>
    /// Send MouseUp for all buttons we actually pressed and clear focus. Call
    /// when the overlay is shown or hidden, or when the application loses OS
    /// focus (prevents stuck button state after alt-tab).
    /// </summary>
    internal void ResetMouseState(HHTMLBrowser browser)
    {
        for (int i = 0; i < ButtonMap.Length; i++)
        {
            if (_buttonsDown[i])
            {
                SteamHTMLSurface.MouseUp(browser, ButtonMap[i]);
                _buttonsDown[i] = false;
            }
        }

        _hasMousePosition = false;
        _focused = false;
    }
}
