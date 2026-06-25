<script lang="ts">
    import CoordTag from './CoordTag.svelte';

    // Only the fields this section renders; the page load also provides `quests`.
    interface Stats {
        zones: number;
        classes: number;
        items: number;
    }
    let { stats }: { stats: Stats } = $props();

    const WORDS = [
        'zero',
        'one',
        'two',
        'three',
        'four',
        'five',
        'six',
        'seven',
        'eight',
        'nine',
        'ten',
        'eleven',
        'twelve'
    ];
    const floorTo = (n: number, step: number) => Math.floor(n / step) * step;

    const zonesText = $derived(`${floorTo(stats.zones, 10)}+`);
    const classesText = $derived(
        stats.classes >= 0 && stats.classes <= 12 ? WORDS[stats.classes] : String(stats.classes)
    );
    const itemsText = $derived(`over ${floorTo(stats.items, 1000).toLocaleString('en-US')}`);
</script>

<section id="about" class="prose">
    <div>
        <CoordTag />
        <h2>About Erenshor</h2>
        <p>
            <a href="https://erenshor.com/">Erenshor</a> is a single-player <em>simulated</em> MMORPG,
            a love letter to the late-90s and early-2000s online RPGs. Its signature SimPlayers level
            up, trade, join guilds, and raid alongside you, driven by state machines rather than AI, so
            the world feels alive while you play completely offline.
        </p>
        <p>
            Developed by Burgee Media, it spans {zonesText} zones, {classesText} classes, {itemsText}
            items, and hundreds of quests and NPCs to discover.
        </p>
    </div>
    <div>
        <CoordTag />
        <h2>About Erenshor Maps</h2>
        <p>
            Erenshor Maps is a fan-made companion suite. The interactive maps plot every creature
            spawn, friendly NPC, and resource node. The companion mods add live tracking and an
            in-game quest guide, and the reference spreadsheet exposes the underlying game data.
        </p>
        <p>
            Everything is pulled straight from the game files and refreshed with each new build, so the
            data you plan around matches the game you're playing.
        </p>
    </div>
</section>

<style>
    #about {
        position: relative;
        overflow: hidden;
        padding: clamp(30px, 4.2vw, 56px) 0;
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 44px;
    }
    #about::before {
        content: '';
        position: absolute;
        top: 50%;
        left: -140px;
        width: 560px;
        height: 560px;
        transform: translateY(-50%);
        pointer-events: none;
        opacity: 0.85;
        background:
            radial-gradient(circle at center, transparent 26%, var(--color-bg) 72%),
            repeating-radial-gradient(
                circle at center,
                transparent 0 40px,
                color-mix(in srgb, var(--color-accent) 12%, transparent) 40px 41px,
                transparent 41px
            );
    }
    #about > div {
        position: relative;
    }
    h2 {
        font-family: var(--font-display);
        font-size: 1.45rem;
        margin: 0 0 0.5em;
        color: var(--color-ink);
        font-weight: 800;
    }
    p {
        color: color-mix(in oklab, var(--color-ink) 84%, var(--color-bg));
        max-width: 62ch;
        margin: 0 0 0.9em;
    }
    a {
        color: var(--color-accent);
        text-decoration: none;
        border-bottom: 1px solid color-mix(in srgb, var(--color-accent) 45%, transparent);
    }
    @media (max-width: 880px) {
        #about {
            grid-template-columns: 1fr;
            gap: 28px;
        }
    }
</style>
