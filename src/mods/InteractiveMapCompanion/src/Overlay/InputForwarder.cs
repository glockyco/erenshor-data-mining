using Steamworks;
using UnityEngine;

namespace InteractiveMapCompanion.Overlay;

/// <summary>
/// Translates Unity input events into Steam HTML Surface API calls, forwarding
/// mouse and keyboard interactions to the embedded browser.
///
/// Mouse coordinate mapping: Unity uses bottom-left origin; the browser surface
/// uses top-left origin. We transform via the panel's screen-space rect.
///
/// Input capture: when the overlay is visible and the cursor is over the panel,
/// we forward mouse button events to CEF. Keyboard input is forwarded when the
/// overlay is focused (after a click inside it).
///
/// Drag tracking: MouseMove continues to flow to CEF even when the cursor leaves
/// the panel during a drag, clamped to browser bounds. This ensures MouseUp is
/// always preceded by a MouseMove in the same frame, which some CEF builds require
/// to correctly process the release.
/// </summary>
internal sealed class InputForwarder
{
    private readonly RectTransform _panelRect;
    private int _browserWidth;
    private int _browserHeight;
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

    // Unity mouse button indices → Steam EHTMLMouseButton
    private static readonly EHTMLMouseButton[] ButtonMap =
    [
        EHTMLMouseButton.eHTMLMouseButton_Left,
        EHTMLMouseButton.eHTMLMouseButton_Right,
        EHTMLMouseButton.eHTMLMouseButton_Middle,
    ];

    // Windows virtual key code for Backspace. Unity's KeyCode.Backspace == 8
    // coincidentally matches VK_BACK, but KeyCode values are not Windows VK
    // codes in general — use the explicit constant to make the intent clear
    // and to guard against breakage if additional special keys are ever added.
    private const uint VK_BACK = 0x08;

    internal InputForwarder(RectTransform panelRect, int browserWidth, int browserHeight)
    {
        _panelRect = panelRect;
        _browserWidth = browserWidth;
        _browserHeight = browserHeight;
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
            RectTransformUtility.ScreenPointToLocalPointInRectangle(
                _panelRect,
                Input.mousePosition,
                null, // Screen Space Overlay canvas — no camera needed
                out Vector2 localPoint
            )
        )
        {
            Rect rect = _panelRect.rect;

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
            return;

        int x = (int)Mathf.Clamp(browserPos.x, 0f, _browserWidth - 1);
        int y = (int)Mathf.Clamp(browserPos.y, 0f, _browserHeight - 1);
        SteamHTMLSurface.MouseMove(browser, x, y);
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
                    _focused = false;
                }
            }

            if (Input.GetMouseButtonUp(i) && _buttonsDown[i])
            {
                SteamHTMLSurface.MouseUp(browser, ButtonMap[i]);
                _buttonsDown[i] = false;
            }
        }
    }

    private static void ForwardMouseWheel(HHTMLBrowser browser, bool mouseOver)
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

        foreach (char c in Input.inputString)
        {
            if (c == '\b')
            {
                SteamHTMLSurface.KeyDown(
                    browser,
                    VK_BACK,
                    EHTMLKeyModifiers.k_eHTMLKeyModifier_None,
                    false
                );
                SteamHTMLSurface.KeyUp(browser, VK_BACK, EHTMLKeyModifiers.k_eHTMLKeyModifier_None);
            }
            else if (c != '\0')
            {
                SteamHTMLSurface.KeyChar(browser, c, EHTMLKeyModifiers.k_eHTMLKeyModifier_None);
            }
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

        _focused = false;
    }
}
