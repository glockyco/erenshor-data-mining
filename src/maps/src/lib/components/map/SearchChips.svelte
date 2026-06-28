<script lang="ts">
    import { CHIP_CONFIG, type Category } from './search-chips';

    interface Props {
        activeCategory: Category;
        counts: Map<string, number>;
        onSelect: (cat: Category) => void;
    }

    let { activeCategory, counts, onSelect }: Props = $props();

    // Visible chips: All always shows; Live only when present; static types
    // always show (greyed when zero).
    const visibleChips = $derived(
        CHIP_CONFIG.filter((c) => {
            if (c.key === 'all') return true;
            if (c.key === 'live') return counts.has(c.key);
            return true;
        })
    );
</script>

<div
    class="flex items-center gap-1.5 px-2 py-1.5"
    role="group"
    aria-label="Filter by category"
>
    {#each visibleChips as chip (chip.key)}
        {@const count = counts.get(chip.key) ?? 0}
        {@const isActive = activeCategory === chip.key}
        {@const isDisabled = count === 0 && chip.key !== 'all'}
        <button
            type="button"
            class="rounded-full px-2.5 py-1 text-xs font-medium transition-colors
                   {isActive
                ? 'bg-accent text-accent-ink'
                : 'bg-surface-2 text-muted hover:text-ink'}
                   {isDisabled ? 'opacity-40 cursor-not-allowed' : ''}"
            aria-pressed={isActive}
            disabled={isDisabled}
            onclick={() => onSelect(chip.key)}
        >
            {chip.label}
            {#if count > 0}
                <span class="ml-1 opacity-70">({count})</span>
            {/if}
        </button>
    {/each}
</div>
