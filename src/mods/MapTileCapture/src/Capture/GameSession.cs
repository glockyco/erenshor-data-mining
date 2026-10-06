using System.Collections;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace MapTileCapture.Capture;

/// <summary>
/// Steps that bring the player into the world and move them between scenes,
/// shared by the zone and portrait captures.
/// </summary>
internal static class GameSession
{
    /// <summary>
    /// MainCam lives in DontDestroyOnLoad after login. Its absence means the
    /// game is still on the main menu or the character select screen.
    /// </summary>
    public static bool InWorld => GameObject.Find("MainCam") != null;

    /// <summary>
    /// Drives the game through its login flow so captures can proceed without
    /// requiring the player to manually navigate the menus.
    ///
    /// Handles two starting states:
    ///   "Menu"      — loads the character select screen
    ///   "LoadScene" — selects character slot 0, waits for sim data, enters world
    ///
    /// On completion (success or timeout) the caller checks <see cref="InWorld"/>
    /// to determine whether the login succeeded.
    /// </summary>
    public static IEnumerator EnsureInWorld(IModLogger logger)
    {
        string scene = SceneManager.GetActiveScene().name;
        logger.LogInfo($"EnsureInWorld: current scene = '{scene}'");

        // From the main menu: load the character select screen.
        // The Login button calls SceneManager.LoadScene("LoadScene") — replicate
        // that directly rather than simulating a UI click.
        if (scene == "Menu")
        {
            logger.LogInfo("On Menu — loading character select screen.");
            SceneManager.LoadScene("LoadScene");

            float t = 0f;
            while (SceneManager.GetActiveScene().name != "LoadScene")
            {
                t += Time.unscaledDeltaTime;
                if (t > 30f)
                {
                    logger.LogError("Timed out waiting for LoadScene.");
                    yield break;
                }
                yield return null;
            }

            // Give MonoBehaviours two frames to run their Start() callbacks.
            yield return null;
            yield return null;
        }

        // On the character select screen: pick slot 0 and enter the world.
        if (SceneManager.GetActiveScene().name == "LoadScene")
        {
            var charSelect = UnityEngine.Object.FindObjectOfType<CharSelectManager>();
            if (charSelect == null)
            {
                logger.LogError("CharSelectManager not found on LoadScene.");
                yield break;
            }

            logger.LogInfo("Selecting character slot 0.");
            charSelect.SelectSlot(0);

            // CharSelectManager.Update() enables EnterWorld only once
            // LoadedSimplayers == true and the selected slot has a character name.
            logger.LogInfo("Waiting for character data to load...");
            float t = 0f;
            while (
                !(
                    GameData.SimMngr?.LoadedSimplayers == true
                    && GameData.CurrentCharacterSlot?.CharName?.Length > 0
                )
            )
            {
                t += Time.unscaledDeltaTime;
                if (t > 60f)
                {
                    logger.LogError("Timed out waiting for character data.");
                    yield break;
                }
                yield return null;
            }

            if (GameData.CurrentCharacterSlot!.CharName.Length == 0)
            {
                logger.LogError("Character slot 0 is empty — cannot enter world.");
                yield break;
            }

            logger.LogInfo($"Entering world as '{GameData.CurrentCharacterSlot.CharName}'.");
            charSelect.EnterWorld.onClick.Invoke();
        }

        // Wait for the player to land in a game zone. MainCam appears in
        // DontDestroyOnLoad once the world scene has loaded and the player spawned.
        logger.LogInfo("Waiting for MainCam...");
        float inWorldTimeout = 60f;
        float inWorldElapsed = 0f;
        while (!InWorld)
        {
            inWorldElapsed += Time.unscaledDeltaTime;
            if (inWorldElapsed > inWorldTimeout)
            {
                logger.LogError("Timed out waiting for MainCam after login.");
                yield break;
            }
            yield return null;
        }

        logger.LogInfo("Player is in-world.");
    }
}

/// <summary>
/// Moves the player to a scene through <c>GameData.SceneChange.ChangeScene</c>
/// and waits until Unity reports the scene loaded. ChangeScene sets
/// <c>GameData.usingSun</c>, enables or disables the Sun light, and calls
/// <c>AtmosphereColors.ForceColors()</c> for outdoor zones, all before the new
/// scene loads, so <c>ZoneAnnounce.Start()</c> sees the correct state.
///
/// Unity does not run the <c>finally</c> blocks of a stopped coroutine, so the
/// owner disposes the operation when it stops early. Disposing removes the
/// scene-loaded handler.
/// </summary>
internal sealed class SceneChangeOperation : IDisposable
{
    private UnityEngine.Events.UnityAction<Scene, LoadSceneMode>? _handler;

    public bool Loaded { get; private set; }
    public bool Cancelled { get; private set; }
    public string? Error { get; private set; }

    public IEnumerator Run(
        string sceneName,
        Vector3 landing,
        bool usingSun,
        float yRotation,
        float timeoutSecs,
        Func<bool> cancelled
    )
    {
        if (GameData.SceneChange == null)
        {
            Error =
                "GameData.SceneChange is null — player must be fully in-world before capturing.";
            yield break;
        }

        bool sceneLoaded = false;
        _handler = (scene, mode) =>
        {
            if (scene.name == sceneName)
                sceneLoaded = true;
        };
        SceneManager.sceneLoaded += _handler;
        GameData.SceneChange.ChangeScene(sceneName, landing, usingSun, yRotation);

        float elapsed = 0f;
        while (!sceneLoaded)
        {
            if (cancelled())
            {
                Cancelled = true;
                Dispose();
                yield break;
            }

            elapsed += Time.unscaledDeltaTime;
            if (elapsed > timeoutSecs)
            {
                Error = $"Scene load timed out after {timeoutSecs}s";
                Dispose();
                yield break;
            }

            yield return null;
        }
        Loaded = true;
        Dispose();
    }

    public void Dispose()
    {
        if (_handler == null)
            return;

        SceneManager.sceneLoaded -= _handler;
        _handler = null;
    }
}
