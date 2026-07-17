using UnityEngine;
using UnityEngine.UI;

namespace InteractiveMapCompanion.Overlay;

/// <summary>
/// Compact Unity UI navigation layered over the embedded browser surface.
/// </summary>
internal sealed class BrowserNavigationToolbar
{
    private const int ControlWidth = 240;
    private const int ControlHeight = 32;
    private const int TopInset = 10;
    private const int BorderThickness = 1;
    private const int HorizontalPadding = 4;
    private const int ButtonGap = 4;
    private const int BackButtonWidth = 72;
    private const int ForwardButtonWidth = 88;
    private const int MapButtonWidth = 62;
    private const int LabelSize = 13;

    private static readonly Color ToolbarBorder = new Color32(67, 81, 95, 170);
    private static readonly Color ToolbarBackground = new Color32(8, 12, 18, 220);
    private static readonly Color ButtonNormal = new Color32(25, 33, 43, 230);
    private static readonly Color MapButtonNormal = new Color32(25, 53, 64, 240);
    private static readonly Color ButtonHover = new Color32(26, 73, 86, 255);
    private static readonly Color ButtonPressed = new Color32(15, 47, 58, 255);
    private static readonly Color ButtonFocused = new Color32(24, 58, 70, 255);
    private static readonly Color ButtonDisabled = new Color32(15, 21, 28, 175);
    private static readonly Color LabelNormal = new Color32(232, 239, 246, 255);
    private static readonly Color LabelDisabled = new Color32(135, 148, 161, 255);

    private readonly Button _backButton;
    private readonly Button _forwardButton;
    private readonly Button _mapButton;
    private readonly Text _backLabel;
    private readonly Text _forwardLabel;
    private readonly Text _mapLabel;

    internal RectTransform RootRect { get; }

    internal BrowserNavigationToolbar(
        RectTransform parent,
        Action goBack,
        Action goForward,
        Action loadMap
    )
    {
        var toolbarObject = new GameObject("MapBrowserToolbar");
        toolbarObject.transform.SetParent(parent, false);

        RootRect = toolbarObject.AddComponent<RectTransform>();
        RootRect.anchorMin = new Vector2(0.5f, 1f);
        RootRect.anchorMax = new Vector2(0.5f, 1f);
        RootRect.pivot = new Vector2(0.5f, 1f);
        RootRect.anchoredPosition = new Vector2(0f, -TopInset);
        RootRect.sizeDelta = new Vector2(ControlWidth, ControlHeight);

        var border = toolbarObject.AddComponent<Image>();
        border.color = ToolbarBorder;
        border.raycastTarget = true;

        var backgroundObject = new GameObject("Background");
        backgroundObject.transform.SetParent(RootRect, false);

        var backgroundRect = backgroundObject.AddComponent<RectTransform>();
        backgroundRect.anchorMin = Vector2.zero;
        backgroundRect.anchorMax = Vector2.one;
        backgroundRect.offsetMin = new Vector2(BorderThickness, BorderThickness);
        backgroundRect.offsetMax = new Vector2(-BorderThickness, -BorderThickness);

        var background = backgroundObject.AddComponent<Image>();
        background.color = ToolbarBackground;
        background.raycastTarget = false;

        float cursor = BorderThickness + HorizontalPadding;
        _backButton = CreateButton(
            RootRect,
            "Back",
            "< Back",
            cursor,
            BackButtonWidth,
            ButtonNormal,
            goBack,
            out _backLabel
        );
        cursor += BackButtonWidth + ButtonGap;
        _forwardButton = CreateButton(
            RootRect,
            "Forward",
            "Forward >",
            cursor,
            ForwardButtonWidth,
            ButtonNormal,
            goForward,
            out _forwardLabel
        );
        cursor += ForwardButtonWidth + ButtonGap;
        _mapButton = CreateButton(
            RootRect,
            "Map",
            "Map",
            cursor,
            MapButtonWidth,
            MapButtonNormal,
            loadMap,
            out _mapLabel
        );

        SetState(false, false, false);
    }

    internal void SetState(bool browserReady, bool canGoBack, bool canGoForward)
    {
        SetInteractable(_backButton, _backLabel, browserReady && canGoBack);
        SetInteractable(_forwardButton, _forwardLabel, browserReady && canGoForward);
        SetInteractable(_mapButton, _mapLabel, browserReady);
    }

    private static Button CreateButton(
        RectTransform parent,
        string name,
        string label,
        float x,
        float width,
        Color normalColor,
        Action action,
        out Text text
    )
    {
        var buttonObject = new GameObject($"MapBrowser{name}Button");
        buttonObject.transform.SetParent(parent, false);

        var buttonRect = buttonObject.AddComponent<RectTransform>();
        buttonRect.anchorMin = new Vector2(0f, 0.5f);
        buttonRect.anchorMax = new Vector2(0f, 0.5f);
        buttonRect.pivot = new Vector2(0f, 0.5f);
        buttonRect.anchoredPosition = new Vector2(x, 0f);
        buttonRect.sizeDelta = new Vector2(width, ControlHeight - BorderThickness * 2);

        var background = buttonObject.AddComponent<Image>();
        background.color = normalColor;

        var button = buttonObject.AddComponent<Button>();
        button.targetGraphic = background;
        button.transition = Selectable.Transition.ColorTint;
        button.colors = new ColorBlock
        {
            normalColor = normalColor,
            highlightedColor = ButtonHover,
            pressedColor = ButtonPressed,
            selectedColor = ButtonFocused,
            disabledColor = ButtonDisabled,
            colorMultiplier = 1f,
            fadeDuration = 0.15f,
        };
        button.onClick.AddListener(() => action());

        var labelObject = new GameObject("Label");
        labelObject.transform.SetParent(buttonObject.transform, false);

        var labelRect = labelObject.AddComponent<RectTransform>();
        labelRect.anchorMin = Vector2.zero;
        labelRect.anchorMax = Vector2.one;
        labelRect.sizeDelta = Vector2.zero;
        labelRect.anchoredPosition = Vector2.zero;

        text = labelObject.AddComponent<Text>();
        text.font = Resources.GetBuiltinResource<Font>("Arial.ttf");
        text.fontSize = LabelSize;
        text.fontStyle = FontStyle.Bold;
        text.alignment = TextAnchor.MiddleCenter;
        text.color = LabelNormal;
        text.raycastTarget = false;
        text.supportRichText = false;
        text.text = label;

        return button;
    }

    private static void SetInteractable(Button button, Text label, bool interactable)
    {
        button.interactable = interactable;
        label.color = interactable ? LabelNormal : LabelDisabled;
    }
}
