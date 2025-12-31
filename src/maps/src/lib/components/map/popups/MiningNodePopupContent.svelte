<script lang="ts">
    import type { WorldMiningNode } from '$lib/types/world-map';
    import WikiLink from '$lib/components/map/WikiLink.svelte';

    interface Props {
        marker: WorldMiningNode;
    }

    let { marker }: Props = $props();

    // Format respawn time
    function formatRespawnTime(seconds: number): string {
        if (seconds === 0) return 'Instant';
        const minutes = Math.round(seconds / 60);
        if (minutes < 1) return `${seconds}s`;
        if (minutes === 1) return '1 minute';
        return `${minutes} minutes`;
    }

    // Format drop chance (0-100 range from database)
    function formatDropChance(chance: number): string {
        return `${chance.toFixed(1)}%`;
    }
</script>

<div class="space-y-3">
    <!-- Items -->
    {#if marker.items.length > 0}
        <div class="rounded bg-zinc-800 p-3">
            <div class="text-xs text-zinc-500 uppercase tracking-wide mb-2">Possible Items</div>
            <div class="space-y-1.5">
                {#each marker.items as item, i (i)}
                    <div class="flex items-center justify-between gap-2 text-sm">
                        <span class="text-zinc-300 truncate min-w-0">{item.name}</span>
                        <div class="flex items-center gap-2 shrink-0">
                            <span class="text-zinc-500">{formatDropChance(item.dropChance)}</span>
                            <WikiLink name={item.name} />
                        </div>
                    </div>
                {/each}
            </div>
        </div>
    {:else}
        <div class="text-sm text-zinc-400">No item data available.</div>
    {/if}

    <!-- Respawn time -->
    <div class="text-xs text-zinc-400">
        Respawn: {formatRespawnTime(marker.respawnTime)}
    </div>
</div>
