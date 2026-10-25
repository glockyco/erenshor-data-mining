# Adventure Guide

Adventure Guide adds quest walkthroughs, item-source lookup and navigation to Erenshor. Use it to follow quest objectives, find missing items and track your next action without leaving the game.

[Read about Adventure Guide](https://erenshor.compendiums.org/adventure-guide).

## Install and use

Choose the release for your loader:

- [BepInEx installation and settings](thunderstore/README.md).
- [Lunaris installation and settings](vault/README.md).

Press L to open the guide, K to show or hide the tracker, and P to toggle the ground path with the initial key settings. Select a quest, then use NAV to follow an objective or "Choose a source" to inspect alternative item sources. Browsing quests does not change your tracked action.

The guide evaluates requirements from live quest, inventory and world state. Locked sources show what you still need. It saves settings and per-character guide state in the loader configuration, and saves window layout separately. The loader-specific instructions above explain where to change settings.

## Build and deploy

Follow the [repository setup](../../../README.md#setup) first. From the repository root, with the game closed:

```sh
uv run erenshor mod setup
uv run erenshor mod build --mod adventure-guide --loader bepinex
uv run erenshor mod deploy --mod adventure-guide --loader bepinex
```

Use `--loader lunaris` instead for the Lunaris build. Deployment installs the selected artifact and activates its loader. Restart the game after deployment. Keep the BepInEx runtime files with the plugin. Do not put one loader's DLL into the other loader's plugin directory.

## Update guide data

From the repository root:

```sh
uv run erenshor guide export-mod
```

The exporter reads the selected variant's clean database and writes [quest_guides/quest-guide.json](../../../quest_guides/quest-guide.json), which the mod embeds at build time. Generate it only from a complete clean build. Keep reviewed presentation overrides in [quest_guides/graph_overrides.toml](../../../quest_guides/graph_overrides.toml), not in generated output.

## Development and releases

[src/Config/GuideConfig.cs](src/Config/GuideConfig.cs) defines settings. [src/Navigation](src/Navigation) handles routes and source selection. [src/State](src/State) reads live quest and tracking state.

The [mod-development guide](../../../.agent/skills/mod-development/SKILL.md) covers local development. The [mod-pipeline guide](../../../.agent/skills/mod-pipeline/SKILL.md) covers packaging and publishing. Run checks through the repository's `erenshor test` commands, as described in the [repository README](../../../README.md#working-on-it).

## License

[MIT](../../../LICENSE).
