<script lang="ts">
    import type { WorldEnemy, WorldNpc } from '$lib/types/world-map';

    interface Props {
        markers: (WorldEnemy | WorldNpc)[];
        onHoverSpawn: (stableKey: string | null) => void;
        onFocusSpawn: (stableKey: string) => void;
    }

    let { markers, onHoverSpawn, onFocusSpawn }: Props = $props();

    function markerName(marker: WorldEnemy | WorldNpc): string {
        return marker.characters.map((character) => character.name).join(', ') || 'Unnamed spawn';
    }
</script>

<div class="space-y-2">
    <p class="text-sm text-zinc-300">
        Multiple spawn markers overlap at this screen location. Select one to inspect it.
    </p>
    <div class="space-y-1">
        {#each markers as marker (marker.stableKey)}
            <button
                type="button"
                class="flex w-full items-center justify-between rounded bg-zinc-800 px-3 py-2 text-left transition hover:bg-zinc-700 focus:outline-none focus:ring-1 focus:ring-cyan-400"
                onmouseenter={() => onHoverSpawn(marker.stableKey)}
                onmouseleave={() => onHoverSpawn(null)}
                onclick={() => onFocusSpawn(marker.stableKey)}
            >
                <span class="text-sm font-medium text-zinc-100">{markerName(marker)}</span>
                <span class="ml-3 text-xs uppercase tracking-wide text-zinc-500">
                    {marker.category === 'enemy' ? 'Enemy' : 'NPC'}
                </span>
            </button>
        {/each}
    </div>
</div>
