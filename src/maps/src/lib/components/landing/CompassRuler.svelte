<!-- Decorative cartographic ruler: W · ▲N · E with ticks marching symmetrically
     outward from a centered north marker. -->
<div class="ruler" aria-hidden="true">
    <span class="r0">W</span>
    <span class="north">N</span>
    <span class="r2">E</span>
</div>

<style>
    .ruler {
        position: relative;
        margin-top: clamp(24px, 3.2vw, 40px);
        height: 36px;
    }
    .ruler::before,
    .ruler::after {
        content: '';
        position: absolute;
        bottom: 12px;
        height: 7px;
    }
    .ruler::before {
        left: 0;
        right: calc(50% + 30px);
        background-image: repeating-linear-gradient(to left, var(--color-line) 0 1px, transparent 1px 58px);
    }
    .ruler::after {
        left: calc(50% + 30px);
        right: 0;
        background-image: repeating-linear-gradient(to right, var(--color-line) 0 1px, transparent 1px 58px);
    }
    .ruler span {
        position: absolute;
        bottom: 1px;
        font-family: var(--font-mono);
        font-size: 0.72rem;
        letter-spacing: 0.18em;
        color: var(--color-muted);
    }
    .r0 {
        left: 0;
    }
    .r2 {
        right: 0;
    }
    .north {
        left: 50%;
        transform: translateX(-50%);
        color: var(--color-accent);
        font-weight: 600;
        text-align: center;
    }
    .north::before {
        content: '';
        display: block;
        margin: 0 auto 4px;
        width: 0;
        height: 0;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-bottom: 6px solid var(--color-accent);
    }
</style>
