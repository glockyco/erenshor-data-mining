<!--
  Switches to another game compendium. The logo stays the link home, so
  switching has a control of its own beside the other icons. The panel is placed
  against the header bar so it stays on the screen at every width. Escape, an
  outside click, or a navigation closes it.
-->
<script lang="ts">
    import { afterNavigate } from '$app/navigation';
    import { COMPENDIUMS, THIS_COMPENDIUM, compendiumIconUrl } from '$lib/compendiums';

    let open = $state(false);
    let root = $state<HTMLElement>();
    let toggle = $state<HTMLButtonElement>();

    afterNavigate(() => {
        open = false;
    });
</script>

<svelte:window
    onpointerdown={(event) => {
        if (open && event.target instanceof Node && !root?.contains(event.target)) open = false;
    }}
    onkeydown={(event) => {
        if (event.key !== 'Escape' || !open) return;
        open = false;
        toggle?.focus();
    }}
/>

<!-- eslint-disable svelte/no-navigation-without-resolve -->
<div class="flex" bind:this={root}>
    <button
        bind:this={toggle}
        type="button"
        aria-label="Switch compendium"
        title="Switch compendium"
        aria-expanded={open}
        aria-controls="compendium-switcher"
        onclick={() => (open = !open)}
        class="grid place-items-center text-muted transition-colors hover:text-accent aria-expanded:text-accent"
    >
        <svg
            viewBox="0 0 24 24"
            class="block h-5 w-5"
            fill="none"
            stroke="currentColor"
            stroke-width="1.8"
            aria-hidden="true"
        >
            <rect x="3" y="3" width="7" height="7" rx="1" />
            <rect x="14" y="3" width="7" height="7" rx="1" />
            <rect x="3" y="14" width="7" height="7" rx="1" />
            <rect x="14" y="14" width="7" height="7" rx="1" />
        </svg>
    </button>
    <div
        id="compendium-switcher"
        hidden={!open}
        class="absolute top-full right-4 z-50 mt-1 w-[min(19rem,calc(100%-2rem))] overflow-hidden rounded-lg border border-line bg-surface shadow-[0_16px_40px_rgb(0_0_0_/_0.45)] min-[480px]:right-7 min-[480px]:w-[min(19rem,calc(100%-3.5rem))]"
    >
        <p
            class="m-0 px-4 pt-3.5 pb-2 font-mono text-[0.7rem] tracking-[0.14em] text-muted uppercase"
        >
            Game Compendiums
        </p>
        <ul class="m-0 grid list-none gap-0.5 px-2 pb-2">
            {#each COMPENDIUMS as compendium (compendium.icon)}
                {@const current = compendium.icon === THIS_COMPENDIUM}
                <li>
                    <a
                        href={current ? '/' : compendium.url}
                        aria-current={current ? 'true' : undefined}
                        class="flex min-h-11 items-center gap-3 rounded-md px-2 font-semibold whitespace-nowrap text-ink no-underline transition-colors hover:bg-bg hover:text-accent aria-[current=true]:bg-bg"
                    >
                        <img
                            src={compendiumIconUrl(compendium)}
                            alt=""
                            width="128"
                            height="128"
                            class="h-7 w-7 flex-none object-contain"
                        />
                        <span>{compendium.name}</span>
                        {#if current}
                            <svg
                                viewBox="0 0 24 24"
                                class="ml-auto h-4 w-4 text-accent"
                                fill="none"
                                stroke="currentColor"
                                stroke-width="2.5"
                                aria-hidden="true"><path d="m5 12 5 5 9-10" /></svg
                            >
                        {/if}
                    </a>
                </li>
            {/each}
        </ul>
        <a
            href="/#about"
            class="block border-t border-line px-4 py-2.5 text-[0.9rem] text-muted no-underline transition-colors hover:text-accent"
        >
            About this Compendium
        </a>
    </div>
</div>
