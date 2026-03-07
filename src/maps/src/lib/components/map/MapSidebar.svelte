<script lang="ts">
    import { LAYER_COLORS } from '$lib/map/config';
    import type { LayerVisibility, LevelRange } from '$lib/types/world-map';
    import type { ConnectionState } from '$lib/map/live';
    import LayerToggle from './LayerToggle.svelte';
    import SidebarSection from './SidebarSection.svelte';
    import LevelFilter from './LevelFilter.svelte';
    import * as Drawer from '$lib/components/ui/drawer';

    // Lucide icons
    import Home from '@lucide/svelte/icons/home';
    import Search from '@lucide/svelte/icons/search';
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
    import Download from '@lucide/svelte/icons/download';
    import Menu from '@lucide/svelte/icons/menu';

    interface Props {
        visibility: LayerVisibility;
        collapsed?: boolean;
        isDesktop: boolean;
        onVisibilityChange: (key: keyof LayerVisibility, value: boolean) => void;
        onToggleCollapse: () => void;
        levelRange: LevelRange;
        levelFilter: [number, number];
        onLevelFilterChange: (value: [number, number]) => void;
        liveEnabled: boolean;
        connectionState: ConnectionState;
        onLiveModeChange: (enabled: boolean) => void;
        autoFollowEnabled: boolean;
        onAutoFollowChange: (enabled: boolean) => void;
        onSearchOpen: () => void;
    }

    let {
        visibility,
        collapsed = false,
        isDesktop,
        onVisibilityChange,
        onToggleCollapse,
        levelRange,
        levelFilter,
        onLevelFilterChange,
        liveEnabled,
        connectionState,
        onLiveModeChange,
        autoFollowEnabled,
        onAutoFollowChange,
        onSearchOpen
    }: Props = $props();

    let drawerOpen = $state(false);

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

{#snippet sidebarContent()}
    <!-- Search button -->
    <div class="px-3 pt-3 pb-1">
        <button
            type="button"
            onclick={() => {
                drawerOpen = false;
                onSearchOpen();
            }}
            class="flex w-full items-center gap-2 rounded-md bg-zinc-700/50 px-3 py-2
                   text-sm text-zinc-400 hover:bg-zinc-700 hover:text-zinc-200
                   transition-colors cursor-pointer"
        >
            <Search class="h-4 w-4 shrink-0" />
            <span class="flex-1 text-left">Search...</span>
            {#if isDesktop}
                <kbd class="rounded bg-zinc-800 px-1.5 py-0.5 text-xs text-zinc-500">&#8984;K</kbd>
            {/if}
        </button>
    </div>

    <!-- Enemies -->
    <SidebarSection title="Enemies">
        <LevelFilter
            label="Level"
            min={levelRange.min}
            max={levelRange.max}
            value={levelFilter}
            onchange={onLevelFilterChange}
        />
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

    <!-- Live Mode -->
    <SidebarSection title="Live Mode">
        <label class="flex cursor-pointer items-center gap-2 py-1 text-sm hover:bg-zinc-700/50">
            <input
                type="checkbox"
                checked={liveEnabled}
                onchange={(e) => onLiveModeChange(e.currentTarget.checked)}
                class="sr-only"
            />
            <span
                class="flex h-4 w-4 items-center justify-center rounded border transition-colors"
                class:bg-zinc-600={!liveEnabled}
                class:border-zinc-500={!liveEnabled}
                class:bg-lime-500={liveEnabled}
                class:border-lime-500={liveEnabled}
            >
                {#if liveEnabled}
                    <svg
                        class="h-3 w-3 text-white"
                        viewBox="0 0 12 12"
                        fill="none"
                        stroke="currentColor"
                    >
                        <path
                            d="M2 6l3 3 5-6"
                            stroke-width="2"
                            stroke-linecap="round"
                            stroke-linejoin="round"
                        />
                    </svg>
                {/if}
            </span>
            <span class="text-zinc-200">Enable Live Mode</span>
        </label>

        <!-- Get Started Guide (when Live Mode disabled) -->
        {#if !liveEnabled}
            <div class="mt-3 rounded-lg bg-zinc-700/40 p-2.5 text-xs text-zinc-300">
                <p class="mb-1.5 font-semibold text-zinc-100">Get Started</p>
                <p class="mb-2.5 leading-relaxed text-zinc-400">
                    Install the World Map Companion mod to enable live entity tracking on the map.
                </p>
                <a
                    href="/mod"
                    class="inline-flex items-center gap-1.5 rounded-md bg-purple-600 px-2.5 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-purple-700"
                >
                    <svg class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <path
                            d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"
                            stroke-width="2"
                            stroke-linecap="round"
                            stroke-linejoin="round"
                        />
                        <path
                            d="M21 3v5h-5"
                            stroke-width="2"
                            stroke-linecap="round"
                            stroke-linejoin="round"
                        />
                        <path
                            d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"
                            stroke-width="2"
                            stroke-linecap="round"
                            stroke-linejoin="round"
                        />
                        <path
                            d="M3 21v-5h5"
                            stroke-width="2"
                            stroke-linecap="round"
                            stroke-linejoin="round"
                        />
                    </svg>
                    <span>View Installation Guide</span>
                </a>
            </div>
        {/if}

        <!-- Connection status -->
        {#if liveEnabled}
            <div class="mt-2 text-xs">
                {#if connectionState === 'connected'}
                    <div class="flex items-center gap-1.5 text-lime-400">
                        <div class="h-2 w-2 rounded-full bg-lime-400"></div>
                        <span>Connected to mod</span>
                    </div>
                {:else if connectionState === 'connecting' || connectionState === 'reconnecting'}
                    <div class="flex items-center gap-1.5 text-yellow-400">
                        <div class="h-2 w-2 rounded-full bg-yellow-400 animate-pulse"></div>
                        <span>Connecting...</span>
                    </div>
                {:else}
                    <div class="flex items-center gap-1.5 text-red-400">
                        <div class="h-2 w-2 rounded-full bg-red-400"></div>
                        <span>Disconnected</span>
                    </div>
                {/if}
            </div>

            <!-- Auto-Follow toggle (only when connected) -->
            <label
                class="mt-2 flex cursor-pointer items-center gap-2 py-1 text-sm hover:bg-zinc-700/50"
                class:opacity-50={connectionState !== 'connected'}
                class:cursor-not-allowed={connectionState !== 'connected'}
            >
                <input
                    type="checkbox"
                    checked={autoFollowEnabled}
                    disabled={connectionState !== 'connected'}
                    onchange={(e) => onAutoFollowChange(e.currentTarget.checked)}
                    class="sr-only"
                />
                <span
                    class="flex h-4 w-4 items-center justify-center rounded border transition-colors"
                    class:bg-zinc-600={!autoFollowEnabled}
                    class:border-zinc-500={!autoFollowEnabled}
                    class:bg-cyan-500={autoFollowEnabled}
                    class:border-cyan-500={autoFollowEnabled}
                >
                    {#if autoFollowEnabled}
                        <svg
                            class="h-3 w-3 text-white"
                            viewBox="0 0 12 12"
                            fill="none"
                            stroke="currentColor"
                        >
                            <path
                                d="M2 6l3 3 5-6"
                                stroke-width="2"
                                stroke-linecap="round"
                                stroke-linejoin="round"
                            />
                        </svg>
                    {/if}
                </span>
                <span class="text-zinc-200 text-xs">Auto-Follow Player</span>
            </label>
        {/if}
    </SidebarSection>
{/snippet}

{#if isDesktop}
    <!-- Desktop: fixed left sidebar -->
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
                {@render sidebarContent()}
            </div>

            <!-- Footer -->
            <div class="border-t border-zinc-700 px-3 py-2 text-xs text-zinc-500">
                <kbd class="rounded bg-zinc-700 px-1.5 py-0.5 text-zinc-400">B</kbd> to toggle sidebar
            </div>
        {:else}
            <!-- Collapsed: Icon toggles with circular backgrounds -->
            <div class="flex flex-1 flex-col items-center gap-2 overflow-y-auto pb-2 pt-2">
                <!-- Home button -->
                <a
                    href="/"
                    class="flex h-7 w-7 items-center justify-center rounded-md text-zinc-400 transition-colors hover:bg-zinc-700 hover:text-white"
                    title="Home"
                >
                    <Home class="h-4 w-4" />
                </a>

                <!-- Search button -->
                <button
                    type="button"
                    onclick={onSearchOpen}
                    class="flex h-7 w-7 cursor-pointer items-center justify-center rounded-md text-zinc-400 transition-colors hover:bg-zinc-700 hover:text-white"
                    title="Search (⌘K)"
                >
                    <Search class="h-4 w-4" />
                </button>

                <div class="w-8 border-t border-zinc-700"></div>

                <!-- Enemies -->
                {#each enemyToggles as toggle (toggle.key)}
                    {@const Icon = toggle.icon}
                    {@const isActive = visibility[toggle.key]}
                    <button
                        type="button"
                        class="flex h-7 w-7 cursor-pointer items-center justify-center rounded-full transition-all hover:ring-2 hover:ring-white"
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
                        class="flex h-7 w-7 cursor-pointer items-center justify-center rounded-full transition-all hover:ring-2 hover:ring-white"
                        class:opacity-40={!npcActive}
                        style:background-color={npcToggle.color}
                        title="{npcToggle.label} ({npcActive ? 'on' : 'off'})"
                        onclick={() =>
                            onVisibilityChange(npcToggle.key, !visibility[npcToggle.key])}
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
                        class="flex h-7 w-7 cursor-pointer items-center justify-center rounded-full transition-all hover:ring-2 hover:ring-white"
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
                        class="flex h-7 w-7 cursor-pointer items-center justify-center rounded-full transition-all hover:ring-2 hover:ring-white"
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
                        class="flex h-7 w-7 cursor-pointer items-center justify-center rounded-full transition-all hover:ring-2 hover:ring-white"
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
                        class="flex h-7 w-7 cursor-pointer items-center justify-center rounded-full transition-all hover:ring-2 hover:ring-white"
                        class:opacity-40={!isActive}
                        style:background-color={toggle.color}
                        title="{toggle.label} ({isActive ? 'on' : 'off'})"
                        onclick={() => onVisibilityChange(toggle.key, !visibility[toggle.key])}
                    >
                        <Icon class="h-4 w-4 text-white drop-shadow-[0_0_1px_rgba(0,0,0,0.8)]" />
                    </button>
                {/each}

                <div class="my-1 w-8 border-t border-zinc-700"></div>

                <!-- Companion Mod link -->
                <a
                    href="/mod"
                    class="flex h-7 w-7 items-center justify-center rounded-md text-purple-400 transition-colors hover:bg-zinc-700 hover:text-purple-300"
                    title="Companion Mod Installation Guide"
                >
                    <Download class="h-4 w-4" />
                </a>
            </div>
        {/if}
    </aside>
{:else}
    <!-- Mobile: floating action buttons -->
    <div class="fixed bottom-4 left-4 z-20 flex gap-2">
        <button
            type="button"
            onclick={() => (drawerOpen = true)}
            class="flex h-12 w-12 cursor-pointer items-center justify-center rounded-full
                   bg-zinc-800/95 shadow-lg backdrop-blur
                   text-zinc-300 hover:text-white transition-colors"
            title="Map controls"
        >
            <Menu class="h-5 w-5" />
        </button>
        <button
            type="button"
            onclick={onSearchOpen}
            class="flex h-12 w-12 cursor-pointer items-center justify-center rounded-full
                   bg-zinc-800/95 shadow-lg backdrop-blur
                   text-zinc-300 hover:text-white transition-colors"
            title="Search"
        >
            <Search class="h-5 w-5" />
        </button>
    </div>

    <!-- Mobile: sidebar content in bottom drawer -->
    <Drawer.Root bind:open={drawerOpen} shouldScaleBackground={false}>
        <Drawer.Content>
            <Drawer.Header class="sr-only">
                <Drawer.Title>Map Controls</Drawer.Title>
            </Drawer.Header>
            <div class="overflow-y-auto px-1 pb-4">
                {@render sidebarContent()}
            </div>
        </Drawer.Content>
    </Drawer.Root>
{/if}
