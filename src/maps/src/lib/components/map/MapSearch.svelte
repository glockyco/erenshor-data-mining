<script lang="ts">
    import { Command } from 'bits-ui';
    import { searchMarkers, type SearchResult, type IndexEntry } from '$lib/map/search';
    import Skull from '@lucide/svelte/icons/skull';
    import User from '@lucide/svelte/icons/user';
    import MapIcon from '@lucide/svelte/icons/map';

    interface Props {
        open: boolean;
        index: IndexEntry[];
        onselect: (result: SearchResult) => void;
        onclose: () => void;
    }

    let { open = $bindable(), index, onselect, onclose }: Props = $props();

    let query = $state('');
    let results = $state<SearchResult[]>([]);
    let loading = $state(false);

    // Debounced search
    let searchTimeout: ReturnType<typeof setTimeout>;
    $effect(() => {
        clearTimeout(searchTimeout);
        if (query.length >= 2) {
            loading = true;
            searchTimeout = setTimeout(() => {
                results = searchMarkers(query, index);
                loading = false;
            }, 150);
        } else {
            results = [];
            loading = false;
        }
    });

    // Reset when dialog closes
    $effect(() => {
        if (!open) {
            query = '';
            results = [];
        }
    });

    function handleSelect(result: SearchResult) {
        onselect(result);
        open = false;
    }

    // Category display config
    const categoryLabels: Record<SearchResult['type'], string> = {
        enemy: 'Enemies',
        npc: 'NPCs',
        zone: 'Zones'
    };

    const categoryOrder: SearchResult['type'][] = ['enemy', 'npc', 'zone'];

    function groupByCategory(items: SearchResult[]): [SearchResult['type'], SearchResult[]][] {
        const groups: Partial<Record<SearchResult['type'], SearchResult[]>> = {};
        for (const item of items) {
            (groups[item.type] ??= []).push(item);
        }
        return categoryOrder.filter((cat) => groups[cat]).map((cat) => [cat, groups[cat]!]);
    }

    function getResultLabel(result: SearchResult): string {
        switch (result.type) {
            case 'enemy':
                return result.name;
            case 'npc':
                return result.name;
            case 'zone':
                return result.name;
        }
    }

    function getResultSublabel(result: SearchResult): string {
        switch (result.type) {
            case 'enemy': {
                const parts: string[] = [];
                if (result.isUnique) parts.push('Unique');
                else if (result.isRare) parts.push('Rare');
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

    function getResultValue(result: SearchResult): string {
        switch (result.type) {
            case 'enemy':
                return `enemy-${result.name}`;
            case 'npc':
                return `npc-${result.name}`;
            case 'zone':
                return `zone-${result.key}`;
        }
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
</script>

{#if open}
    <!-- Backdrop -->
    <!-- svelte-ignore a11y_no_static_element_interactions a11y_click_events_have_key_events -->
    <div
        class="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm"
        onclick={() => {
            open = false;
            onclose();
        }}
    ></div>

    <!-- Command palette -->
    <div
        class="fixed left-1/2 top-[20%] z-50 w-full max-w-lg -translate-x-1/2
		       rounded-xl border border-zinc-700 bg-zinc-900 shadow-2xl"
    >
        <Command.Root shouldFilter={false}>
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
                    {:else if results.length === 0}
                        <Command.Empty>
                            <div class="py-6 text-center text-sm text-zinc-500">
                                No results found for "{query}"
                            </div>
                        </Command.Empty>
                    {:else}
                        {#each groupByCategory(results) as [category, items] (category)}
                            <Command.Group>
                                <Command.GroupHeading
                                    class="px-2 py-1.5 text-xs font-semibold text-zinc-500 uppercase tracking-wide"
                                >
                                    {categoryLabels[category]}
                                </Command.GroupHeading>
                                <Command.GroupItems>
                                    {#each items as result (getResultValue(result))}
                                        <Command.Item
                                            value={getResultValue(result)}
                                            onSelect={() => handleSelect(result)}
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
                                                <div class="truncate">{getResultLabel(result)}</div>
                                                <div class="text-xs text-zinc-500 truncate">
                                                    {getResultSublabel(result)}
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
        </Command.Root>
    </div>
{/if}
