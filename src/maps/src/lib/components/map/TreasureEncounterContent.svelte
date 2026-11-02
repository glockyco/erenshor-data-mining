<script lang="ts">
    import type { TreasureLocMarker } from '$lib/map-markers';
    let { marker }: { marker: TreasureLocMarker } = $props();
</script>

<div class="space-y-3 text-center text-xs text-zinc-300">
    <div>Read the map at {marker.minReadingLevel === 1 ? 'any level' : `level ${marker.minReadingLevel} or higher`}</div>
    <div>
        <div class="mb-1 font-medium text-zinc-100">Chest by your level when you dig</div>
        {#each marker.chests as chest (chest.stableKey)}
            <div>
                {chest.digLevelMin}{chest.digLevelMax === null ? ' or higher' : `–${chest.digLevelMax}`}:
                {#if chest.wikiPageName}
                    <a class="text-blue-400 hover:underline" href="https://erenshor.wiki.gg/wiki/{encodeURIComponent(chest.wikiPageName)}">{chest.name}</a>
                {:else}{chest.name}{/if}
            </div>
        {/each}
    </div>
    <div>
        <div class="mb-1 font-medium text-zinc-100">Guardians (scale with your level)</div>
        {#each marker.guardians as guardian (guardian.stableKey)}
            <div>
                {#if guardian.wikiPageName}
                    <a class="text-blue-400 hover:underline" href="https://erenshor.wiki.gg/wiki/{encodeURIComponent(guardian.wikiPageName)}">{guardian.name}</a>
                {:else}{guardian.name}{/if}: Level {guardian.levelMin}–{guardian.levelMax}
            </div>
        {/each}
    </div>
    <a class="inline-block text-blue-400 hover:underline" href="https://erenshor.wiki.gg/wiki/Treasure_Hunting">Treasure Hunting</a>
</div>
