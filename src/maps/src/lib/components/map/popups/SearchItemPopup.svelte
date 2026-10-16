<script lang="ts">
    import { SvelteMap } from 'svelte/reactivity';
    import type {
        WorldEnemy,
        WorldNpc,
        WorldMiningNode,
        WorldWater,
        WorldItemBag
    } from '$lib/types/world-map';
    import type { AnySourceMarker, ResolvedItemSource } from '$lib/map/search/item-source-provider';
    import type { ItemSearchResult } from '$lib/map/search';
    import { commonWorldSourceLabel } from '$lib/map/search';
    import WikiLink from '$lib/components/map/WikiLink.svelte';
    import Crosshair from '@lucide/svelte/icons/crosshair';

    type AnySpawnMarker = WorldEnemy | WorldNpc;

    interface Props {
        result: ItemSearchResult;
        sources: ResolvedItemSource[];
        onHoverSpawn: (stableKey: string | string[] | null) => void;
        onFocusSpawn: (stableKey: string | string[]) => void;
        onFocusAll: () => void;
    }

    interface ZoneDropper {
        row: Extract<ResolvedItemSource, { kind: 'drop' }>['row'];
        spawns: AnySpawnMarker[];
    }

    interface ZoneVendor {
        row: Extract<ResolvedItemSource, { kind: 'vendor' }>['row'];
        spawns: AnySpawnMarker[];
    }

    interface ZoneDropperGroup {
        zone: string;
        zoneName: string;
        rows: ZoneDropper[];
    }

    interface ZoneVendorGroup {
        zone: string;
        zoneName: string;
        rows: ZoneVendor[];
    }

    interface MiningEntry {
        marker: WorldMiningNode;
        chances: number[];
    }

    interface FishingEntry {
        marker: WorldWater;
        periods: Set<'day' | 'night'>;
        chances: number[];
    }

    interface ZoneMiningGroup {
        zone: string;
        zoneName: string;
        entries: Map<string, MiningEntry>;
    }

    interface ZoneFishingGroup {
        zone: string;
        zoneName: string;
        entries: Map<string, FishingEntry>;
    }

    interface ZoneBagGroup {
        zone: string;
        zoneName: string;
        markers: Map<string, WorldItemBag>;
    }

    let { result, sources, onHoverSpawn, onFocusSpawn, onFocusAll }: Props = $props();

    function sourceMarkers(source: ResolvedItemSource): AnySourceMarker[] {
        if ('markers' in source) return source.markers;
        if ('marker' in source) return [source.marker];
        return [];
    }

    const allMarkers = $derived.by(() => {
        const markers = new SvelteMap<string, AnySourceMarker>();
        for (const source of sources) {
            for (const marker of sourceMarkers(source)) {
                markers.set(marker.stableKey, marker);
            }
        }
        return [...markers.values()];
    });

    const auctionHouses = $derived(sources.filter((source) => source.kind === 'auction_house'));

    const unlocatedDroppers = $derived(sources.filter(
        (source): source is Extract<ResolvedItemSource, { kind: 'drop' }> =>
            source.kind === 'drop' && source.markers.length === 0
    ));
    const unlocatedVendors = $derived(sources.filter(
        (source): source is Extract<ResolvedItemSource, { kind: 'vendor' }> =>
            source.kind === 'vendor' && source.markers.length === 0
    ));
    const treasureGroups = $derived.by(() => {
        const groups = new SvelteMap<string, {
            row: Extract<ResolvedItemSource, { kind: 'treasure' }>['row'];
            zoneName: string;
            markers: AnySourceMarker[];
        }>();
        for (const source of sources) {
            if (source.kind !== 'treasure') continue;
            for (const marker of source.markers) {
                const key = `${source.row.characterStableKey}:${marker.zone}:${source.row.playerLevelMin}:${source.row.playerLevelMax}`;
                const group = groups.get(key);
                if (group) group.markers.push(marker);
                else groups.set(key, { row: source.row, zoneName: marker.zoneName, markers: [marker] });
            }
        }
        return [...groups.values()];
    });

    const droppersByZone = $derived.by(() => {
        const groups = new SvelteMap<string, ZoneDropperGroup>();

        for (const source of sources) {
            if (source.kind !== 'drop') continue;
            const byZone = new SvelteMap<string, AnySpawnMarker[]>();
            for (const marker of source.markers) {
                const spawns = byZone.get(marker.zone);
                if (spawns) spawns.push(marker);
                else byZone.set(marker.zone, [marker]);
            }

            for (const [zone, spawns] of byZone) {
                const group = groups.get(zone);
                const row = { row: source.row, spawns };
                if (group) group.rows.push(row);
                else {
                    groups.set(zone, {
                        zone,
                        zoneName: spawns[0]?.zoneName ?? zone,
                        rows: [row]
                    });
                }
            }
        }

        return [...groups.values()]
            .sort((a, b) => b.rows.length - a.rows.length)
            .map((group) => ({
                ...group,
                rows: [...group.rows].sort((a, b) => b.row.dropProbability - a.row.dropProbability)
            }));
    });

    const vendorsByZone = $derived.by(() => {
        const groups = new SvelteMap<string, ZoneVendorGroup>();

        for (const source of sources) {
            if (source.kind !== 'vendor') continue;
            const byZone = new SvelteMap<string, AnySpawnMarker[]>();
            for (const marker of source.markers) {
                const spawns = byZone.get(marker.zone);
                if (spawns) spawns.push(marker);
                else byZone.set(marker.zone, [marker]);
            }

            for (const [zone, spawns] of byZone) {
                const group = groups.get(zone);
                const row = { row: source.row, spawns };
                if (group) group.rows.push(row);
                else {
                    groups.set(zone, {
                        zone,
                        zoneName: spawns[0]?.zoneName ?? zone,
                        rows: [row]
                    });
                }
            }
        }

        return [...groups.values()]
            .sort((a, b) => b.rows.length - a.rows.length)
            .map((group) => ({
                ...group,
                rows: [...group.rows].sort((a, b) => a.row.price - b.row.price)
            }));
    });

    const miningByZone = $derived.by(() => {
        const groups = new SvelteMap<string, ZoneMiningGroup>();

        for (const source of sources) {
            if (source.kind !== 'mining') continue;
            const marker = source.marker;
            let group = groups.get(marker.zone);
            if (!group) {
                group = {
                    zone: marker.zone,
                    zoneName: marker.zoneName,
                    entries: new Map()
                };
                groups.set(marker.zone, group);
            }
            const entry = group.entries.get(marker.stableKey);
            if (entry) entry.chances.push(source.row.dropChance);
            else {
                group.entries.set(marker.stableKey, {
                    marker,
                    chances: [source.row.dropChance]
                });
            }
        }

        return [...groups.values()].sort((a, b) => b.entries.size - a.entries.size);
    });

    const fishingByZone = $derived.by(() => {
        const groups = new SvelteMap<string, ZoneFishingGroup>();

        for (const source of sources) {
            if (source.kind !== 'fishing') continue;
            const marker = source.marker;
            let group = groups.get(marker.zone);
            if (!group) {
                group = {
                    zone: marker.zone,
                    zoneName: marker.zoneName,
                    entries: new Map()
                };
                groups.set(marker.zone, group);
            }
            const entry = group.entries.get(marker.stableKey);
            if (entry) {
                entry.periods.add(source.row.period);
                entry.chances.push(source.row.dropChance);
            } else {
                group.entries.set(marker.stableKey, {
                    marker,
                    periods: new Set([source.row.period]),
                    chances: [source.row.dropChance]
                });
            }
        }

        return [...groups.values()].sort((a, b) => b.entries.size - a.entries.size);
    });

    const bagsByZone = $derived.by(() => {
        const groups = new SvelteMap<string, ZoneBagGroup>();

        for (const source of sources) {
            if (source.kind !== 'bag') continue;
            const marker = source.marker;
            let group = groups.get(marker.zone);
            if (!group) {
                group = {
                    zone: marker.zone,
                    zoneName: marker.zoneName,
                    markers: new Map()
                };
                groups.set(marker.zone, group);
            }
            group.markers.set(marker.stableKey, marker);
        }

        return [...groups.values()].sort((a, b) => b.markers.size - a.markers.size);
    });

    const giversByZone = $derived.by(() => {
        const groups = new SvelteMap<
            string,
            {
                zone: string;
                zoneName: string;
                rows: {
                    row: Extract<ResolvedItemSource, { kind: 'dialog' }>['row'];
                    spawns: AnySpawnMarker[];
                }[];
            }
        >();
        for (const source of sources) {
            if (source.kind !== 'dialog') continue;
            const byZone = new SvelteMap<string, AnySpawnMarker[]>();
            for (const marker of source.markers) {
                const spawns = byZone.get(marker.zone);
                if (spawns) spawns.push(marker);
                else byZone.set(marker.zone, [marker]);
            }
            for (const [zone, spawns] of byZone) {
                let group = groups.get(zone);
                if (!group) {
                    group = { zone, zoneName: spawns[0].zoneName, rows: [] };
                    groups.set(zone, group);
                }
                group.rows.push({ row: source.row, spawns });
            }
        }
        return [...groups.values()].sort((a, b) => a.zoneName.localeCompare(b.zoneName));
    });

    const quests = $derived.by(() => {
        const groups = new SvelteMap<
            string,
            {
                row: Extract<ResolvedItemSource, { kind: 'quest' }>['row'];
                turnIns: { key: string; name: string; markers: AnySpawnMarker[] }[];
            }
        >();
        for (const source of sources) {
            if (source.kind !== 'quest') continue;
            let group = groups.get(source.row.questStableKey);
            if (!group) {
                group = { row: source.row, turnIns: [] };
                groups.set(source.row.questStableKey, group);
            }
            if (source.markers.length) {
                group.turnIns.push({
                    key: source.row.turnInCharacterStableKey!,
                    name: source.row.turnInCharacterName ?? '',
                    markers: source.markers
                });
            }
        }
        return [...groups.values()];
    });
    const recipes = $derived(sources.filter((s) => s.kind === 'craft'));
    const itemUses = $derived(sources.filter((s) => s.kind === 'item_use'));
    const starting = $derived(sources.filter((s) => s.kind === 'starting'));
    const commonWorldDrops = $derived(sources.filter((s) => s.kind === 'common_world_item'));

    const worldDrops = $derived(
        sources
            .filter((source) => source.kind === 'world')
            .map((source) => source.row)
            .sort((a, b) => b.dropProbability - a.dropProbability)
    );

    // Two significant digits: world drop chances range from 1% down to 0.002%.
    function formatWorldDropChance(pct: number): string {
        return `${Number(pct.toPrecision(2))}%`;
    }

    function focusMarkers(markers: AnySourceMarker[]): void {
        if (markers.length > 0) onFocusSpawn(markerKeys(markers));
    }

    function markerKeys(markers: AnySourceMarker[]): string[] {
        return [...new Set(markers.map((marker) => marker.stableKey))];
    }

    function formatDropChance(pct: number): string {
        // One decimal for sub-percent chances, integer otherwise
        return pct < 1 ? `${pct.toFixed(1)}%` : `${Math.round(pct)}%`;
    }

    function formatChanceRange(chances: number[]): string {
        const min = Math.min(...chances);
        const max = Math.max(...chances);
        return min === max
            ? formatDropChance(max)
            : `${formatDropChance(min)}–${formatDropChance(max)}`;
    }

    const formatPrice = (n: number): string => n.toLocaleString();
</script>

<div class="space-y-4">
    <!-- Summary -->
    <div class="relative flex items-center justify-center">
        {#if result.iconHash}
            <img src={`/items/${result.iconHash}.w48.webp`} alt="" class="h-12 w-12" />
        {/if}
        <div class="absolute right-0">
            <WikiLink pageName={result.wikiPageName} />
        </div>
    </div>

    {#if allMarkers.length > 0}
        <!-- Focus all button -->
        <button
            type="button"
            onclick={() => onFocusAll()}
            onmouseenter={() => onHoverSpawn(markerKeys(allMarkers))}
            onmouseleave={() => onHoverSpawn(null)}
            class="flex w-full items-center justify-center gap-2 rounded-md
                   bg-zinc-700/50 px-3 py-2 text-xs text-zinc-300
                   hover:bg-zinc-700 hover:text-white transition-colors"
        >
            <Crosshair class="h-3.5 w-3.5" />
            <span>Show all {allMarkers.length} location{allMarkers.length !== 1 ? 's' : ''}</span>
        </button>
    {:else if !result.hasKnownSource}
        <p class="border-t border-zinc-700 pt-3 text-center text-xs text-zinc-400">
            The map has no data on how to obtain this item.
        </p>
    {/if}

    {#if vendorsByZone.length > 0}
        <!-- Sold by -->
        <div class="space-y-3 border-t border-zinc-700 pt-2">
            <div class="text-xs uppercase tracking-wide text-zinc-500">Sold by</div>
            {#each vendorsByZone as group (group.zone)}
                <div>
                    <div class="flex items-center justify-between mb-1.5">
                        <div class="text-xs font-medium text-zinc-300">{group.zoneName}</div>
                        <div class="text-xs text-zinc-500">
                            {group.rows.length} vendor{group.rows.length !== 1 ? 's' : ''}
                        </div>
                    </div>
                    <div class="space-y-1">
                        {#each group.rows as vendor (`${group.zone}:${vendor.row.characterStableKey}`)}
                            <button
                                type="button"
                                class="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left
                                       text-xs text-zinc-400 hover:bg-zinc-700/50 hover:text-zinc-200
                                       transition-colors group"
                                onmouseenter={() => onHoverSpawn(markerKeys(vendor.spawns))}
                                onmouseleave={() => onHoverSpawn(null)}
                                onclick={() => focusMarkers(vendor.spawns)}
                            >
                                <div class="min-w-0 flex-1">
                                    <div class="text-zinc-300">
                                        <span class="truncate">{vendor.row.npcName}</span>
                                    </div>
                                    <div class="flex flex-wrap items-center gap-x-1 text-zinc-500">
                                        <span>{formatPrice(vendor.row.price)} gold</span>
                                        <span>·</span>
                                        <span>
                                            {vendor.spawns.length} location{vendor.spawns.length !==
                                            1
                                                ? 's'
                                                : ''}
                                        </span>
                                    </div>
                                </div>
                                <Crosshair
                                    class="h-3.5 w-3.5 shrink-0 text-zinc-600 group-hover:text-zinc-400"
                                />
                            </button>
                        {/each}
                    </div>
                </div>
            {/each}
        </div>
    {/if}

    {#if unlocatedVendors.length}
        <!-- Shown after the located sold by entries, under their heading when they exist. -->
        <div class="space-y-2 pt-2 text-xs" class:border-t={!vendorsByZone.length} class:border-zinc-700={!vendorsByZone.length}>
            {#if !vendorsByZone.length}<div class="uppercase tracking-wide text-zinc-500">Sold by</div>{/if}
            {#each unlocatedVendors as source (source.row.characterStableKey)}
                {#if source.kind === 'vendor'}
                    <div>
                        <div class="flex items-center gap-1 text-zinc-300">
                            {source.row.npcName}<WikiLink pageName={source.row.npcWikiPageName} />
                        </div>
                        <div class="text-zinc-400">{formatPrice(source.row.price)} gold · Location unknown</div>
                    </div>
                {/if}
            {/each}
        </div>
    {/if}

    {#if giversByZone.length}
        <div class="space-y-3 border-t border-zinc-700 pt-2">
            <div class="text-xs uppercase tracking-wide text-zinc-500">Given by</div>
            {#each giversByZone as group (group.zone)}
                <div class="space-y-1">
                    <div class="text-xs font-medium text-zinc-300">{group.zoneName}</div>
                    {#each group.rows as giver (`${giver.row.characterStableKey}:${giver.row.requiredQuestStableKey ?? ''}`)}
                        <div class="rounded px-2 py-1.5 text-xs text-zinc-400">
                            <button
                                type="button"
                                class="flex w-full items-center justify-between text-left text-zinc-300 hover:text-white"
                                onmouseenter={() => onHoverSpawn(markerKeys(giver.spawns))}
                                onmouseleave={() => onHoverSpawn(null)}
                                onclick={() => focusMarkers(giver.spawns)}
                            >
                                <span
                                    >{giver.row.npcName} · {giver.spawns.length} location{giver
                                        .spawns.length !== 1
                                        ? 's'
                                        : ''}</span
                                >
                                <Crosshair class="h-3.5 w-3.5 shrink-0" />
                            </button>
                            {#if giver.row.requiredQuestName}
                                <div class="mt-1 flex items-center gap-1">
                                    after {giver.row.requiredQuestName}
                                    <WikiLink pageName={giver.row.requiredQuestWikiPageName} />
                                </div>
                            {/if}
                        </div>
                    {/each}
                </div>
            {/each}
        </div>
    {/if}

    {#if quests.length}
        <div class="space-y-2 border-t border-zinc-700 pt-2 text-xs text-zinc-300">
            <div class="uppercase tracking-wide text-zinc-500">Reward from</div>
            {#each quests as quest (quest.row.questStableKey)}
                <div class="space-y-1">
                    <div class="flex items-center gap-1">
                        {quest.row.questName}<WikiLink pageName={quest.row.questWikiPageName} />
                    </div>
                    {#each quest.turnIns as turnIn (turnIn.key)}
                        {#each [...new Set(turnIn.markers.map((m) => m.zone))] as zone (zone)}
                            {@const markers = turnIn.markers.filter((m) => m.zone === zone)}
                            <button
                                type="button"
                                class="flex w-full items-center justify-between rounded px-2 py-1.5 text-left text-zinc-400 hover:bg-zinc-700/50 hover:text-white"
                                onmouseenter={() => onHoverSpawn(markerKeys(markers))}
                                onmouseleave={() => onHoverSpawn(null)}
                                onclick={() => focusMarkers(markers)}
                            >
                                <span>Turn in to {turnIn.name} · {markers[0].zoneName}</span>
                                <Crosshair class="h-3.5 w-3.5 shrink-0" />
                            </button>
                        {/each}
                    {/each}
                </div>
            {/each}
        </div>
    {/if}

    {#if recipes.length}
        <div class="space-y-2 border-t border-zinc-700 pt-2 text-xs text-zinc-300">
            <div class="uppercase tracking-wide text-zinc-500">Crafting recipe</div>
            {#each recipes as recipe (recipe.row.recipeStableKey)}
                <div class="flex items-center gap-1">
                    {recipe.row.recipeName}<WikiLink pageName={recipe.row.recipeWikiPageName} />
                </div>
            {/each}
            <p class="text-zinc-400">Crafted at a forge.</p>
        </div>
    {/if}

    {#if bagsByZone.length > 0}
        <!-- Item bags -->
        <div class="space-y-1 border-t border-zinc-700 pt-2">
            <div class="text-xs uppercase tracking-wide text-zinc-500 mb-2">Item bags</div>
            {#each bagsByZone as group (group.zone)}
                {@const markers = [...group.markers.values()]}
                <button
                    type="button"
                    class="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left
                           text-xs text-zinc-400 hover:bg-zinc-700/50 hover:text-zinc-200
                           transition-colors group"
                    onmouseenter={() => onHoverSpawn(markerKeys(markers))}
                    onmouseleave={() => onHoverSpawn(null)}
                    onclick={() => focusMarkers(markers)}
                >
                    <div class="min-w-0 flex-1">
                        <div class="flex flex-wrap items-center gap-x-1.5 text-zinc-300">
                            <span>{group.zoneName}</span>
                        </div>
                        <div class="text-zinc-500">
                            {markers.length} bag{markers.length !== 1 ? 's' : ''}
                        </div>
                    </div>
                    <Crosshair
                        class="h-3.5 w-3.5 shrink-0 text-zinc-600 group-hover:text-zinc-400"
                    />
                </button>
            {/each}
        </div>
    {/if}

    {#if starting.length}
        <div class="space-y-2 border-t border-zinc-700 pt-2 text-xs text-zinc-300">
            <div class="uppercase tracking-wide text-zinc-500">Starting item of</div>
            {#if starting[0].row.allClasses}
                <div class="flex items-center gap-1">
                    All classes<WikiLink pageName="Classes" />
                </div>
            {:else}
                {#each starting as source (source.row.className)}
                    <div class="flex items-center gap-1">
                        {source.row.classDisplayName}<WikiLink
                            pageName={source.row.classDisplayName}
                        />
                    </div>
                {/each}
            {/if}
        </div>
    {/if}

    {#if droppersByZone.length > 0}
        <!-- Dropped by -->
        <div class="space-y-3 border-t border-zinc-700 pt-2">
            <div class="text-xs uppercase tracking-wide text-zinc-500">Dropped by</div>
            {#each droppersByZone as group (group.zone)}
                <div>
                    <div class="flex items-center justify-between mb-1.5">
                        <div class="text-xs font-medium text-zinc-300">{group.zoneName}</div>
                        <div class="text-xs text-zinc-500">
                            {group.rows.length} dropper{group.rows.length !== 1 ? 's' : ''}
                        </div>
                    </div>
                    <div class="space-y-1">
                        {#each group.rows as dropper (`${group.zone}:${dropper.row.characterStableKey}`)}
                            <button
                                type="button"
                                class="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left
                                       text-xs text-zinc-400 hover:bg-zinc-700/50 hover:text-zinc-200
                                       transition-colors group"
                                onmouseenter={() => onHoverSpawn(markerKeys(dropper.spawns))}
                                onmouseleave={() => onHoverSpawn(null)}
                                onclick={() => focusMarkers(dropper.spawns)}
                            >
                                <div class="min-w-0 flex-1">
                                    <div
                                        class="flex flex-wrap items-center gap-x-1.5 text-zinc-300"
                                    >
                                        <span class="truncate">{dropper.row.npcName}</span>
                                        {#if dropper.row.encounterTier === 'boss'}
                                            <span
                                                class="rounded px-1 py-0.5 text-[10px]
                                                       bg-amber-900/50 text-amber-300">Boss</span
                                            >
                                        {:else if dropper.row.encounterTier === 'elite'}
                                            <span
                                                class="rounded px-1 py-0.5 text-[10px]
                                                       bg-indigo-900/50 text-indigo-300">Elite</span
                                            >
                                        {:else if dropper.row.encounterTier === 'chest'}
                                            <span
                                                class="rounded px-1 py-0.5 text-[10px]
                                                       bg-teal-900/50 text-teal-300">Chest</span
                                            >
                                        {/if}
                                    </div>
                                    <div class="flex flex-wrap items-center gap-x-1 text-zinc-500">
                                        <span
                                            >{formatDropChance(dropper.row.dropProbability)} drop</span
                                        >
                                        <span>·</span>
                                        <span>
                                            {dropper.spawns.length} spawn{dropper.spawns.length !==
                                            1
                                                ? 's'
                                                : ''}
                                        </span>
                                    </div>
                                </div>
                                <Crosshair
                                    class="h-3.5 w-3.5 shrink-0 text-zinc-600 group-hover:text-zinc-400"
                                />
                            </button>
                        {/each}
                    </div>
                </div>
            {/each}
        </div>
    {/if}

    {#if unlocatedDroppers.length}
        <!-- Shown after the located dropped by entries, under their heading when they exist. -->
        <div class="space-y-2 pt-2 text-xs" class:border-t={!droppersByZone.length} class:border-zinc-700={!droppersByZone.length}>
            {#if !droppersByZone.length}<div class="uppercase tracking-wide text-zinc-500">Dropped by</div>{/if}
            {#each unlocatedDroppers as source (source.row.characterStableKey)}
                {#if source.kind === 'drop'}
                    <div>
                        <div class="flex items-center gap-1 text-zinc-300">
                            {source.row.npcName}<WikiLink pageName={source.row.npcWikiPageName} />
                        </div>
                        <div class="text-zinc-400">{formatDropChance(source.row.dropProbability)} drop · Location unknown</div>
                    </div>
                {/if}
            {/each}
        </div>
    {/if}

    {#if treasureGroups.length}
        <div class="space-y-2 border-t border-zinc-700 pt-2 text-xs">
            <div class="uppercase tracking-wide text-zinc-500">Treasure hunting</div>
            <p class="text-zinc-400">Possible hunt locations, not chests present at every site.</p>
            {#each treasureGroups as group (`${group.row.characterStableKey}:${group.zoneName}:${group.row.playerLevelMin}:${group.row.playerLevelMax}`)}
                <div class="space-y-1">
                    <div class="flex items-center gap-1 text-zinc-300">
                        {group.row.chestName}<WikiLink pageName={group.row.chestWikiPageName} />
                    </div>
                    <button
                        type="button"
                        class="flex w-full items-center justify-between rounded px-2 py-1.5 text-left text-zinc-400 hover:bg-zinc-700/50 hover:text-white"
                        onmouseenter={() => onHoverSpawn(markerKeys(group.markers))}
                        onmouseleave={() => onHoverSpawn(null)}
                        onclick={() => focusMarkers(group.markers)}
                    >
                        <span>
                            {group.zoneName} · player levels {group.row.playerLevelMin}–{group.row.playerLevelMax}
                            <br />{group.markers.length} possible location{group.markers.length !== 1 ? 's' : ''}
                            · {formatDropChance(group.row.dropProbability)} drop
                        </span>
                        <Crosshair class="h-3.5 w-3.5 shrink-0" />
                    </button>
                </div>
            {/each}
        </div>
    {/if}

    {#if miningByZone.length > 0}
        <!-- Mining nodes -->
        <div class="space-y-1 border-t border-zinc-700 pt-2">
            <div class="text-xs uppercase tracking-wide text-zinc-500 mb-2">Mining nodes</div>
            {#each miningByZone as group (group.zone)}
                {@const entries = [...group.entries.values()]}
                {@const markers = entries.map((entry) => entry.marker)}
                {@const chances = entries.flatMap((entry) => entry.chances)}
                <button
                    type="button"
                    class="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left
                           text-xs text-zinc-400 hover:bg-zinc-700/50 hover:text-zinc-200
                           transition-colors group"
                    onmouseenter={() => onHoverSpawn(markerKeys(markers))}
                    onmouseleave={() => onHoverSpawn(null)}
                    onclick={() => focusMarkers(markers)}
                >
                    <div class="min-w-0 flex-1">
                        <div class="text-zinc-300">{group.zoneName}</div>
                        <div class="text-zinc-500">
                            {entries.length} node{entries.length !== 1 ? 's' : ''} ·
                            {formatChanceRange(chances)} chance
                        </div>
                    </div>
                    <Crosshair
                        class="h-3.5 w-3.5 shrink-0 text-zinc-600 group-hover:text-zinc-400"
                    />
                </button>
            {/each}
        </div>
    {/if}

    {#if fishingByZone.length > 0}
        <!-- Fishing spots -->
        <div class="space-y-1 border-t border-zinc-700 pt-2">
            <div class="text-xs uppercase tracking-wide text-zinc-500 mb-2">Fishing spots</div>
            {#each fishingByZone as group (group.zone)}
                {@const entries = [...group.entries.values()]}
                {@const markers = entries.map((entry) => entry.marker)}
                {@const chances = entries.flatMap((entry) => entry.chances)}
                {@const periods = entries.flatMap((entry) => [...entry.periods])}
                <button
                    type="button"
                    class="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left
                           text-xs text-zinc-400 hover:bg-zinc-700/50 hover:text-zinc-200
                           transition-colors group"
                    onmouseenter={() => onHoverSpawn(markerKeys(markers))}
                    onmouseleave={() => onHoverSpawn(null)}
                    onclick={() => focusMarkers(markers)}
                >
                    <div class="min-w-0 flex-1">
                        <div class="flex flex-wrap items-center gap-x-1.5 text-zinc-300">
                            <span>{group.zoneName}</span>
                            {#if periods.every((period) => period === 'day')}
                                <span
                                    class="rounded px-1 py-0.5 text-[10px] bg-sky-900/50 text-sky-300"
                                >
                                    Day
                                </span>
                            {:else if periods.every((period) => period === 'night')}
                                <span
                                    class="rounded px-1 py-0.5 text-[10px]
                                           bg-indigo-900/50 text-indigo-300">Night</span
                                >
                            {/if}
                        </div>
                        <div class="text-zinc-500">
                            {entries.length} spot{entries.length !== 1 ? 's' : ''} ·
                            {formatChanceRange(chances)} chance
                        </div>
                    </div>
                    <Crosshair
                        class="h-3.5 w-3.5 shrink-0 text-zinc-600 group-hover:text-zinc-400"
                    />
                </button>
            {/each}
        </div>
    {/if}

    {#if itemUses.length}
        <div class="space-y-2 border-t border-zinc-700 pt-2 text-xs text-zinc-300">
            <div class="uppercase tracking-wide text-zinc-500">Obtained by using</div>
            {#each itemUses as source (`${source.row.sourceItemStableKey}:${source.row.zoneName ?? ''}`)}
                <div>
                    <div class="flex items-center gap-1">
                        {source.row.sourceItemName}<WikiLink
                            pageName={source.row.sourceItemWikiPageName}
                        />
                    </div>
                    {#if source.row.dropProbability !== null}<div class="text-zinc-400">
                            {formatWorldDropChance(source.row.dropProbability)}
                        </div>{/if}
                    {#if source.row.zoneName}<div class="text-zinc-400">
                            in {source.row.zoneName}
                        </div>{/if}
                </div>
            {/each}
        </div>
    {/if}

    {#if commonWorldDrops.length > 0}
        <div class="space-y-1 border-t border-zinc-700 pt-2">
            <div class="text-xs uppercase tracking-wide text-zinc-500 mb-2">World drop</div>
            {#each commonWorldDrops as source (source.row.itemStableKey)}
                <div class="px-2 text-xs text-zinc-300">
                    {commonWorldSourceLabel(source.row.dropProbability, source.row.dropProbabilityMax)}
                </div>
            {/each}
        </div>
    {/if}

    {#if worldDrops.length > 0}
        <!-- Special world drops -->
        <div class="space-y-1 border-t border-zinc-700 pt-2">
            <div class="text-xs uppercase tracking-wide text-zinc-500 mb-2">World drop</div>
            {#each worldDrops as drop (drop.pool)}
                <div class="flex justify-between gap-2 px-2 text-xs">
                    <span class="text-zinc-300">
                        {drop.minLevelExclusive > 0
                            ? `Any enemy above level ${drop.minLevelExclusive}`
                            : 'Any enemy'}
                    </span>
                    <span class="shrink-0 text-zinc-500"
                        >{formatWorldDropChance(drop.dropProbability)} per kill</span
                    >
                </div>
            {/each}
            <div class="px-2 text-xs text-zinc-500">At the default loot rate.</div>
        </div>
    {/if}
    {#if auctionHouses.length}
        <div class="space-y-2 border-t border-zinc-700 pt-2 text-xs">
            <div class="flex items-center gap-1 text-zinc-300">
                Auction House<WikiLink pageName="Auction House" />
            </div>
            <p class="text-zinc-400">May be listed by simulated players</p>
            <p class="text-zinc-500">Stock is random.</p>
            {#each auctionHouses as source (source.row.itemStableKey)}
                {#each source.brokers as broker (broker.row.characterStableKey)}
                    <div class="space-y-1">
                        <div class="flex items-center gap-1 text-zinc-300">
                            {broker.row.npcName}<WikiLink pageName={broker.row.npcWikiPageName} />
                        </div>
                        {#each [...new Set(broker.markers.map((marker) => marker.zone))] as zone (zone)}
                            {@const markers = broker.markers.filter((marker) => marker.zone === zone)}
                            <button
                                type="button"
                                class="flex w-full items-center justify-between rounded px-2 py-1.5 text-left text-zinc-400 hover:bg-zinc-700/50 hover:text-white"
                                onmouseenter={() => onHoverSpawn(markerKeys(markers))}
                                onmouseleave={() => onHoverSpawn(null)}
                                onclick={() => focusMarkers(markers)}
                            >
                                <span>{markers[0].zoneName} · {markers.length} location{markers.length !== 1 ? 's' : ''}</span>
                                <Crosshair class="h-3.5 w-3.5 shrink-0" />
                            </button>
                        {:else}
                            <div class="text-zinc-400">Location unknown</div>
                        {/each}
                    </div>
                {/each}
            {/each}
        </div>
    {/if}

</div>
