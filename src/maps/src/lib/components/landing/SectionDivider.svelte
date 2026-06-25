<!-- Understated cartographic divider: a hairline that fades into the margins
     with a small centered diamond. -->
<div class="divider" aria-hidden="true"><span></span></div>

<style>
    .divider {
        display: flex;
        align-items: center;
        gap: 18px;
        margin: clamp(2px, 1.4vw, 12px) 0;
    }
    .divider::before,
    .divider::after {
        content: '';
        flex: 1;
        height: 1px;
    }
    .divider::before {
        background: linear-gradient(90deg, transparent, var(--color-line));
    }
    .divider::after {
        background: linear-gradient(90deg, var(--color-line), transparent);
    }
    .divider span {
        flex: none;
        width: 7px;
        height: 7px;
        transform: rotate(45deg);
        border: 1px solid var(--color-accent);
        opacity: 0.8;
    }
</style>
