<script lang="ts">
    import Icon from './Icon.svelte';
    import { line } from './icons';
    import { SvelteSet } from 'svelte/reactivity';

    // The landing's sections, in document order. `short` shows in the pill;
    // `label` in the open menu. Each `id` is a real section anchor on the page.
    const SECTIONS = [
        { id: 'tools', label: 'Tools & resources', short: 'Tools' },
        { id: 'about', label: 'About Erenshor', short: 'About' },
        { id: 'faq', label: 'Common questions', short: 'FAQ' },
        { id: 'community', label: 'The game & community', short: 'Community' }
    ] as const;
    const IDS = SECTIONS.map((s) => s.id) as readonly string[];

    let activeId = $state<string>(SECTIONS[0].id);
    let menuOpen = $state(false);
    let coords = $state<Record<string, { y: number }>>({});
    const active = $derived(SECTIONS.find((s) => s.id === activeId) ?? SECTIONS[0]);

    // Active-section indicator. A *passive* observer: it only reads which section
    // is in view to light up the current waypoint. It never moves the scroll —
    // navigation is plain `<a href="#id">` anchors, so nothing hijacks scrolling.
    $effect(() => {
        const visible = new SvelteSet<Element>();

        const atBottom = () =>
            window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 2;

        const select = () => {
            if (atBottom()) {
                activeId = IDS[IDS.length - 1];
                return;
            }
            if (visible.size === 0) return;
            const topmost = [...visible].reduce((a, b) =>
                a.getBoundingClientRect().top < b.getBoundingClientRect().top ? a : b
            );
            if (IDS.includes(topmost.id)) activeId = topmost.id;
        };

        const observer = new IntersectionObserver(
            (entries) => {
                for (const e of entries) {
                    if (e.isIntersecting) visible.add(e.target);
                    else visible.delete(e.target);
                }
                select();
            },
            { rootMargin: '-25% 0% -65% 0%', threshold: 0 }
        );

        window.addEventListener('scroll', select, { passive: true });
        window.addEventListener('resize', select);
        for (const id of IDS) {
            const el = document.getElementById(id);
            if (el) observer.observe(el);
        }
        select();

        return () => {
            observer.disconnect();
            window.removeEventListener('scroll', select);
            window.removeEventListener('resize', select);
        };
    });

    // Close the menu on outside pointer or Escape.
    $effect(() => {
        if (!menuOpen) return;
        const onDown = (e: PointerEvent) => {
            if (!(e.target as Element).closest('.lens')) menuOpen = false;
        };
        const onKey = (e: KeyboardEvent) => {
            if (e.key === 'Escape') menuOpen = false;
        };
        window.addEventListener('pointerdown', onDown);
        window.addEventListener('keydown', onKey);
        return () => {
            window.removeEventListener('pointerdown', onDown);
            window.removeEventListener('keydown', onKey);
        };
    });

    // Each waypoint's depth (Y) for the menu, read from the value the survey tag
    // stamped on itself (see coordinates.ts) so the menu shows exactly the
    // coordinate beside the heading — one source of truth, no re-measuring.
    function measure() {
        const next: Record<string, { y: number }> = {};
        for (const id of IDS) {
            const tag = document.getElementById(id)?.querySelector<HTMLElement>('.coord-tag');
            const y = tag?.dataset.surveyY;
            if (y != null) next[id] = { y: Number(y) };
        }
        coords = next;
    }

    function toggle() {
        if (!menuOpen) measure();
        menuOpen = !menuOpen;
    }
</script>

<div class="lens">
    {#if menuOpen}
        <nav class="menu" id="lens-menu" aria-label="Jump to section">
            <div class="list">
                <a class="top" href="#top" onclick={() => (menuOpen = false)}>
                    <span class="arrow" aria-hidden="true">↑</span>
                    <span class="label">Back to top</span>
                </a>
                <div class="rule" aria-hidden="true"></div>
                {#each SECTIONS as s, i (s.id)}
                    <a
                        class="wp"
                        class:active={s.id === activeId}
                        href="#{s.id}"
                        aria-current={s.id === activeId ? 'true' : undefined}
                        style="--i:{i}"
                        onclick={() => (menuOpen = false)}
                    >
                        <span class="mark" aria-hidden="true">
                            <Icon paths={line.crosshair} stroke class="block h-[13px] w-[13px]" />
                        </span>
                        <span class="idx">{String(i + 1).padStart(2, '0')}</span>
                        <span class="name">{s.label}</span>
                        <span class="coord">
                            <b>Y</b>
                            <span class="num">{coords[s.id]?.y ?? '—'}</span>
                        </span>
                    </a>
                {/each}
            </div>
        </nav>
    {/if}

    <button
        type="button"
        class="pill"
        aria-expanded={menuOpen}
        aria-controls="lens-menu"
        aria-label="Jump to section"
        onclick={toggle}
    >
        <span class="hud-xy"><b>X</b> 0 · <b>Y</b> 0</span>
        <span class="sep" aria-hidden="true">·</span>
        <span class="sect">{active.short}</span>
        <span class="caret" class:open={menuOpen} aria-hidden="true">
            <Icon paths={line.chevron} stroke class="block h-[13px] w-[13px]" />
        </span>
    </button>
</div>

<style>
    /* Spacing scale for the whole component:
         18px  viewport offset
         12px  horizontal rhythm (pill padding, row padding, column gap)
         10px  row vertical padding
          8px  between pill and menu, pill v-padding, pill inner gap
          6px  menu frame inset, coord inner gap */
    .lens {
        position: fixed;
        right: 18px;
        bottom: 18px;
        z-index: 60;
        display: flex;
        flex-direction: column;
        align-items: flex-end;
        gap: 8px;
    }

    .pill {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        margin: 0;
        padding: 8px 12px;
        border: 1px solid var(--color-line);
        border-radius: 10px;
        background: color-mix(in oklab, var(--color-surface) 90%, var(--color-bg));
        box-shadow: 0 8px 26px rgba(0, 0, 0, 0.4);
        cursor: pointer;
        font-family: var(--font-mono);
        font-size: 0.74rem;
        letter-spacing: 0.08em;
        line-height: 1;
        color: var(--color-muted);
        transition:
            border-color 0.15s,
            color 0.15s;
    }
    .pill:hover {
        border-color: var(--color-accent);
    }
    .pill:focus-visible {
        outline: 2px solid var(--color-accent);
        outline-offset: 2px;
    }
    .hud-xy :global(b) {
        color: var(--color-accent);
        font-weight: 500;
    }
    .sep {
        color: var(--color-line);
    }
    .sect {
        color: var(--color-ink);
        font-weight: 500;
        letter-spacing: 0.04em;
    }
    .caret {
        display: flex;
        color: var(--color-muted);
        transform: rotate(-90deg);
        transition: transform 0.18s;
    }
    .caret.open {
        transform: rotate(90deg);
    }
    .pill:hover .caret {
        color: var(--color-accent);
    }

    .menu {
        width: max-content;
        max-width: calc(100vw - 28px);
        overflow: hidden;
        border: 1px solid var(--color-line);
        border-radius: 12px;
        background: color-mix(in oklab, var(--color-surface) 93%, var(--color-bg));
        box-shadow: 0 12px 34px rgba(0, 0, 0, 0.5);
    }

    /* One grid for the whole menu so every row shares columns: the marker, the
       index, the name, and the Y reading each line up across rows (subgrid). */
    .list {
        display: grid;
        grid-template-columns: auto auto auto auto;
        column-gap: 12px;
        padding: 6px;
    }
    .top,
    .wp {
        grid-column: 1 / -1;
        display: grid;
        grid-template-columns: subgrid;
        align-items: center;
        padding: 10px 12px;
        border-radius: 8px;
        text-decoration: none;
        color: var(--color-ink);
        transition:
            background 0.14s,
            color 0.14s;
    }
    .top:hover,
    .top:focus-visible,
    .wp:hover,
    .wp:focus-visible {
        background: color-mix(in oklab, var(--color-accent) 12%, transparent);
    }
    .top:focus-visible,
    .wp:focus-visible {
        outline: 1px solid color-mix(in oklab, var(--color-accent) 55%, transparent);
        outline-offset: -1px;
    }

    /* Hairline divider between the action and the section list; its own element
       so each row keeps an identical rounded hover. */
    .rule {
        grid-column: 1 / -1;
        height: 1px;
        margin: 2px 6px;
        background: var(--color-line);
    }

    /* Back to top spans the index gap so its label aligns with the section names
       and its arrow aligns with the waypoint crosshairs. */
    .top {
        font-family: var(--font-mono);
        font-size: 0.72rem;
        letter-spacing: 0.16em;
        text-transform: uppercase;
        color: var(--color-muted);
    }
    .top:hover,
    .top:focus-visible {
        color: var(--color-accent);
    }
    .top .arrow {
        grid-column: 1;
        display: flex;
        justify-content: center;
        color: var(--color-accent);
    }
    .top .label {
        grid-column: 3 / -1;
    }

    .wp .mark {
        display: flex;
        color: var(--color-accent);
        opacity: 0;
        transition: opacity 0.14s;
    }
    .wp:hover .mark,
    .wp:focus-visible .mark {
        opacity: 0.5;
    }
    .wp.active .mark {
        opacity: 1;
    }
    .wp .idx {
        font-family: var(--font-mono);
        font-size: 0.72rem;
        color: var(--color-muted);
        font-variant-numeric: tabular-nums;
    }
    .wp .name {
        font-family: var(--font-display);
        font-size: 0.95rem;
        font-weight: 400;
        letter-spacing: 0.01em;
        white-space: nowrap;
    }
    .wp .coord {
        display: inline-grid;
        grid-template-columns: auto 4ch;
        align-items: baseline;
        column-gap: 6px;
        font-family: var(--font-mono);
        font-size: 0.68rem;
        letter-spacing: 0.04em;
        color: var(--color-muted);
        font-variant-numeric: tabular-nums;
    }
    .wp .coord b {
        color: var(--color-accent);
        font-weight: 500;
    }
    .wp .coord .num {
        text-align: right;
    }
    .wp.active .idx,
    .wp.active .name {
        color: var(--color-accent);
    }

    @media (prefers-reduced-motion: no-preference) {
        .menu {
            animation: lens-in 0.16s ease-out;
        }
        .top {
            animation: wp-in 0.24s ease-out backwards;
            animation-delay: 30ms;
        }
        .wp {
            animation: wp-in 0.24s ease-out backwards;
            animation-delay: calc(70ms + var(--i) * 35ms);
        }
    }
    @keyframes lens-in {
        from {
            opacity: 0;
            transform: translateY(6px);
        }
        to {
            opacity: 1;
            transform: none;
        }
    }
    @keyframes wp-in {
        from {
            opacity: 0;
            transform: translateX(7px);
        }
        to {
            opacity: 1;
            transform: none;
        }
    }
    @media (prefers-reduced-motion: reduce) {
        .caret {
            transition: none;
        }
    }

    /* No cursor, no live coordinate. Keep the pill as the section nav. */
    @media (pointer: coarse) {
        .hud-xy,
        .pill .sep {
            display: none;
        }
    }
</style>
