<svelte:head>
    <title>Adventure Guide - Erenshor</title>
</svelte:head>

<!-- Hero -->
<div class="text-center mb-12">
    <h2 class="text-3xl md:text-4xl font-bold text-white mb-4">Adventure Guide</h2>
    <div class="w-24 h-1 bg-gradient-to-r from-purple-500 to-pink-500 mx-auto rounded-full"></div>
    <p class="text-slate-300 mt-4 text-lg">Every quest. Every item source. Click and go.</p>
    <p class="text-slate-400 mt-2 max-w-2xl mx-auto">
        In-game quest companion for Erenshor. 170+ quests with step-by-step walkthroughs, GPS
        navigation, and floating world markers above every quest-relevant NPC.
    </p>
</div>

<div class="max-w-4xl mx-auto space-y-16">
    <!-- Navigate to anything -->
    <section>
        <h3 class="text-2xl font-bold text-white mb-4">Navigate to anything</h3>
        <img
            src="/adventure-guide-window.png"
            alt="Quest window with walkthroughs and navigation buttons"
            class="rounded-xl border border-slate-700 mb-6 w-full"
            loading="lazy"
        />
        <div class="text-slate-300 space-y-3">
            <p>
                Every quest step has a <span class="font-semibold text-white">[NAV]</span> button. Click
                it and a directional arrow points you to your target — across zone boundaries, chaining
                through multiple connections to get you there.
            </p>
            <p>
                Need an item? Every source is listed — enemy drops, vendors, mining nodes, fishing
                spots, crafting recipes, quest rewards. Click any source and the arrow takes you to
                it. When a source is another quest's reward, that quest's walkthrough unfolds inline
                with its own nav buttons.
            </p>
        </div>
    </section>

    <!-- See what you've been missing -->
    <section>
        <h3 class="text-2xl font-bold text-white mb-4">See what you've been missing</h3>
        <img
            src="/adventure-guide-markers.png"
            alt="World markers above NPCs showing quest state and respawn timers"
            class="rounded-xl border border-slate-700 mb-6 w-full"
            loading="lazy"
        />
        <div class="text-slate-300 space-y-3">
            <p>
                Floating icons appear above NPCs in the game world — quest givers you've walked
                past, turn-in targets waiting for your items, enemies you need to hunt down. Kill a
                quest mob and its marker switches to a skull with a live respawn countdown.
                Night-only spawns show the spawn window and current game time so you know when to
                come back.
            </p>
        </div>
    </section>

    <!-- Know the whole path -->
    <section>
        <h3 class="text-2xl font-bold text-white mb-4">Know the whole path</h3>
        <img
            src="/adventure-guide-nav.png"
            alt="Navigation arrow and ground path guiding to target"
            class="rounded-xl border border-slate-700 mb-6 w-full"
            loading="lazy"
        />
        <div class="text-slate-300 space-y-3">
            <p>
                Each step tells you who to talk to, what to say, where to go, and what items to
                collect. Level estimates on quests and steps show what you're ready for and help you
                tackle things in the right order. Come back after a week and your progress, item
                counts, and active step are right where you left them.
            </p>
        </div>
    </section>

    <!-- Download & Install -->
    <section class="bg-slate-800 rounded-xl p-8 border border-slate-700">
        <h3 class="text-2xl font-bold text-white mb-6">Install</h3>

        <p class="text-slate-300 text-sm mb-6">
            Requires <a
                href="https://thunderstore.io/c/erenshor/p/BepInEx/BepInExPack/"
                class="text-purple-400 hover:text-purple-300 underline">BepInEx 5</a
            >.
        </p>

        <div class="space-y-6">
            <div>
                <h4 class="text-lg font-semibold text-white mb-2">Thunderstore install</h4>
                <p class="text-slate-300 text-sm">
                    Install from the
                    <a
                        href="https://thunderstore.io/c/erenshor/p/WoW_Much/AdventureGuide/"
                        class="text-purple-400 hover:text-purple-300 underline">Thunderstore page</a
                    >
                    with a mod manager.
                </p>
            </div>

            <div>
                <h4 class="text-lg font-semibold text-white mb-2">Manual install</h4>
                <div class="text-slate-300 text-sm space-y-2">
                    <p>
                        Download the mod and copy the
                        <code class="bg-slate-900 px-1.5 py-0.5 rounded text-xs text-slate-200"
                            >AdventureGuide/</code
                        >
                        folder into
                        <code class="bg-slate-900 px-1.5 py-0.5 rounded text-xs text-slate-200"
                            >BepInEx/plugins/</code
                        >.
                    </p>
                    <pre
                        class="bg-slate-900 px-3 py-2 rounded text-xs text-slate-200 overflow-x-auto mt-2"><code
                            >Erenshor/
└── BepInEx/
    └── plugins/
        └── AdventureGuide/
            ├── AdventureGuide.dll
            ├── Newtonsoft.Json.dll
            ├── ImGui.NET.dll
            ├── System.Numerics.Vectors.dll
            └── System.Runtime.CompilerServices.Unsafe.dll</code
                        ></pre>
                </div>
            </div>
        </div>

        <div class="mt-8 pt-6 border-t border-slate-700">
            <h4 class="text-lg font-semibold text-white mb-2">Usage</h4>
            <p class="text-slate-300 text-sm">
                Press <kbd
                    class="bg-slate-900 px-1.5 py-0.5 rounded text-xs text-slate-200 font-mono"
                    >L</kbd
                >
                to open the Adventure Guide in-game.
            </p>
        </div>

        <div class="mt-6 pt-6 border-t border-slate-700">
            <h4 class="text-lg font-semibold text-white mb-2">Configuration</h4>
            <p class="text-slate-300 text-sm">
                Config file:
                <code class="bg-slate-900 px-1.5 py-0.5 rounded text-xs text-slate-200"
                    >BepInEx/config/wow-much.adventure-guide.cfg</code
                >
                (generated on first launch).
            </p>
            <p class="text-slate-400 text-sm mt-1">
                Or edit in-game with
                <a
                    href="https://github.com/BepInEx/BepInEx.ConfigurationManager"
                    class="text-purple-400 hover:text-purple-300 underline">Configuration Manager</a
                > (F1).
            </p>
        </div>
    </section>
</div>
