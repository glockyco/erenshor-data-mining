<script lang="ts">
    import type { WorldTreasureLoc } from '$lib/types/world-map';
    let { name, sites, onHoverSpawn, onSelectSpawn, onFocusAll }: {
        name: string;
        sites: WorldTreasureLoc[];
        onHoverSpawn: (key: string | null) => void;
        onSelectSpawn: (key: string) => void;
        onFocusAll: () => void;
    } = $props();
    const zones = $derived([...new Set(sites.map((site) => site.zone))]);
    const character = $derived([...sites[0].chests, ...sites[0].guardians].find((c) => c.name === name));
</script>

<div class="space-y-3 text-center text-xs text-zinc-300">
    <p>This encounter appears at treasure dig sites, not fixed enemy spawn points.</p>
    {#if character?.wikiPageName}
        <a class="inline-block text-blue-400 hover:underline" href="https://erenshor.wiki.gg/wiki/{encodeURIComponent(character.wikiPageName)}">{name} on the wiki</a>
    {/if}
    <button type="button" class="w-full rounded bg-zinc-700/50 px-3 py-2 hover:bg-zinc-700" onclick={onFocusAll}>Show all {sites.length} dig site{sites.length !== 1 ? 's' : ''}</button>
    {#each zones as zone (zone)}
        {@const zoneSites = sites.filter((site) => site.zone === zone)}
        <div class="space-y-1 border-t border-zinc-700 pt-2">
            <div class="font-medium">{zoneSites[0].zoneName}</div>
            {#each zoneSites as site, index (site.stableKey)}
                <button type="button" class="w-full rounded px-2 py-1.5 hover:bg-zinc-700/50" onmouseenter={() => onHoverSpawn(site.stableKey)} onmouseleave={() => onHoverSpawn(null)} onclick={() => onSelectSpawn(site.stableKey)}>
                    Dig site {index + 1} · Guardians {site.levelMin}–{site.levelMax}
                </button>
            {/each}
        </div>
    {/each}
</div>
