<script lang="ts">
    import { SvelteMap } from 'svelte/reactivity';
    import type { WorldEnemy } from '$lib/types/world-map';
    import WikiLink from '$lib/components/map/WikiLink.svelte';
    import Crosshair from '@lucide/svelte/icons/crosshair';

    interface Props {
        name: string;
        markers: WorldEnemy[];
        onHoverSpawn: (stableKey: string | null) => void;
        onFocusSpawn: (stableKey: string) => void;
        onFocusAll: () => void;
    }

    let { name, markers, onHoverSpawn, onFocusSpawn, onFocusAll }: Props = $props();

    // Overall level range from the searched character across all spawn points
    const levelRange = $derived.by(() => {
        let min = Infinity;
        let max = -Infinity;
        for (const marker of markers) {
            for (const char of marker.characters) {
                if (char.name !== name) continue;
                if (char.isInvulnerable) continue;
                min = Math.min(min, char.level);
                max = Math.max(max, char.level);
            }
        }
        if (!isFinite(min)) return null;
        return min === max ? `Level ${min}` : `Level ${min}–${max}`;
    });

    function getSpawnChance(marker: WorldEnemy): number | null {
        const char = marker.characters.find((c) => c.name === name);
        if (!char) return null;
        return char.spawnChance;
    }

    // Group markers by zone, sorted by spawn count descending, then by spawn
    // chance descending within each zone
    const groupedByZone = $derived.by(() => {
        const groups = new SvelteMap<string, WorldEnemy[]>();
        for (const marker of markers) {
            const existing = groups.get(marker.zone);
            if (existing) {
                existing.push(marker);
            } else {
                groups.set(marker.zone, [marker]);
            }
        }
        return [...groups.entries()]
            .sort((a, b) => b[1].length - a[1].length)
            .map(
                ([zone, zoneMarkers]) =>
                    [
                        zone,
                        [...zoneMarkers].sort(
                            (a, b) => (getSpawnChance(b) ?? 0) - (getSpawnChance(a) ?? 0)
                        )
                    ] as [string, WorldEnemy[]]
            );
    });

    function formatRespawnTime(seconds: number | null): string {
        if (seconds === null || seconds === 0) return 'zone re-entry';
        const minutes = Math.round(seconds / 60);
        if (minutes < 1) return `~${seconds}s`;
        if (minutes === 1) return '~1 min';
        return `~${minutes} min`;
    }

    function formatSpawnChance(chance: number): string {
        return `${Math.round(chance)}%`;
    }
</script>

<div class="space-y-4">
    <!-- Summary -->
    <div class="flex items-center justify-between">
        {#if levelRange}
            <div class="text-sm text-zinc-300">{levelRange}</div>
        {:else}
            <div></div>
        {/if}
        <WikiLink {name} />
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

    <!-- Spawn points grouped by zone -->
    <div class="space-y-3">
        {#each groupedByZone as [zone, zoneMarkers] (zone)}
            <div class="border-t border-zinc-700 pt-2">
                <div class="flex items-center justify-between mb-1.5">
                    <div class="text-xs font-medium text-zinc-300">{zoneMarkers[0].zoneName}</div>
                    <div class="text-xs text-zinc-500">
                        {zoneMarkers.length} spawn{zoneMarkers.length !== 1 ? 's' : ''}
                    </div>
                </div>
                <div class="space-y-1">
                    {#each zoneMarkers as marker (marker.stableKey)}
                        {@const chance = getSpawnChance(marker)}
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
                                    {#if chance !== null}
                                        <span class="text-zinc-300"
                                            >{formatSpawnChance(chance)} spawn</span
                                        >
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
