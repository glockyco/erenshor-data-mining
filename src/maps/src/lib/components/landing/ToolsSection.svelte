<script lang="ts">
    import SectionHead from './SectionHead.svelte';

    const tiles = [
        {
            href: '/adventure-guide',
            img: '/adventure-guide-window.webp',
            alt: 'Adventure Guide quest window',
            title: 'Adventure Guide',
            desc: 'In-game quest companion. 170+ quests with walkthroughs, world markers, and navigation.'
        },
        {
            href: '/mod',
            img: '/world-map-companion.gif',
            alt: 'Live entity tracking on the map',
            title: 'Companion Mods',
            desc: 'Live tracking on the maps. See your character, SimPlayers, NPCs, and enemies move in real time.'
        },
        {
            href: '/spreadsheet',
            img: '/spreadsheet.png',
            alt: 'Reference data spreadsheet',
            title: 'Reference Spreadsheet',
            desc: 'Searchable items, drop chances, characters, classes, spells, skills, ascensions, and more.'
        },
        {
            href: '/zone-maps',
            img: '/maps/Braxonia.jpg',
            alt: 'Per-zone map of Braxonia',
            title: 'Zone Maps',
            tag: 'Legacy',
            desc: 'Per-zone maps with spawn, NPC, and connection markers. Superseded by the world map.'
        }
    ];
</script>

<!-- eslint-disable svelte/no-navigation-without-resolve -->
<section id="tools">
    <SectionHead title="Tools & resources" />

    <a class="featured" href="/map">
        <img
            src="/world-map-preview.webp"
            alt="Interactive world map of Erenshor with spawn and NPC markers"
        />
        <div class="body">
            <div class="coord">EVERY ZONE · ONE MAP</div>
            <h3>Interactive World Map</h3>
            <p>
                Pan the entire world. Every spawn point, friendly NPC, and enemy, filterable by level
                and searchable by name.
            </p>
            <span class="go">Open the map →</span>
        </div>
    </a>

    <div class="tools">
        {#each tiles as t (t.href)}
            <a class="tile" href={t.href}>
                <img class="thumb" src={t.img} alt={t.alt} loading="lazy" />
                <div class="body">
                    <div class="row">
                        <h3>{t.title}</h3>
                        {#if t.tag}<span class="tag">{t.tag}</span>{/if}
                    </div>
                    <p>{t.desc}</p>
                </div>
            </a>
        {/each}
    </div>
</section>

<style>
    section {
        padding: clamp(24px, 3vw, 38px) 0 clamp(30px, 4.2vw, 56px);
    }
    .featured {
        display: grid;
        grid-template-columns: 1.3fr 1fr;
        background: var(--color-surface);
        border: 1px solid var(--color-line);
        border-radius: var(--radius-card);
        overflow: hidden;
        text-decoration: none;
        color: inherit;
        margin-bottom: 18px;
        transition: border-color 0.15s;
    }
    .featured:hover {
        border-color: var(--color-accent);
    }
    .featured img {
        width: 100%;
        height: 100%;
        min-height: 260px;
        object-fit: cover;
        display: block;
    }
    .featured .body {
        padding: clamp(22px, 2.6vw, 38px);
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    .coord {
        font-family: var(--font-mono);
        font-size: 0.72rem;
        letter-spacing: 0.1em;
        color: var(--color-accent);
        margin-bottom: 12px;
    }
    .featured h3 {
        font-family: var(--font-display);
        font-size: clamp(1.45rem, 2.4vw, 1.9rem);
        margin: 0 0 0.4em;
        color: var(--color-ink);
        font-weight: 800;
    }
    .featured p {
        margin: 0 0 1.3em;
        color: var(--color-muted);
        max-width: 44ch;
    }
    .go {
        font-weight: 700;
        color: var(--color-accent);
    }
    .tools {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
        gap: 18px;
    }
    .tile {
        display: flex;
        flex-direction: column;
        background: var(--color-surface);
        border: 1px solid var(--color-line);
        border-radius: var(--radius-card);
        overflow: hidden;
        text-decoration: none;
        color: inherit;
        transition:
            border-color 0.15s,
            background 0.15s;
    }
    .tile:hover {
        border-color: var(--color-accent);
        background: var(--color-surface-2);
    }
    .thumb {
        aspect-ratio: 16 / 9;
        width: 100%;
        object-fit: cover;
        display: block;
        border-bottom: 1px solid var(--color-line);
    }
    .tile .body {
        padding: 16px 16px 18px;
    }
    .row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
        margin-bottom: 0.3em;
    }
    .tile h3 {
        font-family: var(--font-display);
        margin: 0;
        font-size: 1.12rem;
        color: var(--color-ink);
        font-weight: 700;
    }
    .tag {
        font-family: var(--font-mono);
        font-size: 0.6rem;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: var(--color-muted);
        border: 1px solid var(--color-line);
        border-radius: 99px;
        padding: 3px 8px;
    }
    .tile p {
        margin: 0;
        color: var(--color-muted);
        font-size: 0.9rem;
        line-height: 1.5;
    }
    @media (max-width: 880px) {
        .featured {
            grid-template-columns: 1fr;
        }
        .featured img {
            min-height: 190px;
        }
    }
</style>
