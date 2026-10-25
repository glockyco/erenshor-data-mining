# Justice for F7

Justice for F7 extends Erenshor's F7 "Hide UI" action to hide nameplates, target indicators, health bars and other UI drawn in the game world. Use it when you want screenshots without those elements.

## Install and use

Choose the release for your loader:

- [BepInEx installation and settings](thunderstore/README.md).
- [Lunaris installation and settings](vault/README.md).

Press F7 to hide the UI and press it again to show it. Choose which element categories to hide through your loader's configuration. Turn off Enabled to restore the game's normal F7 behavior.

## Build and deploy

Follow the [repository setup](../../../README.md#setup) first. From the repository root, with the game closed:

```sh
uv run erenshor mod setup
uv run erenshor mod build --mod justice-for-f7 --loader bepinex
uv run erenshor mod deploy --mod justice-for-f7 --loader bepinex
```

Use `--loader lunaris` instead for the Lunaris build. Deployment installs the selected artifact and activates its loader. Restart the game after deployment. Do not put one loader's DLL into the other loader's plugin directory.

## Development and releases

[src/JusticeRuntime.cs](src/JusticeRuntime.cs) holds the shared lifecycle. [src/WorldUIHider.cs](src/WorldUIHider.cs) handles world-space visibility, and [src/Patches](src/Patches) suppresses transient elements while the UI is hidden.

The [mod-development guide](../../../.agent/skills/mod-development/SKILL.md) covers local development. The [mod-pipeline guide](../../../.agent/skills/mod-pipeline/SKILL.md) covers packaging and publishing. Run checks through the repository's `erenshor test` commands, as described in the [repository README](../../../README.md#working-on-it).

## License

[MIT](../../../LICENSE).
