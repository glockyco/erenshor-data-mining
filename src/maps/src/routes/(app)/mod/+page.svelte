<script lang="ts">
    import Seo from '$lib/components/Seo.svelte';
    import { breadcrumbJsonLd } from '$lib/seo/jsonld';

    interface ModEntry {
        name: string;
        description: string;
        vaultUrl: string;
        thunderstoreUrl: string;
        image?: {
            src: string;
            alt: string;
            width: number;
            height: number;
        };
        demo?: boolean;
    }

    const mods: ModEntry[] = [
        {
            name: 'Adventure Guide',
            description:
                'In-game quest companion with GPS navigation. 170+ quests with walkthroughs, item sources, and world markers. Click any step, follow the arrow.',
            vaultUrl: 'https://erenshorvault.app/mod/adventure-guide',
            thunderstoreUrl: 'https://thunderstore.io/c/erenshor/p/WoW_Much/AdventureGuide/',
            image: {
                src: '/adventure-guide-window.webp',
                alt: 'Adventure Guide quest window showing walkthroughs, item sources, and navigation controls',
                width: 1868,
                height: 1404
            }
        },
        {
            name: 'Interactive Map Companion',
            description:
                'Companion mod for the interactive world map. Live tracking of all characters — player, SimPlayers, NPCs, enemies, and pets — right in your browser.',
            vaultUrl: 'https://erenshorvault.app/mod/interactive-map-companion',
            thunderstoreUrl:
                'https://thunderstore.io/c/erenshor/p/WoW_Much/InteractiveMapCompanion/',
            demo: true
        },
        {
            name: 'Sprint',
            description:
                'Hold Shift to run faster. Configurable sprint key with adjustable speed from subtle to ludicrous. No stamina, no cooldowns, just speed.',
            vaultUrl: 'https://erenshorvault.app/mod/sprint',
            thunderstoreUrl: 'https://thunderstore.io/c/erenshor/p/WoW_Much/Sprint/'
        },
        {
            name: 'Justice for F7',
            description:
                'Extends F7 Hide UI to also hide nameplates, damage numbers, target rings, XP orbs, cast bars, and loot prompts.',
            vaultUrl: 'https://erenshorvault.app/mod/justice-for-f7',
            thunderstoreUrl: 'https://thunderstore.io/c/erenshor/p/WoW_Much/JusticeForF7/'
        }
    ];
</script>

<Seo
    path="/mod"
    title="Erenshor Mods – Lunaris, Erenshor Vault, and Thunderstore"
    description="Install Adventure Guide, Interactive Map Companion, Sprint, and Justice for F7 through Lunaris and Erenshor Vault, or use Thunderstore with BepInEx."
    jsonLd={breadcrumbJsonLd([
        { name: 'Home', path: '/' },
        { name: 'Mods', path: '/mod' }
    ])}
/>

<div class="mx-auto max-w-5xl space-y-10 md:space-y-12">
    <header class="max-w-3xl">
        <h1 class="text-3xl font-bold text-white text-balance md:text-4xl">Erenshor Mods</h1>
        <div class="mt-4 h-1 w-20 rounded-full bg-gradient-to-r from-purple-500 to-pink-500"></div>
        <p class="mt-4 text-base leading-relaxed text-slate-300 md:text-lg">
            Four maintained mods. Install them in-game with Lunaris and Erenshor Vault, or use
            Thunderstore with BepInEx.
        </p>
    </header>

    <section
        class="rounded-xl border border-purple-500/40 bg-gradient-to-br from-slate-800 to-purple-950/40 p-6 md:p-8"
        aria-labelledby="recommended-setup"
    >
        <div class="grid gap-8 md:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)] md:items-center">
            <div class="min-w-0">
                <p class="mb-2 font-semibold text-purple-300">Recommended for most players</p>
                <h2 id="recommended-setup" class="text-2xl font-bold text-white text-balance">
                    Install mods with Lunaris
                </h2>
                <p class="mt-3 max-w-xl text-sm leading-relaxed text-slate-300 md:text-base">
                    Lunaris adds a mod browser to Erenshor's main menu. It uses Erenshor Vault to
                    install and update mods while the game is running.
                </p>
                <a
                    href="https://github.com/MizukiBelhi/Lunaris/releases/latest"
                    target="_blank"
                    rel="noreferrer"
                    class="mt-6 inline-flex min-h-11 w-full items-center justify-center rounded-lg bg-gradient-to-r from-purple-500 to-pink-500 px-5 py-2.5 font-semibold text-white transition-colors duration-200 hover:from-purple-600 hover:to-pink-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-purple-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-800 sm:w-auto"
                >
                    <svg class="mr-2 h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                        <path
                            stroke-linecap="round"
                            stroke-linejoin="round"
                            stroke-width="2"
                            d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
                        ></path>
                    </svg>
                    Download Lunaris
                </a>
                <p class="mt-3 text-sm text-slate-400">
                    Already use BepInEx? Choose the Thunderstore link on any mod below.
                </p>
            </div>

            <ol class="space-y-5 border-t border-slate-700 pt-6 md:border-l md:border-t-0 md:pl-8 md:pt-0">
                <li class="flex gap-4">
                    <span
                        class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-purple-500/20 text-sm font-bold text-purple-300"
                        >1</span
                    >
                    <p class="text-sm leading-relaxed text-slate-300">
                        Download the latest Lunaris release and extract
                        <code class="rounded bg-slate-900 px-1.5 py-0.5 text-xs text-slate-200">winhttp.dll</code>
                        next to <code class="rounded bg-slate-900 px-1.5 py-0.5 text-xs text-slate-200">Erenshor.exe</code>.
                    </p>
                </li>
                <li class="flex gap-4">
                    <span
                        class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-purple-500/20 text-sm font-bold text-purple-300"
                        >2</span
                    >
                    <p class="text-sm leading-relaxed text-slate-300">
                        Launch Erenshor and open Lunaris from the icon on the main menu.
                    </p>
                </li>
                <li class="flex gap-4">
                    <span
                        class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-purple-500/20 text-sm font-bold text-purple-300"
                        >3</span
                    >
                    <p class="text-sm leading-relaxed text-slate-300">
                        Find a mod in Erenshor Vault, then install it from inside Lunaris.
                    </p>
                </li>
            </ol>
        </div>
    </section>

    <section aria-labelledby="maintained-mods">
        <div class="mb-5">
            <h2 id="maintained-mods" class="text-2xl font-bold text-white">Maintained mods</h2>
            <p class="mt-2 text-sm text-slate-400">
                Lunaris uses Erenshor Vault. BepInEx users can install the same mods from Thunderstore.
            </p>
        </div>

        <div class="grid gap-6 md:grid-cols-2">
            {#each mods as mod (mod.name)}
                <article class="flex h-full min-w-0 flex-col overflow-hidden rounded-xl border border-slate-700 bg-slate-800">
                    {#if mod.image}
                        <div class="aspect-video overflow-hidden border-b border-slate-700 bg-slate-950">
                            <img
                                src={mod.image.src}
                                alt={mod.image.alt}
                                width={mod.image.width}
                                height={mod.image.height}
                                loading="lazy"
                                class="h-full w-full object-contain"
                            />
                        </div>
                    {:else if mod.demo}
                        <div class="aspect-video overflow-hidden border-b border-slate-700 bg-slate-900">
                            <video
                                autoplay
                                muted
                                loop
                                playsinline
                                preload="metadata"
                                poster="/world-map-companion.gif"
                                class="h-full w-full object-cover"
                                aria-label="Interactive Map Companion live entity tracking demo"
                            >
                                <source src="/world-map-companion.mp4" type="video/mp4" />
                                <img
                                    src="/world-map-companion.gif"
                                    alt="Interactive Map Companion live entity tracking demo"
                                    class="h-full w-full object-cover"
                                />
                            </video>
                        </div>
                    {/if}

                    <div class="flex flex-grow flex-col p-6">
                        <h3 class="text-xl font-bold text-white text-balance">{mod.name}</h3>
                        <p class="mt-3 text-sm leading-relaxed text-slate-300">{mod.description}</p>

                        <div class="mt-auto grid gap-4 border-t border-slate-700 pt-5 sm:grid-cols-2 md:grid-cols-1 lg:grid-cols-2">
                            <div class="min-w-0">
                                <p class="mb-2 text-sm font-medium leading-5 text-slate-400">
                                    Recommended: Lunaris + Erenshor Vault
                                </p>
                                <a
                                    href={mod.vaultUrl}
                                    target="_blank"
                                    rel="noreferrer"
                                    class="inline-flex min-h-11 w-full items-center justify-center rounded-lg bg-purple-600 px-4 py-2.5 font-semibold text-white transition-colors duration-200 hover:bg-purple-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-purple-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-800"
                                >
                                    Erenshor Vault
                                    <span class="ml-1.5" aria-hidden="true">↗</span>
                                </a>
                            </div>

                            <div class="min-w-0">
                                <p class="mb-2 text-sm font-medium leading-5 text-slate-400">
                                    Alternative: BepInEx + Thunderstore
                                </p>
                                <a
                                    href={mod.thunderstoreUrl}
                                    target="_blank"
                                    rel="noreferrer"
                                    class="inline-flex min-h-11 w-full items-center justify-center rounded-lg border border-slate-600 bg-slate-700/50 px-4 py-2.5 font-semibold text-slate-200 transition-colors duration-200 hover:border-slate-500 hover:bg-slate-700 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-purple-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-800"
                                >
                                    Thunderstore
                                    <span class="ml-1.5" aria-hidden="true">↗</span>
                                </a>
                            </div>
                        </div>
                    </div>
                </article>
            {/each}
        </div>
    </section>

    <section class="border-t border-slate-700 pt-8" aria-labelledby="live-mode">
        <div class="max-w-3xl">
            <h2 id="live-mode" class="text-2xl font-bold text-white">Use Interactive Map Companion</h2>
            <p class="mt-3 text-sm leading-relaxed text-slate-300 md:text-base">
                With Erenshor running, open the
                <a
                    href="/map"
                    class="font-medium text-purple-400 underline underline-offset-4 transition-colors hover:text-purple-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-purple-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
                    >interactive world map</a
                > and enable Live Mode in the sidebar. Your character, SimPlayers, NPCs, enemies,
                and pets will update in real time.
            </p>
        </div>
    </section>
</div>
