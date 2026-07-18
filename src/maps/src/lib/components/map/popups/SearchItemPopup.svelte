<script lang="ts">
    import { SvelteMap } from 'svelte/reactivity';
    import type { WorldEnemy, WorldNpc, WorldMiningNode, WorldWater, WorldItemBag } from '$lib/types/world-map';
    import type { AnySourceMarker, ResolvedItemSource } from '$lib/map/search/item-source-provider';
    import type { ItemSearchResult } from '$lib/map/search';
    import WikiLink from '$lib/components/map/WikiLink.svelte';
    import Crosshair from '@lucide/svelte/icons/crosshair';

    type AnySpawnMarker = WorldEnemy | WorldNpc;

    interface Props {
        result: ItemSearchResult;
        sources: ResolvedItemSource[];
        onHoverSpawn: (stableKey: string | string[] | null) => void;
        onFocusSpawn: (stableKey: string) => void;
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
        switch (source.kind) {
            case 'drop':
            case 'vendor':
                return source.markers;
            case 'mining':
            case 'fishing':
            case 'bag':
                return [source.marker];
        }
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
                rows: [...group.rows].sort(
                    (a, b) => b.row.dropProbability - a.row.dropProbability
                )
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

        return [...groups.values()].sort(
            (a, b) => b.entries.size - a.entries.size
        );
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

        return [...groups.values()].sort(
            (a, b) => b.entries.size - a.entries.size
        );
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

        return [...groups.values()].sort(
            (a, b) => b.markers.size - a.markers.size
        );
    });

    function focusMarkers(markers: AnySourceMarker[]): void {
        if (markers.length > 0) onFocusSpawn(markers[0].stableKey);
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
        {#if result.iconName}
            <img src={`/items/${result.iconName}.w48.webp`} alt="" class="h-12 w-12" />
        {/if}
        <div class="absolute right-0">
            <WikiLink pageName={result.wikiPageName} />
        </div>
    </div>

    <!-- Focus all button -->
    <button
        type="button"
        onclick={() => onFocusAll()}
        class="flex w-full items-center justify-center gap-2 rounded-md
               bg-zinc-700/50 px-3 py-2 text-xs text-zinc-300
               hover:bg-zinc-700 hover:text-white transition-colors"
    >
        <Crosshair class="h-3.5 w-3.5" />
        <span>Show all {allMarkers.length} location{allMarkers.length !== 1 ? 's' : ''}</span>
    </button>

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
                                    <div class="flex flex-wrap items-center gap-x-1.5 text-zinc-300">
                                        <span class="truncate">{dropper.row.npcName}</span>
                                        {#if dropper.row.isUnique}
                                            <span
                                                class="rounded px-1 py-0.5 text-[10px]
                                                       bg-amber-900/50 text-amber-300"
                                            >Unique</span>
                                        {:else if dropper.row.isRare}
                                            <span
                                                class="rounded px-1 py-0.5 text-[10px]
                                                       bg-indigo-900/50 text-indigo-300"
                                            >Rare</span>
                                        {/if}
                                    </div>
                                    <div class="flex flex-wrap items-center gap-x-1 text-zinc-500">
                                        <span>{formatDropChance(dropper.row.dropProbability)} drop</span>
                                        <span>·</span>
                                        <span>
                                            {dropper.spawns.length} spawn{dropper.spawns.length !== 1
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
                                            {vendor.spawns.length} location{vendor.spawns.length !== 1
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
                                <span class="rounded px-1 py-0.5 text-[10px] bg-sky-900/50 text-sky-300">
                                    Day
                                </span>
                            {:else if periods.every((period) => period === 'night')}
                                <span
                                    class="rounded px-1 py-0.5 text-[10px]
                                           bg-indigo-900/50 text-indigo-300"
                                >Night</span>
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
</div>
