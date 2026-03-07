<script lang="ts">
    import { Command } from 'bits-ui';
    import { searchMarkers, type SearchResult, type IndexEntry } from '$lib/map/search';
    import { Rarity } from '$lib/map-markers';
    import type { EntityData } from '$lib/map/live/types';
    import * as Drawer from '$lib/components/ui/drawer';
    import Skull from '@lucide/svelte/icons/skull';
    import User from '@lucide/svelte/icons/user';
    import MapIcon from '@lucide/svelte/icons/map';
    import Radio from '@lucide/svelte/icons/radio';

    // Live-only result type, separate from the static SearchResult union
    type LiveSearchResult = { kind: 'live'; entity: EntityData; zone: string };

    // Combined item for the rendered list
    type AnyResult = { kind: 'static'; result: SearchResult } | LiveSearchResult;

    interface Props {
        open: boolean;
        isDesktop: boolean;
        initialQuery?: string;
        index: IndexEntry[];
        liveEntities: EntityData[];
        liveZone: string | null;
        onselect: (result: SearchResult) => void;
        onliveselect: (entity: EntityData, zone: string) => void;
        onclose: () => void;
    }

    let {
        open = $bindable(),
        isDesktop,
        initialQuery = $bindable(''),
        index,
        liveEntities,
        liveZone,
        onselect,
        onliveselect,
        onclose
    }: Props = $props();

    let query = $state('');
    let staticResults = $state<SearchResult[]>([]);
    let liveResults = $state<LiveSearchResult[]>([]);
    let loading = $state(false);

    // Debounced search
    let searchTimeout: ReturnType<typeof setTimeout>;
    $effect(() => {
        clearTimeout(searchTimeout);
        if (query.length >= 2) {
            loading = true;
            searchTimeout = setTimeout(() => {
                staticResults = searchMarkers(query, index);
                liveResults = searchLiveEntities(query);
                loading = false;
            }, 150);
        } else {
            staticResults = [];
            liveResults = [];
            loading = false;
        }
    });

    // Seed query from initialQuery when opening, reset when closing
    $effect(() => {
        if (open) {
            if (initialQuery) {
                query = initialQuery;
                initialQuery = '';
            }
        } else {
            query = '';
            staticResults = [];
            liveResults = [];
        }
    });

    /**
     * Search live entities by name. Prefix matches first, then substring.
     * Capped at 5 results — live entities are transient and highly contextual.
     */
    function searchLiveEntities(q: string): LiveSearchResult[] {
        if (!liveZone || liveEntities.length === 0) return [];
        const lower = q.toLowerCase().trim();
        const zone = liveZone;
        const prefix: LiveSearchResult[] = [];
        const substring: LiveSearchResult[] = [];
        for (const entity of liveEntities) {
            const nameLower = entity.name.toLowerCase();
            if (nameLower.startsWith(lower)) {
                prefix.push({ kind: 'live', entity, zone });
            } else if (nameLower.includes(lower)) {
                substring.push({ kind: 'live', entity, zone });
            }
        }
        return [...prefix, ...substring].slice(0, 5);
    }

    function handleSelect(item: AnyResult) {
        if (item.kind === 'live') {
            onliveselect(item.entity, item.zone);
        } else {
            onselect(item.result);
        }
        open = false;
    }

    // Category display config for static results
    const categoryLabels: Record<SearchResult['type'], string> = {
        enemy: 'Enemy Spawn Points',
        npc: 'NPC Spawn Points',
        zone: 'Zones'
    };

    const staticCategoryOrder: SearchResult['type'][] = ['enemy', 'npc', 'zone'];

    function groupStaticByCategory(
        items: SearchResult[]
    ): [SearchResult['type'], SearchResult[]][] {
        const groups: Partial<Record<SearchResult['type'], SearchResult[]>> = {};
        for (const item of items) {
            (groups[item.type] ??= []).push(item);
        }
        return staticCategoryOrder.filter((cat) => groups[cat]).map((cat) => [cat, groups[cat]!]);
    }

    function getStaticResultLabel(result: SearchResult): string {
        return result.name;
    }

    function getStaticResultSublabel(result: SearchResult): string {
        switch (result.type) {
            case 'enemy': {
                const parts: string[] = [];
                if (result.effectiveRarity === Rarity.unique) parts.push('Unique');
                else if (result.effectiveRarity === Rarity.rare) parts.push('Rare');
                parts.push(`${result.spawnCount} spawn${result.spawnCount !== 1 ? 's' : ''}`);
                parts.push(`${result.zoneCount} zone${result.zoneCount !== 1 ? 's' : ''}`);
                return parts.join(' · ');
            }
            case 'npc': {
                const parts: string[] = [];
                if (result.isVendor) parts.push('Vendor');
                parts.push(`${result.spawnCount} spawn${result.spawnCount !== 1 ? 's' : ''}`);
                parts.push(`${result.zoneCount} zone${result.zoneCount !== 1 ? 's' : ''}`);
                return parts.join(' · ');
            }
            case 'zone':
                return 'Zone';
        }
    }

    function getStaticResultValue(result: SearchResult): string {
        switch (result.type) {
            case 'enemy':
                return `enemy-${result.name}`;
            case 'npc':
                return `npc-${result.name}`;
            case 'zone':
                return `zone-${result.key}`;
        }
    }

    /** Human-readable label for an entity type. */
    function getLiveEntityTypeLabel(entity: EntityData): string {
        switch (entity.entityType) {
            case 'player':
                return 'Player';
            case 'simplayer':
                return 'SimPlayer';
            case 'pet':
                return 'Pet';
            case 'npc_friendly':
                return 'Friendly NPC';
            case 'npc_enemy':
                return 'Enemy';
        }
    }

    /** Sub-label for a live entity result. */
    function getLiveResultSublabel(entity: EntityData): string {
        const parts: string[] = [getLiveEntityTypeLabel(entity)];
        if (entity.level != null) parts.push(`Lv ${entity.level}`);
        // Rarity only meaningful for npc_enemy
        if (entity.entityType === 'npc_enemy' && entity.rarity) {
            const rarityLabel =
                entity.rarity === 'boss' ? 'Boss' : entity.rarity === 'rare' ? 'Rare' : 'Common';
            parts.push(rarityLabel);
        }
        // Class for player / simplayer
        if (entity.characterClass) parts.push(entity.characterClass);
        // Owner for pets
        if (entity.owner) parts.push(`owned by ${entity.owner}`);
        return parts.join(' · ');
    }

    // Scroll fix for bits-ui Command
    function fixScrollIntoView(node: HTMLElement) {
        function isFullyVisible(el: HTMLElement, container: HTMLElement): boolean {
            const elRect = el.getBoundingClientRect();
            const containerRect = container.getBoundingClientRect();
            return elRect.top >= containerRect.top && elRect.bottom <= containerRect.bottom;
        }

        const observer = new MutationObserver((mutations) => {
            for (const mutation of mutations) {
                if (mutation.attributeName !== 'aria-selected') continue;
                const target = mutation.target as HTMLElement;
                if (target.getAttribute('aria-selected') !== 'true') continue;

                const list = node.querySelector('[data-command-list]');
                if (list && !isFullyVisible(target, list as HTMLElement)) {
                    target.scrollIntoView({ block: 'nearest' });
                }
            }
        });

        observer.observe(node, {
            subtree: true,
            attributes: true,
            attributeFilter: ['aria-selected']
        });

        return { destroy: () => observer.disconnect() };
    }

    const hasResults = $derived(staticResults.length > 0 || liveResults.length > 0);
</script>

{#snippet searchContent()}
    <div class="flex items-center border-b border-zinc-700 px-3">
        <svg
            class="mr-2 h-4 w-4 shrink-0 text-zinc-500"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
        >
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
        <Command.Input
            bind:value={query}
            autofocus
            placeholder="Search enemies, NPCs, zones..."
            class="flex h-12 w-full bg-transparent text-sm text-white placeholder:text-zinc-500
                   outline-none disabled:cursor-not-allowed disabled:opacity-50"
        />
    </div>
    <div use:fixScrollIntoView>
        <Command.List class="max-h-80 overflow-y-auto px-2 py-2">
            {#if loading}
                <Command.Loading>
                    <div class="py-6 text-center text-sm text-zinc-500">Searching...</div>
                </Command.Loading>
            {:else if query.length < 2}
                <Command.Empty>
                    <div class="py-6 text-center text-sm text-zinc-500">
                        Type at least 2 characters to search
                    </div>
                </Command.Empty>
            {:else if !hasResults}
                <Command.Empty>
                    <div class="py-6 text-center text-sm text-zinc-500">
                        No results found for "{query}"
                    </div>
                </Command.Empty>
            {:else}
                <!-- Live entities first -->
                {#if liveResults.length > 0}
                    <Command.Group>
                        <Command.GroupHeading
                            class="px-2 py-1.5 text-xs font-semibold text-zinc-500 uppercase tracking-wide"
                        >
                            Live Entities
                        </Command.GroupHeading>
                        <Command.GroupItems>
                            {#each liveResults as item (item.entity.id)}
                                <Command.Item
                                    value={`live-${item.entity.id}`}
                                    onSelect={() => handleSelect(item)}
                                    class="flex items-center gap-3 rounded-lg px-2 py-2
                                           text-sm text-zinc-300 cursor-pointer
                                           aria-selected:bg-zinc-700 aria-selected:text-white"
                                >
                                    <Radio class="h-4 w-4 shrink-0 text-lime-400" />
                                    <div class="min-w-0 flex-1">
                                        <div class="truncate">{item.entity.name}</div>
                                        <div class="text-xs text-zinc-500 truncate">
                                            {getLiveResultSublabel(item.entity)}
                                        </div>
                                    </div>
                                </Command.Item>
                            {/each}
                        </Command.GroupItems>
                    </Command.Group>
                {/if}

                <!-- Static results grouped by category -->
                {#each groupStaticByCategory(staticResults) as [category, items] (category)}
                    <Command.Group>
                        <Command.GroupHeading
                            class="px-2 py-1.5 text-xs font-semibold text-zinc-500 uppercase tracking-wide"
                        >
                            {categoryLabels[category]}
                        </Command.GroupHeading>
                        <Command.GroupItems>
                            {#each items as result (getStaticResultValue(result))}
                                <Command.Item
                                    value={getStaticResultValue(result)}
                                    onSelect={() => handleSelect({ kind: 'static', result })}
                                    class="flex items-center gap-3 rounded-lg px-2 py-2
                                           text-sm text-zinc-300 cursor-pointer
                                           aria-selected:bg-zinc-700 aria-selected:text-white"
                                >
                                    {#if result.type === 'enemy'}
                                        <Skull class="h-4 w-4 shrink-0 text-amber-500" />
                                    {:else if result.type === 'npc'}
                                        <User class="h-4 w-4 shrink-0 text-sky-500" />
                                    {:else}
                                        <MapIcon class="h-4 w-4 shrink-0 text-purple-500" />
                                    {/if}
                                    <div class="min-w-0 flex-1">
                                        <div class="truncate">{getStaticResultLabel(result)}</div>
                                        <div class="text-xs text-zinc-500 truncate">
                                            {getStaticResultSublabel(result)}
                                        </div>
                                    </div>
                                </Command.Item>
                            {/each}
                        </Command.GroupItems>
                    </Command.Group>
                {/each}
            {/if}
        </Command.List>
    </div>
{/snippet}

{#if isDesktop}
    {#if open}
        <!-- Desktop: Backdrop -->
        <button
            type="button"
            class="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm"
            aria-label="Close search"
            onclick={() => {
                open = false;
                onclose();
            }}
        ></button>

        <!-- Desktop: Command palette -->
        <div
            class="fixed left-1/2 top-[20%] z-50 w-full max-w-lg -translate-x-1/2
                   rounded-xl border border-zinc-700 bg-zinc-900 shadow-2xl"
        >
            <Command.Root shouldFilter={false}>
                {@render searchContent()}
            </Command.Root>
        </div>
    {/if}
{:else}
    <!-- Mobile: Command palette in bottom drawer -->
    <Drawer.Root bind:open shouldScaleBackground={false}>
        <Drawer.Content>
            <Drawer.Header class="sr-only">
                <Drawer.Title>Search Map</Drawer.Title>
            </Drawer.Header>
            <Command.Root shouldFilter={false} class="bg-transparent">
                {@render searchContent()}
            </Command.Root>
        </Drawer.Content>
    </Drawer.Root>
{/if}
