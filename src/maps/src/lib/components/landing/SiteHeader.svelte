<script lang="ts">
    import { brand } from './icons';
    import Icon from './Icon.svelte';
    import CompendiumSwitcher from './CompendiumSwitcher.svelte';

    let open = $state(false);

    const nav = [
        { href: '/map', label: 'World Map' },
        { href: '/zone-maps', label: 'Zone Maps' },
        { href: '/adventure-guide', label: 'Adventure Guide' },
        { href: '/mod', label: 'Mods' },
        { href: '/spreadsheet', label: 'Spreadsheet' }
    ];

    const community = [
        {
            href: 'https://store.steampowered.com/app/2382520/Erenshor/',
            label: 'Erenshor on Steam',
            icon: brand.steam
        },
        { href: 'https://discord.gg/erenshor', label: 'Erenshor Discord', icon: brand.discord }
    ];
</script>

<!-- eslint-disable svelte/no-navigation-without-resolve -->
<header>
    <!-- The bar anchors the compendium switcher's panel. Below 480px it tightens, so the
         brand stays on one line beside the icons and the menu. -->
    <div
        class="relative mx-auto flex max-w-[1140px] items-center justify-between gap-2 px-4 py-[18px] min-[480px]:gap-5 min-[480px]:px-7"
    >
        <a
            href="/"
            class="flex items-center gap-2 font-display text-[1.125rem] font-extrabold tracking-[-0.01em] whitespace-nowrap text-ink no-underline min-[480px]:gap-2.5 min-[480px]:text-[1.3rem]"
        >
            <img src="/logo.png" alt="" width="32" height="32" class="h-8 w-8" />
            <span>Erenshor <span class="text-accent">Maps</span></span>
        </a>

        <div class="flex items-center gap-2.5 min-[480px]:gap-[22px]">
            <nav class="hidden flex-wrap gap-[22px] text-[0.95rem] min-[880px]:flex">
                {#each nav as item (item.href)}
                    <a
                        href={item.href}
                        class="text-muted no-underline transition-colors hover:text-accent"
                    >
                        {item.label}
                    </a>
                {/each}
            </nav>

            <!-- The line has the same space on both sides, and the switcher sits beside Ko-fi. -->
            <div
                class="flex items-center gap-2.5 min-[480px]:gap-[15px] min-[880px]:border-l min-[880px]:border-line min-[880px]:pl-[22px]"
            >
                {#each community as s (s.href)}
                    <a
                        href={s.href}
                        aria-label={s.label}
                        title={s.label}
                        class="grid place-items-center text-muted transition-colors hover:text-accent"
                    >
                        <Icon paths={s.icon} class="block h-5 w-5" />
                    </a>
                {/each}
                <CompendiumSwitcher />
                <a
                    href="https://ko-fi.com/wowmuch"
                    aria-label="Support on Ko-fi"
                    title="Support on Ko-fi"
                    class="grid place-items-center text-muted transition-colors hover:text-accent"
                >
                    <Icon paths={brand.kofi} class="block h-5 w-5" />
                </a>
            </div>

            <button
                type="button"
                onclick={() => (open = !open)}
                aria-label="Menu"
                aria-expanded={open}
                class="grid h-9 w-9 place-items-center text-ink min-[880px]:hidden"
            >
                <svg
                    viewBox="0 0 24 24"
                    class="h-6 w-6"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2"
                    stroke-linecap="round"
                >
                    {#if open}
                        <path d="M6 6l12 12M18 6L6 18" />
                    {:else}
                        <path d="M3 6h18M3 12h18M3 18h18" />
                    {/if}
                </svg>
            </button>
        </div>
    </div>

    {#if open}
        <nav
            class="flex flex-col gap-1 border-t border-line bg-surface px-7 py-3 min-[880px]:hidden"
        >
            {#each nav as item (item.href)}
                <a
                    href={item.href}
                    onclick={() => (open = false)}
                    class="py-2 text-muted no-underline transition-colors hover:text-accent"
                >
                    {item.label}
                </a>
            {/each}
        </nav>
    {/if}
</header>
