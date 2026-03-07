<script lang="ts">
    import { SvelteMap } from 'svelte/reactivity';
    import type { WorldNpc } from '$lib/types/world-map';
    import WikiLink from '$lib/components/map/WikiLink.svelte';
    import Crosshair from '@lucide/svelte/icons/crosshair';

    interface Props {
        name: string;
        markers: WorldNpc[];
        onHoverSpawn: (stableKey: string | null) => void;
        onFocusSpawn: (stableKey: string) => void;
        onFocusAll: () => void;
    }

    let { name, markers, onHoverSpawn, onFocusSpawn, onFocusAll }: Props = $props();

    // Overall level range (across all characters on all matching markers)
    const levelRange = $derived.by(() => {
        const levels = markers.flatMap((m) => m.characters.map((c) => c.level));
        const min = Math.min(...levels);
        const max = Math.max(...levels);
        return min === max ? `Level ${min}` : `Level ${min}–${max}`;
    });

    // Whether level varies across locations (show per-row if so)
    const levelVaries = $derived.by(() => {
        const levels = new Set(markers.flatMap((m) => m.characters.map((c) => c.level)));
        return levels.size > 1;
    });

    // Group markers by zone, sorted by spawn count descending
    const groupedByZone = $derived.by(() => {
        const groups = new SvelteMap<string, WorldNpc[]>();
        for (const marker of markers) {
            const existing = groups.get(marker.zone);
            if (existing) {
                existing.push(marker);
            } else {
                groups.set(marker.zone, [marker]);
            }
        }
        return [...groups.entries()].sort((a, b) => b[1].length - a[1].length);
    });

    const zoneCount = $derived(new Set(markers.map((m) => m.zone)).size);

    function formatRespawnTime(seconds: number | null): string {
        if (seconds === null || seconds === 0) return 'zone re-entry';
        const minutes = Math.round(seconds / 60);
        if (minutes < 1) return `~${seconds}s`;
        if (minutes === 1) return '~1 min';
        return `~${minutes} min`;
    }
</script>

<div class="space-y-4">
    <!-- Summary -->
    <div class="space-y-1">
        <div class="text-sm text-zinc-300">{levelRange}</div>
        <div class="text-xs text-zinc-400">
            {markers.length} location{markers.length !== 1 ? 's' : ''} across
            {zoneCount} zone{zoneCount !== 1 ? 's' : ''}
        </div>
        <WikiLink {name} />
    </div>

    <!-- Focus all button -->
    {#if markers.length > 1}
        <button
            type="button"
            onclick={() => onFocusAll()}
            class="flex w-full items-center justify-center gap-2 rounded-md
			       bg-zinc-700/50 px-3 py-2 text-xs text-zinc-300
			       hover:bg-zinc-700 hover:text-white transition-colors"
        >
            <Crosshair class="h-3.5 w-3.5" />
            <span>Show all {markers.length} locations</span>
        </button>
    {/if}

    <!-- NPCs grouped by zone -->
    <div class="space-y-3">
        {#each groupedByZone as [zone, zoneMarkers] (zone)}
            <div class="border-t border-zinc-700 pt-2">
                <div class="flex items-center justify-between mb-1.5">
                    <div class="text-xs font-medium text-zinc-300">{zoneMarkers[0].zoneName}</div>
                    <div class="text-xs text-zinc-500">
                        {zoneMarkers.length} location{zoneMarkers.length !== 1 ? 's' : ''}
                    </div>
                </div>
                <div class="space-y-1">
                    {#each zoneMarkers as marker (marker.stableKey)}
                        <button
                            type="button"
                            class="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left
							       text-xs text-zinc-400 hover:bg-zinc-700/50 hover:text-zinc-200
							       transition-colors group"
                            onmouseenter={() => onHoverSpawn(marker.stableKey)}
                            onmouseleave={() => onHoverSpawn(null)}
                            onclick={() => onFocusSpawn(marker.stableKey)}
                        >
                            <div class="min-w-0 flex-1">
                                <div class="flex flex-wrap items-center gap-x-1 text-zinc-500">
                                    {#if levelVaries}
                                        {@const markerLevels = marker.characters.map(
                                            (c) => c.level
                                        )}
                                        {@const minLv = Math.min(...markerLevels)}
                                        {@const maxLv = Math.max(...markerLevels)}
                                        <span class="text-zinc-300">
                                            Lv {minLv === maxLv ? minLv : `${minLv}–${maxLv}`}
                                        </span>
                                        <span>·</span>
                                    {/if}
                                    <span>{formatRespawnTime(marker.spawnDelay)} respawn</span>
                                    {#if marker.isNightSpawn}
                                        <span
                                            class="rounded px-1 py-0.5 text-[10px]
										       bg-indigo-900/50 text-indigo-300"
                                        >
                                            Night
                                        </span>
                                    {/if}
                                    {#if !marker.isEnabled}
                                        <span
                                            class="rounded px-1 py-0.5 text-[10px]
										       bg-amber-900/50 text-amber-300"
                                        >
                                            Disabled
                                        </span>
                                    {/if}
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
