<script lang="ts">
    import Skull from '@lucide/svelte/icons/skull';
    import User from '@lucide/svelte/icons/user';
    import type { WorldEnemy, WorldNpc } from '$lib/types/world-map';
    import { Rarity } from '$lib/map-markers';

    interface Props {
        markers: (WorldEnemy | WorldNpc)[];
        onHoverSpawn: (stableKey: string | null) => void;
        onFocusSpawn: (stableKey: string) => void;
    }

    let { markers, onHoverSpawn, onFocusSpawn }: Props = $props();

    function markerSummary(marker: WorldEnemy | WorldNpc): { first: string; more: number } {
        const sortedCharacters = [...marker.characters].sort((a, b) => {
            const rarity = a.effectiveRarity - b.effectiveRarity;
            return rarity !== 0 ? rarity : a.name.localeCompare(b.name);
        });
        const [first, ...rest] = sortedCharacters.map((character) => character.name);
        return { first: first || 'Unnamed spawn', more: rest.length };
    }

    function markerRarity(marker: WorldEnemy | WorldNpc): Rarity {
        if (marker.characters.some((character) => character.effectiveRarity === Rarity.unique)) {
            return Rarity.unique;
        }
        if (marker.characters.some((character) => character.effectiveRarity === Rarity.rare)) {
            return Rarity.rare;
        }
        return Rarity.common;
    }

    function iconClass(marker: WorldEnemy | WorldNpc): string {
        if (marker.category === 'npc') return 'text-sky-500';
        switch (markerRarity(marker)) {
            case Rarity.unique:
                return 'text-violet-700';
            case Rarity.rare:
                return 'text-rose-600';
            default:
                return 'text-amber-600';
        }
    }

    const sortedMarkers = $derived(
        [...markers].sort((a, b) => {
            const category = (a.category === 'npc' ? 1 : 0) - (b.category === 'npc' ? 1 : 0);
            if (category !== 0) return category;
            const rarity = markerRarity(a) - markerRarity(b);
            if (rarity !== 0) return rarity;
            return markerSummary(a).first.localeCompare(markerSummary(b).first);
        })
    );
</script>

<div class="space-y-1">
    {#each sortedMarkers as marker (marker.stableKey)}
        {@const summary = markerSummary(marker)}
        <button
            type="button"
            class="flex w-full cursor-pointer items-center gap-2 rounded bg-zinc-800 px-3 py-2 text-left transition hover:bg-zinc-700 focus:outline-none focus:ring-1 focus:ring-cyan-400"
            onmouseenter={() => onHoverSpawn(marker.stableKey)}
            onmouseleave={() => onHoverSpawn(null)}
            onclick={() => onFocusSpawn(marker.stableKey)}
        >
            {#if marker.category === 'enemy'}
                <Skull size={16} strokeWidth={2.5} class={iconClass(marker)} aria-hidden="true" />
            {:else}
                <User size={16} strokeWidth={2.5} class={iconClass(marker)} aria-hidden="true" />
            {/if}
            <span class="min-w-0 flex-1 truncate text-sm font-medium text-zinc-100">
                {summary.first}
                {#if summary.more > 0}
                    <span class="font-normal text-zinc-500"> +{summary.more} more</span>
                {/if}
            </span>
        </button>
    {/each}
</div>
