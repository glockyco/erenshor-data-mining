<script lang="ts">
    import Icon from './Icon.svelte';
    import { line } from './icons';
</script>

<div class="coord-hud" aria-hidden="true">
    <Icon paths={line.crosshair} stroke class="block h-[14px] w-[14px] shrink-0 text-accent" />
    <span class="hud-xy"><b>X</b> 0 · <b>Y</b> 0</span>
</div>

<style>
    .coord-hud {
        position: fixed;
        right: 18px;
        bottom: 18px;
        z-index: 60;
        display: flex;
        align-items: center;
        gap: 9px;
        padding: 8px 12px;
        border: 1px solid var(--color-line);
        border-radius: 10px;
        background: color-mix(in oklab, var(--color-surface) 90%, var(--color-bg));
        box-shadow: 0 8px 26px rgba(0, 0, 0, 0.4);
        font-family: var(--font-mono);
        font-size: 0.74rem;
        letter-spacing: 0.08em;
        color: var(--color-muted);
        pointer-events: none;
        opacity: 0;
        transform: translateY(6px);
        transition:
            opacity 0.25s,
            transform 0.25s;
    }
    .coord-hud:global(.on) {
        opacity: 1;
        transform: none;
    }
    /* :global because the <b> elements are re-created via innerHTML at runtime. */
    .hud-xy :global(b) {
        color: var(--color-accent);
        font-weight: 500;
    }
    @media (pointer: coarse) {
        .coord-hud {
            display: none;
        }
    }
    @media (max-width: 640px) {
        .coord-hud {
            display: none;
        }
    }
    @media (prefers-reduced-motion: reduce) {
        .coord-hud {
            transition: opacity 0.25s;
        }
    }
</style>
