<script lang="ts">
    import { LAYER_COLORS } from '$lib/map/config';
    import type { LayerVisibility } from '$lib/types/map';
    import LayerToggle from './LayerToggle.svelte';
    import SidebarSection from './SidebarSection.svelte';

    // Lucide icons
    import Home from '@lucide/svelte/icons/home';
    import PanelLeftClose from '@lucide/svelte/icons/panel-left-close';
    import PanelLeftOpen from '@lucide/svelte/icons/panel-left-open';
    import Skull from '@lucide/svelte/icons/skull';
    import User from '@lucide/svelte/icons/user';
    import KeyRound from '@lucide/svelte/icons/key-round';
    import Flame from '@lucide/svelte/icons/flame';
    import Droplet from '@lucide/svelte/icons/droplet';
    import Map from '@lucide/svelte/icons/map';
    import Pickaxe from '@lucide/svelte/icons/pickaxe';
    import Package from '@lucide/svelte/icons/package';
    import CircleHelp from '@lucide/svelte/icons/circle-help';
    import Trophy from '@lucide/svelte/icons/trophy';
    import CircleDot from '@lucide/svelte/icons/circle-dot';
    import Compass from '@lucide/svelte/icons/compass';

    interface Props {
        visibility: LayerVisibility;
        collapsed?: boolean;
        onVisibilityChange: (key: keyof LayerVisibility, value: boolean) => void;
        onToggleCollapse: () => void;
    }

    let { visibility, collapsed = false, onVisibilityChange, onToggleCollapse }: Props = $props();

    function rgbToHex(rgb: readonly [number, number, number]): string {
        return `#${rgb.map((c) => c.toString(16).padStart(2, '0')).join('')}`;
    }

    // Layer colors for toggles
    const colors = {
        tiles: '#6b7280',
        worldMap: '#6b7280',
        zoneBounds: '#6b7280',
        zoneLabels: '#6b7280',
        spawnPoints: rgbToHex(LAYER_COLORS.enemy),
        spawnPointsRare: rgbToHex(LAYER_COLORS['enemy-rare']),
        spawnPointsUnique: rgbToHex(LAYER_COLORS['enemy-unique']),
        characters: rgbToHex(LAYER_COLORS.npc),
        zoneLines: rgbToHex(LAYER_COLORS['zone-line']),
        teleports: rgbToHex(LAYER_COLORS.teleport),
        forges: rgbToHex(LAYER_COLORS.forge),
        wishingWells: rgbToHex(LAYER_COLORS['wishing-well']),
        miningNodes: rgbToHex(LAYER_COLORS['mining-node']),
        itemBags: rgbToHex(LAYER_COLORS['item-bag']),
        treasureLocs: rgbToHex(LAYER_COLORS['treasure-loc']),
        doors: rgbToHex(LAYER_COLORS.door),
        secretPassages: rgbToHex(LAYER_COLORS['secret-passage']),
        achievementTriggers: rgbToHex(LAYER_COLORS['achievement-trigger'])
    };

    function handleToggle(key: keyof LayerVisibility) {
        return (checked: boolean) => onVisibilityChange(key, checked);
    }

    // Quick toggle configuration for collapsed state
    type QuickToggle = {
        key: keyof LayerVisibility;
        icon: typeof Skull;
        color: string;
        label: string;
    };

    const enemyToggles: QuickToggle[] = [
        {
            key: 'spawnPointsUnique',
            icon: Skull,
            color: colors.spawnPointsUnique,
            label: 'Unique Enemies'
        },
        {
            key: 'spawnPointsRare',
            icon: Skull,
            color: colors.spawnPointsRare,
            label: 'Rare Enemies'
        },
        { key: 'spawnPoints', icon: Skull, color: colors.spawnPoints, label: 'Common Enemies' }
    ];

    const npcToggle: QuickToggle = {
        key: 'characters',
        icon: User,
        color: colors.characters,
        label: 'NPCs'
    };

    const interactableToggles: QuickToggle[] = [
        { key: 'doors', icon: KeyRound, color: colors.doors, label: 'Doors' },
        { key: 'forges', icon: Flame, color: colors.forges, label: 'Forges' },
        { key: 'wishingWells', icon: Droplet, color: colors.wishingWells, label: 'Wishing Wells' }
    ];

    const resourceToggles: QuickToggle[] = [
        { key: 'treasureLocs', icon: Map, color: colors.treasureLocs, label: 'Treasure Locations' },
        { key: 'miningNodes', icon: Pickaxe, color: colors.miningNodes, label: 'Mining Nodes' },
        { key: 'itemBags', icon: Package, color: colors.itemBags, label: 'Item Bags' }
    ];

    const secretToggles: QuickToggle[] = [
        {
            key: 'secretPassages',
            icon: CircleHelp,
            color: colors.secretPassages,
            label: 'Secret Passages'
        },
        {
            key: 'achievementTriggers',
            icon: Trophy,
            color: colors.achievementTriggers,
            label: 'Achievement Triggers'
        }
    ];

    const travelToggles: QuickToggle[] = [
        { key: 'zoneLines', icon: CircleDot, color: colors.zoneLines, label: 'Zone Connections' },
        { key: 'teleports', icon: Compass, color: colors.teleports, label: 'Teleport Destinations' }
    ];
</script>

<aside
    class="fixed left-0 top-0 z-40 flex h-full flex-col bg-zinc-800/95 shadow-xl backdrop-blur"
    class:w-64={!collapsed}
    class:w-14={collapsed}
>
    <!-- Header -->
    <div class="flex items-center justify-between border-b border-zinc-700 px-3 py-3">
        {#if !collapsed}
            <a href="/" class="flex items-center gap-2 text-sm text-zinc-300 hover:text-white">
                <Home class="h-4 w-4" />
                <span>Home</span>
            </a>
        {/if}
        <button
            type="button"
            onclick={onToggleCollapse}
            class="cursor-pointer rounded p-1 text-zinc-400 hover:bg-zinc-700 hover:text-white"
            class:mx-auto={collapsed}
            title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
            {#if collapsed}
                <PanelLeftOpen class="h-5 w-5" />
            {:else}
                <PanelLeftClose class="h-5 w-5" />
            {/if}
        </button>
    </div>

    {#if !collapsed}
        <!-- Scrollable content -->
        <div class="flex-1 overflow-y-auto">
            <!-- Enemies -->
            <SidebarSection title="Enemies">
                <LayerToggle
                    label="Unique"
                    checked={visibility.spawnPointsUnique}
                    color={colors.spawnPointsUnique}
                    onchange={handleToggle('spawnPointsUnique')}
                />
                <LayerToggle
                    label="Rare"
                    checked={visibility.spawnPointsRare}
                    color={colors.spawnPointsRare}
                    onchange={handleToggle('spawnPointsRare')}
                />
                <LayerToggle
                    label="Common"
                    checked={visibility.spawnPoints}
                    color={colors.spawnPoints}
                    onchange={handleToggle('spawnPoints')}
                />
            </SidebarSection>

            <!-- NPCs -->
            <SidebarSection title="NPCs">
                <LayerToggle
                    label="NPCs"
                    checked={visibility.characters}
                    color={colors.characters}
                    onchange={handleToggle('characters')}
                />
            </SidebarSection>

            <!-- Interactables -->
            <SidebarSection title="Interactables">
                <LayerToggle
                    label="Doors"
                    checked={visibility.doors}
                    color={colors.doors}
                    onchange={handleToggle('doors')}
                />
                <LayerToggle
                    label="Forges"
                    checked={visibility.forges}
                    color={colors.forges}
                    onchange={handleToggle('forges')}
                />
                <LayerToggle
                    label="Wishing Wells"
                    checked={visibility.wishingWells}
                    color={colors.wishingWells}
                    onchange={handleToggle('wishingWells')}
                />
            </SidebarSection>

            <!-- Resources -->
            <SidebarSection title="Resources">
                <LayerToggle
                    label="Treasure Locations"
                    checked={visibility.treasureLocs}
                    color={colors.treasureLocs}
                    onchange={handleToggle('treasureLocs')}
                />
                <LayerToggle
                    label="Mining Nodes"
                    checked={visibility.miningNodes}
                    color={colors.miningNodes}
                    onchange={handleToggle('miningNodes')}
                />
                <LayerToggle
                    label="Item Bags"
                    checked={visibility.itemBags}
                    color={colors.itemBags}
                    onchange={handleToggle('itemBags')}
                />
            </SidebarSection>

            <!-- Secrets -->
            <SidebarSection title="Secrets">
                <LayerToggle
                    label="Secret Passages"
                    checked={visibility.secretPassages}
                    color={colors.secretPassages}
                    onchange={handleToggle('secretPassages')}
                />
                <LayerToggle
                    label="Achievement Triggers"
                    checked={visibility.achievementTriggers}
                    color={colors.achievementTriggers}
                    onchange={handleToggle('achievementTriggers')}
                />
            </SidebarSection>

            <!-- Travel -->
            <SidebarSection title="Travel">
                <LayerToggle
                    label="Zone Connections"
                    checked={visibility.zoneLines}
                    color={colors.zoneLines}
                    onchange={handleToggle('zoneLines')}
                />
                <LayerToggle
                    label="Teleport Destinations"
                    checked={visibility.teleports}
                    color={colors.teleports}
                    onchange={handleToggle('teleports')}
                />
            </SidebarSection>

            <!-- Terrain -->
            <SidebarSection title="Terrain">
                <LayerToggle
                    label="Zone Tiles"
                    checked={visibility.tiles}
                    color={colors.tiles}
                    onchange={handleToggle('tiles')}
                />
                <LayerToggle
                    label="World Map"
                    checked={visibility.worldMap}
                    color={colors.worldMap}
                    onchange={handleToggle('worldMap')}
                />
                <LayerToggle
                    label="Zone Boundaries"
                    checked={visibility.zoneBounds}
                    color={colors.zoneBounds}
                    onchange={handleToggle('zoneBounds')}
                />
                <LayerToggle
                    label="Zone Labels"
                    checked={visibility.zoneLabels}
                    color={colors.zoneLabels}
                    onchange={handleToggle('zoneLabels')}
                />
            </SidebarSection>
        </div>

        <!-- Footer -->
        <div class="border-t border-zinc-700 px-3 py-2 text-xs text-zinc-500">
            <kbd class="rounded bg-zinc-700 px-1.5 py-0.5 text-zinc-400">B</kbd> to toggle sidebar
        </div>
    {:else}
        <!-- Collapsed: Icon toggles with circular backgrounds -->
        <div class="flex flex-1 flex-col items-center gap-2 overflow-y-auto py-2">
            <!-- Enemies -->
            {#each enemyToggles as toggle (toggle.key)}
                {@const Icon = toggle.icon}
                {@const isActive = visibility[toggle.key]}
                <button
                    type="button"
                    class="flex h-7 w-7 cursor-pointer items-center justify-center rounded-full transition-opacity"
                    class:opacity-40={!isActive}
                    style:background-color={toggle.color}
                    title="{toggle.label} ({isActive ? 'on' : 'off'})"
                    onclick={() => onVisibilityChange(toggle.key, !visibility[toggle.key])}
                >
                    <Icon class="h-4 w-4 text-white drop-shadow-[0_0_1px_rgba(0,0,0,0.8)]" />
                </button>
            {/each}

            <div class="my-1 w-8 border-t border-zinc-700"></div>

            <!-- NPCs -->
            {#if true}
                {@const npcActive = visibility[npcToggle.key]}
                <button
                    type="button"
                    class="flex h-7 w-7 cursor-pointer items-center justify-center rounded-full transition-opacity"
                    class:opacity-40={!npcActive}
                    style:background-color={npcToggle.color}
                    title="{npcToggle.label} ({npcActive ? 'on' : 'off'})"
                    onclick={() => onVisibilityChange(npcToggle.key, !visibility[npcToggle.key])}
                >
                    <User class="h-4 w-4 text-white drop-shadow-[0_0_1px_rgba(0,0,0,0.8)]" />
                </button>
            {/if}

            <div class="my-1 w-8 border-t border-zinc-700"></div>

            <!-- Interactables -->
            {#each interactableToggles as toggle (toggle.key)}
                {@const Icon = toggle.icon}
                {@const isActive = visibility[toggle.key]}
                <button
                    type="button"
                    class="flex h-7 w-7 cursor-pointer items-center justify-center rounded-full transition-opacity"
                    class:opacity-40={!isActive}
                    style:background-color={toggle.color}
                    title="{toggle.label} ({isActive ? 'on' : 'off'})"
                    onclick={() => onVisibilityChange(toggle.key, !visibility[toggle.key])}
                >
                    <Icon class="h-4 w-4 text-white drop-shadow-[0_0_1px_rgba(0,0,0,0.8)]" />
                </button>
            {/each}

            <div class="my-1 w-8 border-t border-zinc-700"></div>

            <!-- Resources -->
            {#each resourceToggles as toggle (toggle.key)}
                {@const Icon = toggle.icon}
                {@const isActive = visibility[toggle.key]}
                <button
                    type="button"
                    class="flex h-7 w-7 cursor-pointer items-center justify-center rounded-full transition-opacity"
                    class:opacity-40={!isActive}
                    style:background-color={toggle.color}
                    title="{toggle.label} ({isActive ? 'on' : 'off'})"
                    onclick={() => onVisibilityChange(toggle.key, !visibility[toggle.key])}
                >
                    <Icon class="h-4 w-4 text-white drop-shadow-[0_0_1px_rgba(0,0,0,0.8)]" />
                </button>
            {/each}

            <div class="my-1 w-8 border-t border-zinc-700"></div>

            <!-- Secrets -->
            {#each secretToggles as toggle (toggle.key)}
                {@const Icon = toggle.icon}
                {@const isActive = visibility[toggle.key]}
                <button
                    type="button"
                    class="flex h-7 w-7 cursor-pointer items-center justify-center rounded-full transition-opacity"
                    class:opacity-40={!isActive}
                    style:background-color={toggle.color}
                    title="{toggle.label} ({isActive ? 'on' : 'off'})"
                    onclick={() => onVisibilityChange(toggle.key, !visibility[toggle.key])}
                >
                    <Icon class="h-4 w-4 text-white drop-shadow-[0_0_1px_rgba(0,0,0,0.8)]" />
                </button>
            {/each}

            <div class="my-1 w-8 border-t border-zinc-700"></div>

            <!-- Travel -->
            {#each travelToggles as toggle (toggle.key)}
                {@const Icon = toggle.icon}
                {@const isActive = visibility[toggle.key]}
                <button
                    type="button"
                    class="flex h-7 w-7 cursor-pointer items-center justify-center rounded-full transition-opacity"
                    class:opacity-40={!isActive}
                    style:background-color={toggle.color}
                    title="{toggle.label} ({isActive ? 'on' : 'off'})"
                    onclick={() => onVisibilityChange(toggle.key, !visibility[toggle.key])}
                >
                    <Icon class="h-4 w-4 text-white drop-shadow-[0_0_1px_rgba(0,0,0,0.8)]" />
                </button>
            {/each}
        </div>
    {/if}
</aside>
