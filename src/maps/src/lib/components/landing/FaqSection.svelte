<script lang="ts">
    import SectionHead from './SectionHead.svelte';
    import Icon from './Icon.svelte';
    import { line } from './icons';
    import { FAQ_ITEMS, type FaqCategory } from '$lib/seo/faq';

    // Two rendered clusters over the flat, category-ordered array. Each group
    // carries its items' global indices so the open-state array stays flat and
    // aligned with FAQ_ITEMS.
    const GROUP_LABELS: Record<FaqCategory, string> = {
        tools: 'Using this site',
        game: 'About the game'
    };
    const GROUPS = (['tools', 'game'] satisfies FaqCategory[]).map((category) => ({
        label: GROUP_LABELS[category],
        entries: FAQ_ITEMS.map((item, index) => ({ item, index })).filter(
            ({ item }) => item.category === category
        )
    }));

    // First question open by default, the rest collapsed. Each <details> stays
    // independently user-toggleable through the binding; the bulk control just
    // sets every entry at once. All answers render regardless of state, so this
    // is a progressive enhancement that never hides content from crawlers.
    let open = $state(FAQ_ITEMS.map((_, i) => i === 0));
    const allOpen = $derived(open.every(Boolean));

    function toggleAll() {
        const next = !allOpen;
        open = open.map(() => next);
    }
</script>

<section id="faq">
    <SectionHead title="Common questions">
        <button type="button" class="toggle-all" onclick={toggleAll}>
            {allOpen ? 'Collapse all' : 'Expand all'}
        </button>
    </SectionHead>
    <div class="faq">
        {#each GROUPS as group (group.label)}
            <div class="group">
                <h3 class="group-label">{group.label}</h3>
                {#each group.entries as { item, index } (item.question)}
                    <details class="qa" bind:open={open[index]}>
                        <summary>
                            <h4>{item.question}</h4>
                            <span class="chev" aria-hidden="true">
                                <Icon paths={line.chevron} stroke class="block h-[18px] w-[18px]" />
                            </span>
                        </summary>
                        <div class="answer">
                            <p>
                                {#each item.answer as seg, j (j)}
                                    {#if typeof seg === 'string'}
                                        {seg}
                                    {:else}
                                        <a href={seg.href}>{seg.text}</a>
                                    {/if}
                                {/each}
                            </p>
                        </div>
                    </details>
                {/each}
            </div>
        {/each}
    </div>
</section>

<style>
    #faq {
        padding: clamp(30px, 4.2vw, 56px) 0;
    }
    .toggle-all {
        margin: 0;
        padding: 4px 2px;
        border: none;
        background: none;
        cursor: pointer;
        font-family: var(--font-mono, var(--font-display));
        font-size: 0.8rem;
        letter-spacing: 0.02em;
        color: var(--color-muted);
        white-space: nowrap;
        transition: color 0.15s;
    }
    .toggle-all:hover {
        color: var(--color-accent);
    }
    .toggle-all:focus-visible {
        outline: 2px solid var(--color-accent);
        outline-offset: 2px;
        border-radius: 3px;
    }
    .faq {
        display: flex;
        flex-direction: column;
        gap: clamp(26px, 3vw, 40px);
    }
    .group-label {
        margin: 0;
        padding: 0 0 6px;
        border-bottom: 1px solid var(--color-line);
        font-family: var(--font-mono, var(--font-display));
        font-size: 0.8rem;
        font-weight: 600;
        letter-spacing: 0.02em;
        color: var(--color-muted);
    }
    .qa {
        border-bottom: 1px solid var(--color-line);
    }
    .qa:last-child {
        border-bottom: none;
    }
    .qa summary {
        list-style: none;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 20px;
        min-height: 44px;
        padding: 18px 0;
        cursor: pointer;
    }
    .qa summary::-webkit-details-marker {
        display: none;
    }
    .qa summary:focus-visible {
        outline: 2px solid var(--color-accent);
        outline-offset: 3px;
        border-radius: 3px;
    }
    .qa h4 {
        margin: 0;
        font-family: var(--font-display);
        font-size: 1.12rem;
        font-weight: 700;
        color: var(--color-ink);
        transition: color 0.15s;
    }
    .qa summary:hover h4 {
        color: var(--color-accent);
    }
    .chev {
        flex: none;
        display: flex;
        color: var(--color-muted);
        transition:
            transform 0.15s,
            color 0.15s;
    }
    .qa summary:hover .chev,
    .qa[open] > summary .chev {
        color: var(--color-accent);
    }
    .qa[open] > summary .chev {
        transform: rotate(90deg);
    }
    .answer {
        padding: 0 0 22px;
    }
    .answer p {
        max-width: 64ch;
        margin: 0;
        line-height: 1.6;
        color: color-mix(in oklab, var(--color-ink) 84%, var(--color-bg));
    }
    .answer a {
        color: var(--color-accent);
        text-decoration: none;
        border-bottom: 1px solid color-mix(in srgb, var(--color-accent) 45%, transparent);
    }
    @media (prefers-reduced-motion: no-preference) {
        .qa[open] > .answer {
            animation: faq-reveal 0.18s ease-out;
        }
    }
    @keyframes faq-reveal {
        from {
            opacity: 0;
            transform: translateY(-2px);
        }
        to {
            opacity: 1;
            transform: none;
        }
    }
    @media (prefers-reduced-motion: reduce) {
        .chev {
            transition: none;
        }
    }
</style>
