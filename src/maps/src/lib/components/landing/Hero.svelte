<script lang="ts">
    import CompassRuler from './CompassRuler.svelte';
</script>

<!-- eslint-disable svelte/no-navigation-without-resolve -->
<section class="hero">
    <div class="wrap">
        <span class="kicker">Free · fan-made · updated every patch</span>
        <h1>Chart the world of Erenshor.</h1>
        <div class="hero-row">
            <p class="lede">
                Interactive maps, reference data, and companion mods for the single-player
                <em>simulated</em> MMORPG. Built by the community, refreshed with every game build.
            </p>
            <div class="cta">
                <a class="btn primary" href="/map">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
                        ><path
                            d="M9 20l-5.4-2.7A1 1 0 013 16.4V5.6a1 1 0 011.4-.9L9 7m0 13l6-3m-6 3V7m6 10l4.6 2.3A1 1 0 0021 18.4V7.6a1 1 0 00-.6-.9L15 4m0 13V4m0 0L9 7"
                        /></svg
                    >
                    Open the world map
                </a>
                <a class="btn secondary" href="#tools">Browse all tools</a>
                <a class="textlink" href="#about">New to Erenshor? →</a>
            </div>
        </div>
        <CompassRuler />
    </div>
</section>

<style>
    .hero {
        position: relative;
        overflow: hidden;
        border-bottom: 1px solid var(--color-line);
        padding: clamp(34px, 4.5vw, 56px) 0 0;
    }
    .hero::before {
        content: '';
        position: absolute;
        inset: 0;
        pointer-events: none;
        opacity: 0.55;
        background: repeating-radial-gradient(
            circle at 90% -40%,
            transparent 0 62px,
            color-mix(in srgb, var(--color-accent) 12%, transparent) 62px 63px,
            transparent 63px
        );
    }
    .wrap {
        position: relative;
        max-width: 1140px;
        margin: 0 auto;
        padding: 0 28px;
    }
    .kicker {
        display: inline-flex;
        align-items: center;
        gap: 0.6em;
        font-family: var(--font-mono);
        font-size: 0.76rem;
        letter-spacing: 0.16em;
        text-transform: uppercase;
        color: var(--color-accent);
    }
    .kicker::before {
        content: '';
        width: 26px;
        height: 1px;
        background: var(--color-accent);
    }
    h1 {
        font-family: var(--font-display);
        font-size: clamp(2.3rem, 5.6vw, 4.1rem);
        line-height: 1.02;
        margin: 0.3em 0 0.46em;
        color: var(--color-ink);
        text-wrap: balance;
        font-weight: 800;
        letter-spacing: -0.015em;
    }
    .hero-row {
        display: flex;
        justify-content: space-between;
        align-items: flex-end;
        gap: 22px 48px;
        flex-wrap: wrap;
    }
    .lede {
        color: color-mix(in oklab, var(--color-ink) 82%, var(--color-bg));
        max-width: 50ch;
        font-size: 1.08rem;
        margin: 0;
    }
    .cta {
        display: flex;
        gap: 12px;
        flex-wrap: wrap;
        align-items: center;
    }
    .btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 0.5em;
        text-decoration: none;
        font-weight: 700;
        font-size: 1rem;
        line-height: 1.2;
        padding: 0.8em 1.4em;
        border-radius: var(--radius-card);
        border: 1px solid transparent;
        transition:
            filter 0.15s,
            border-color 0.15s,
            background 0.15s;
    }
    .btn.primary {
        background: var(--color-accent);
        color: var(--color-accent-ink);
        border-color: var(--color-accent);
    }
    .btn.primary:hover {
        filter: brightness(1.06);
    }
    .btn.secondary {
        background: var(--color-surface-2);
        color: var(--color-ink);
        border-color: var(--color-line);
    }
    .btn.secondary:hover {
        border-color: var(--color-accent);
    }
    .btn svg {
        width: 1.05em;
        height: 1.05em;
    }
    .textlink {
        color: var(--color-muted);
        text-decoration: none;
        font-size: 0.92rem;
        padding: 0 0.4em;
    }
    .textlink:hover {
        color: var(--color-accent);
    }
    @media (prefers-reduced-motion: reduce) {
        .btn {
            transition: none;
        }
    }
</style>
