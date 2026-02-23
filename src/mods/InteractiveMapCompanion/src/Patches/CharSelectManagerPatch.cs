using HarmonyLib;
using UnityEngine.EventSystems;

namespace InteractiveMapCompanion.Patches;

/// <summary>
/// Harmony Postfix on CharSelectManager.Update() to maintain GameData.PlayerTyping
/// while the character name input field is focused on the character select screen.
///
/// The game never sets PlayerTyping for the character name TMP_InputField — it
/// only does so for chat, auction house, bank rename, and guild name fields.
/// This patch closes that gap by polling EventSystem.currentSelectedGameObject
/// each frame, replicating the pattern used in GuildManagerUI.
///
/// We track whether we set the flag ourselves (_weSetPlayerTyping) so we never
/// accidentally clear a flag that a different game system raised.
/// </summary>
[HarmonyPatch(typeof(CharSelectManager), "Update")]
internal static class CharSelectManagerPatch
{
    /// <summary>
    /// True when this patch was the one that set GameData.PlayerTyping.
    /// Reset by Plugin.OnSceneLoaded() when leaving LoadScene so the flag
    /// cannot get stuck if the player enters the game world while the name
    /// field is focused.
    /// </summary>
    internal static bool _weSetPlayerTyping;

    [HarmonyPostfix]
    private static void Postfix(CharSelectManager __instance)
    {
        // EventSystem can be null briefly during scene transitions.
        if (EventSystem.current == null)
            return;

        // The name field only exists within CharCreate, and CharCreate is
        // inactive except during new character creation. Scoping to
        // CharCreate.activeSelf prevents a false positive from any other
        // "InputField (TMP)" in LoadScene (e.g. the auction house price
        // field, which shares the default TMP GameObject name).
        bool nameFieldFocused =
            __instance.CharCreate.activeSelf
            && EventSystem.current.currentSelectedGameObject?.name == "InputField (TMP)";

        if (nameFieldFocused && !_weSetPlayerTyping)
        {
            GameData.PlayerTyping = true;
            _weSetPlayerTyping = true;
        }
        else if (!nameFieldFocused && _weSetPlayerTyping)
        {
            GameData.PlayerTyping = false;
            _weSetPlayerTyping = false;
        }
    }
}
