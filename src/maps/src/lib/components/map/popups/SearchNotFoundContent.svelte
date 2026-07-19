<script lang="ts">
    import Search from '@lucide/svelte/icons/search';

    interface Props {
        searchType: 'enemy' | 'npc' | 'zone' | 'item';
        name: string;
        onSearchAlternative: (query: string) => void;
    }

    let { searchType, name, onSearchAlternative }: Props = $props();

    const typeLabels: Record<string, string> = {
        enemy: 'enemy',
        npc: 'NPC',
        zone: 'zone',
        item: 'item'
    };
</script>

<div class="space-y-4">
    <p class="text-sm text-zinc-300">
        This {typeLabels[searchType]} was not found on the map.
    </p>

    <p class="text-sm text-zinc-400">
        {#if searchType === 'item'}
            This item may only be obtainable in ways the map doesn't track yet.
        {:else}
            Some characters have special spawn conditions that aren't yet tracked by this map.
        {/if}
        If you believe this is an error, let us know on the
        <a href="https://discord.gg/erenshor" class="text-blue-400 underline hover:text-blue-300"
            >Erenshor Discord</a
        >.
    </p>

    <button
        type="button"
        onclick={() => onSearchAlternative(name)}
        class="flex w-full cursor-pointer items-center justify-center gap-2 rounded-md
               bg-zinc-700/50 px-3 py-2 text-sm text-zinc-300
               transition-colors hover:bg-zinc-700 hover:text-white"
    >
        <Search class="h-4 w-4" />
        Search for alternatives
    </button>
</div>
