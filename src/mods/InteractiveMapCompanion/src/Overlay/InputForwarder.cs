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
/// we consume mouse button events so they don't reach the game. Keyboard input
/// is forwarded when the overlay is focused (after a click inside it).
/// </summary>
internal sealed class InputForwarder
{
    private readonly RectTransform _panelRect;
    private int _browserWidth;
    private int _browserHeight;
    private bool _focused;

    // Unity mouse button indices → Steam EHTMLMouseButton
    private static readonly EHTMLMouseButton[] ButtonMap =
    [
        EHTMLMouseButton.eHTMLMouseButton_Left,
        EHTMLMouseButton.eHTMLMouseButton_Right,
        EHTMLMouseButton.eHTMLMouseButton_Middle,
    ];

    internal InputForwarder(RectTransform panelRect, int browserWidth, int browserHeight)
    {
        _panelRect = panelRect;
        _browserWidth = browserWidth;
        _browserHeight = browserHeight;
    }

    internal void UpdateSize(int width, int height)
    {
        _browserWidth = width;
        _browserHeight = height;
    }

    /// <summary>
    /// Call every frame when the overlay is visible and the browser is ready.
    /// Returns true if the mouse is currently over the panel (caller can use
    /// this to suppress game input handling).
    /// </summary>
    internal bool Tick(HHTMLBrowser browser)
    {
        bool mouseOver = IsMouseOverPanel(out Vector2 browserPos);

        ForwardMouseMove(browser, browserPos, mouseOver);
        ForwardMouseButtons(browser, mouseOver);
        ForwardMouseWheel(browser, mouseOver);
        ForwardKeyboard(browser);

        return mouseOver;
    }

    private bool IsMouseOverPanel(out Vector2 browserPos)
    {
        // RectTransformUtility converts screen point to local rect point
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

    private static void ForwardMouseMove(HHTMLBrowser browser, Vector2 browserPos, bool mouseOver)
    {
        // Only send mouse position when the cursor is inside the panel. Sending
        // it unconditionally every frame can trigger drag/selection behaviour in
        // the browser when combined with stale button-down state.
        if (!mouseOver)
            return;
        SteamHTMLSurface.MouseMove(browser, (int)browserPos.x, (int)browserPos.y);
    }

    private void ForwardMouseButtons(HHTMLBrowser browser, bool mouseOver)
    {
        for (int i = 0; i < ButtonMap.Length; i++)
        {
            if (Input.GetMouseButtonDown(i))
            {
                if (mouseOver)
                    _focused = true;

                if (_focused)
                    SteamHTMLSurface.MouseDown(browser, ButtonMap[i]);
            }
            else if (Input.GetMouseButtonUp(i))
            {
                if (_focused)
                    SteamHTMLSurface.MouseUp(browser, ButtonMap[i]);
            }
        }

        // Lose focus when the user clicks outside the panel
        if (Input.GetMouseButtonDown(0) && !mouseOver)
            _focused = false;
    }

    private static void ForwardMouseWheel(HHTMLBrowser browser, bool mouseOver)
    {
        if (!mouseOver)
            return;

        float scroll = Input.mouseScrollDelta.y;
        if (scroll != 0f)
        {
            // Steam expects delta in "ticks" — 120 per notch is the Windows standard
            SteamHTMLSurface.MouseWheel(browser, (int)(scroll * 120f));
        }
    }

    private void ForwardKeyboard(HHTMLBrowser browser)
    {
        if (!_focused)
            return;

        // Forward printable characters via KeyChar
        foreach (char c in Input.inputString)
        {
            if (c == '\b')
            {
                // Backspace — send as key down/up with no char
                SteamHTMLSurface.KeyDown(
                    browser,
                    (uint)KeyCode.Backspace,
                    EHTMLKeyModifiers.k_eHTMLKeyModifier_None,
                    false
                );
                SteamHTMLSurface.KeyUp(
                    browser,
                    (uint)KeyCode.Backspace,
                    EHTMLKeyModifiers.k_eHTMLKeyModifier_None
                );
            }
            else if (c != '\0')
            {
                SteamHTMLSurface.KeyChar(browser, c, EHTMLKeyModifiers.k_eHTMLKeyModifier_None);
            }
        }
    }

    /// <summary>
    /// Send MouseUp for all buttons to clear any stale press state the browser
    /// may have accumulated while the overlay was hidden. Call this whenever the
    /// overlay becomes visible, before the user has a chance to interact.
    /// </summary>
    internal void ResetMouseState(HHTMLBrowser browser)
    {
        foreach (var button in ButtonMap)
            SteamHTMLSurface.MouseUp(browser, button);
    }

    /// <summary>
    /// Whether the overlay currently has keyboard focus (user clicked inside it).
    /// </summary>
    internal bool HasFocus => _focused;

    /// <summary>
    /// Forcibly clear focus (e.g. when the overlay is hidden).
    /// </summary>
    internal void ClearFocus() => _focused = false;
}
