<script lang="ts">
    import type { ScaleBarState } from '$lib/map/scale-bar';

    interface Props {
        state: ScaleBarState | null;
        leftPx?: number;
    }

    let { state, leftPx = 24 }: Props = $props();

    const style = $derived(`left: ${leftPx}px;`);
</script>

{#if state}
    <div class="scale-bar" {style} aria-label={`Scale: ${state.label}`}>
        <div class="scale-label">{state.label}</div>
        <div class="scale-rule" style:width={`${state.widthPx}px`}>
            <span class="scale-rule-line"></span>
            <span class="scale-rule-mid"></span>
        </div>
    </div>
{/if}

<style>
    .scale-bar {
        position: absolute;
        bottom: 22px;
        z-index: 900;
        width: max-content;
        color: #fff;
        font-family: var(--font-mono);
        font-size: 0.72rem;
        font-weight: 700;
        line-height: 1;
        letter-spacing: 0.03em;
        pointer-events: none;
        text-shadow:
            0 1px 2px rgb(0 0 0 / 0.95),
            1px 0 1px rgb(0 0 0 / 0.9),
            -1px 0 1px rgb(0 0 0 / 0.9),
            0 -1px 1px rgb(0 0 0 / 0.9);
    }

    .scale-label {
        margin-bottom: 5px;
    }

    .scale-rule {
        position: relative;
        height: 16px;
        min-width: 1px;
        color: #f8fafc;
        filter: drop-shadow(0 1px 1px rgb(0 0 0 / 0.95))
            drop-shadow(0 0 2px rgb(0 0 0 / 0.85));
    }

    .scale-rule::before,
    .scale-rule::after,
    .scale-rule-mid {
        content: '';
        position: absolute;
        bottom: 0;
        width: 2px;
        background: currentColor;
    }

    .scale-rule::before {
        left: 0;
        height: 15px;
    }

    .scale-rule::after {
        right: 0;
        height: 15px;
    }

    .scale-rule-mid {
        left: 50%;
        height: 9px;
    }

    .scale-rule-line {
        position: absolute;
        right: 0;
        bottom: 0;
        left: 0;
        height: 2px;
        background: currentColor;
    }
</style>
