<script lang="ts">
    import { SvelteMap } from 'svelte/reactivity';
    import type { WorldEnemy, WorldNpc } from '$lib/types/world-map';
    import type { ItemDropperRow } from '$lib/map-markers';
    import type { ItemSearchResult } from '$lib/map/search';
    import WikiLink from '$lib/components/map/WikiLink.svelte';
    import Crosshair from '@lucide/svelte/icons/crosshair';

    type AnySpawnMarker = WorldEnemy | WorldNpc;

    /** One dropper character within one zone — carries that zone's spawns. */
    interface ZoneDropper {
        row: ItemDropperRow;
        spawns: AnySpawnMarker[]; // this character's spawns in THIS zone only
    }

    interface Props {
        result: ItemSearchResult;
        markers: AnySpawnMarker[];
        dropRows: ItemDropperRow[];
        onHoverSpawn: (stableKey: string | string[] | null) => void;
        onFocusSpawn: (stableKey: string) => void;
        onFocusAll: () => void;
    }

    let {
        result,
        markers,
        dropRows,
        onHoverSpawn,
        onFocusSpawn,
        onFocusAll
    }: Props = $props();

    /**
     * Every spawn marker (from the item's highlight set) containing each
     * dropper character, across all zones. Used to seed per-zone grouping.
     */
    const allSpawnsByDropper = $derived.by(() => {
        const map = new SvelteMap<string, AnySpawnMarker[]>();
        for (const row of dropRows) {
            const key = row.characterStableKey;
            const matches = markers.filter((m) =>
                m.characters.some((c) => c.stableKey === key)
            );
            if (matches.length > 0) map.set(key, matches);
        }
        return map;
    });

    /**
     * Droppers grouped by zone. Each (zone, character) pair appears exactly
     * once — a character with multiple spawns in the same zone is one row
     * carrying that zone's spawn count, not one row per spawn marker. Zones
     * sorted by dropper count descending; rows within a zone sorted by drop
     * probability descending. Droppers with no resolvable spawn (vendor-only
     * or event-only sources) are omitted — the map has nothing to show.
     */
    const droppersByZone = $derived.by(() => {
        const groups = new SvelteMap<string, ZoneDropper[]>();

        for (const row of dropRows) {
            const allSpawns = allSpawnsByDropper.get(row.characterStableKey);
            if (!allSpawns || allSpawns.length === 0) continue;

            // Partition this dropper's spawns by zone — one row per zone
            const byZone = new SvelteMap<string, AnySpawnMarker[]>();
            for (const marker of allSpawns) {
                const existing = byZone.get(marker.zone);
                if (existing) {
                    existing.push(marker);
                } else {
                    byZone.set(marker.zone, [marker]);
                }
            }

            for (const [zone, spawns] of byZone) {
                const entry: ZoneDropper = { row, spawns };
                const existing = groups.get(zone);
                if (existing) {
                    existing.push(entry);
                } else {
                    groups.set(zone, [entry]);
                }
            }
        }

        return [...groups.entries()]
            .sort((a, b) => b[1].length - a[1].length)
            .map(
                ([zone, droppers]) =>
                    [
                        zone,
                        [...droppers].sort(
                            (a, b) => b.row.dropProbability - a.row.dropProbability
                        )
                    ] as [string, ZoneDropper[]]
            );
    });

    function zoneNameFor(zoneKey: string): string {
        const marker = markers.find((m) => m.zone === zoneKey);
        return marker?.zoneName ?? zoneKey;
    }

    // Hover spotlights one spawn of this dropper in this zone. The existing
    // single-key hover infra (onHoverSpawn → hoveredSpawnKey) cannot narrow to
    // multiple spawns at once, so we spotlight the first; click flies to it.
    function focusDropper(spawns: AnySpawnMarker[]): void {
        if (spawns.length > 0) onFocusSpawn(spawns[0].stableKey);
    }

    function formatDropChance(pct: number): string {
        // One decimal for sub-percent chances, integer otherwise
        return pct < 1 ? `${pct.toFixed(1)}%` : `${Math.round(pct)}%`;
    }
</script>

<div class="space-y-4">
    <!-- Summary -->
    <div class="flex items-center justify-between">
        <div class="flex items-center gap-3">
            {#if result.iconName}
                <img src={`/items/${result.iconName}.w48.webp`} alt="" class="h-12 w-12" />
            {/if}
            <div class="text-sm text-zinc-300">
                {result.dropperCount} dropper{result.dropperCount !== 1 ? 's' : ''}
            </div>
        </div>
        <WikiLink pageName={result.wikiPageName} />
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
        <span>Show all {markers.length} spawn points</span>
    </button>

    <!-- Droppers grouped by zone -->
    <div class="space-y-3">
        {#each droppersByZone as [zone, droppers] (zone)}
            <div class="border-t border-zinc-700 pt-2">
                <div class="flex items-center justify-between mb-1.5">
                    <div class="text-xs font-medium text-zinc-300">{zoneNameFor(zone)}</div>
                    <div class="text-xs text-zinc-500">
                        {droppers.length} dropper{droppers.length !== 1 ? 's' : ''}
                    </div>
                </div>
                <div class="space-y-1">
                    {#each droppers as dropper (`${zone}:${dropper.row.characterStableKey}`)}
                        <button
                            type="button"
                            class="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left
							       text-xs text-zinc-400 hover:bg-zinc-700/50 hover:text-zinc-200
							       transition-colors group"
                            onmouseenter={() =>
                                onHoverSpawn(dropper.spawns.map((s) => s.stableKey))}
                            onmouseleave={() => onHoverSpawn(null)}
                            onclick={() => focusDropper(dropper.spawns)}
                        >
                            <div class="min-w-0 flex-1">
                                <div class="flex flex-wrap items-center gap-x-1.5 text-zinc-300">
                                    <span class="truncate">{dropper.row.npcName}</span>
                                    {#if dropper.row.isUnique}
                                        <span
                                            class="rounded px-1 py-0.5 text-[10px]
										       bg-amber-900/50 text-amber-300"
                                        >
                                            Unique
                                        </span>
                                    {:else if dropper.row.isRare}
                                        <span
                                            class="rounded px-1 py-0.5 text-[10px]
										       bg-indigo-900/50 text-indigo-300"
                                        >
                                            Rare
                                        </span>
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
</div>
