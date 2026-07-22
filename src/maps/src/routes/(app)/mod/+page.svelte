<script lang="ts">
    import Seo from '$lib/components/Seo.svelte';
    import { breadcrumbJsonLd } from '$lib/seo/jsonld';

    const mods = [
        {
            name: 'Adventure Guide',
            description:
                'In-game quest companion with GPS navigation. 170+ quests with walkthroughs, item sources, and world markers. Click any step, follow the arrow.',
            vaultUrl: 'https://erenshorvault.app/mod/adventure-guide',
            thunderstoreUrl: 'https://thunderstore.io/c/erenshor/p/WoW_Much/AdventureGuide/'
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

<div class="text-center mb-12">
    <h1 class="text-3xl md:text-4xl font-bold text-white mb-4">Erenshor Mods</h1>
    <div class="w-24 h-1 bg-gradient-to-r from-purple-500 to-pink-500 mx-auto rounded-full"></div>
    <p class="text-slate-400 mt-4 max-w-2xl mx-auto">
        Browse maintained companions and enhancements for your Erenshor adventure.
    </p>
</div>

<section class="max-w-4xl mx-auto mb-12 bg-slate-800 rounded-xl p-6 md:p-8 border border-slate-700">
    <h2 class="text-2xl font-bold text-white mb-3">Recommended setup</h2>
    <p class="text-slate-300 text-sm md:text-base mb-5 max-w-3xl">
        Lunaris uses Erenshor Vault to browse, install, and update mods while the game runs.
    </p>
    <a
        href="https://github.com/MizukiBelhi/Lunaris/releases/latest"
        target="_blank"
        rel="noreferrer"
        class="inline-block px-5 py-2.5 bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 text-white font-semibold rounded-lg shadow-lg hover:shadow-xl transition-all duration-300"
    >
        Get Lunaris
    </a>
</section>

<div class="grid md:grid-cols-2 gap-6 max-w-5xl mx-auto mb-12">
    {#each mods as mod (mod.name)}
        <article class="rounded-xl bg-slate-800 border border-slate-700 overflow-hidden flex flex-col h-full">
            {#if mod.demo}
                <div class="aspect-video bg-slate-700 overflow-hidden">
                    <video
                        autoplay
                        muted
                        loop
                        playsinline
                        class="w-full h-full object-cover"
                        aria-label="Interactive Map Companion live entity tracking demo"
                    >
                        <source src="/world-map-companion.mp4" type="video/mp4" />
                        <img
                            src="/world-map-companion.gif"
                            alt="Interactive Map Companion live entity tracking demo"
                            class="w-full h-full object-cover"
                        />
                    </video>
                </div>
            {/if}

            <div class="p-6 flex flex-col flex-grow">
                <h2 class="text-xl font-bold text-white mb-3">{mod.name}</h2>
                <p class="text-slate-300 text-sm leading-relaxed mb-6">{mod.description}</p>

                <div class="mt-auto space-y-4">
                    <div>
                        <p class="text-xs font-semibold text-slate-400 mb-2">
                            Recommended: Lunaris + Erenshor Vault
                        </p>
                        <a
                            href={mod.vaultUrl}
                            target="_blank"
                            rel="noreferrer"
                            class="block w-full py-2.5 px-4 rounded-lg font-semibold text-center bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 text-white shadow-lg hover:shadow-xl transition-all duration-300"
                        >
                            Erenshor Vault
                        </a>
                    </div>

                    <div>
                        <p class="text-xs font-semibold text-slate-400 mb-2">
                            Alternative: BepInEx + Thunderstore
                        </p>
                        <a
                            href={mod.thunderstoreUrl}
                            target="_blank"
                            rel="noreferrer"
                            class="block w-full py-2.5 px-4 rounded-lg font-semibold text-center border border-slate-600 bg-slate-700/60 text-slate-200 hover:bg-slate-600 transition-all duration-300"
                        >
                            Thunderstore
                        </a>
                    </div>
                </div>
            </div>
        </article>
    {/each}
</div>

<section class="max-w-4xl mx-auto bg-slate-800 rounded-xl p-6 md:p-8 border border-slate-700">
    <h2 class="text-2xl font-bold text-white mb-3">Live mode on /map</h2>
    <p class="text-slate-300 text-sm md:text-base">
        Open the <a href="/map" class="text-purple-400 hover:text-purple-300 underline">/map</a>
        page in your browser while the game is running, then enable Live Mode in the map sidebar to
        see your character, SimPlayers, NPCs, enemies, and pets move in real time.
    </p>
</section>
