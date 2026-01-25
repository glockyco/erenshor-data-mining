<script lang="ts">
    import type { PageData } from './$types';

    export let data: PageData;
</script>

<!-- Companion Mods Section -->
<div class="text-center mb-12">
    <h2 class="text-3xl md:text-4xl font-bold text-white mb-4">Companion Mods</h2>
    <div class="w-24 h-1 bg-gradient-to-r from-purple-500 to-pink-500 mx-auto rounded-full"></div>
    <p class="text-slate-400 mt-4">
        Enhance your Erenshor experience with real-time tracking on the interactive maps.
    </p>
</div>

<!-- Mods Grid -->
<div class="grid md:grid-cols-2 gap-6 max-w-5xl mx-auto mb-12">
    {#each data.modsMetadata.mods as mod (mod.id)}
        <div
            class={`rounded-xl overflow-hidden border transition-all duration-300 flex flex-col h-full ${
                mod.status === 'current'
                    ? 'bg-slate-800 border-purple-500 shadow-lg shadow-purple-500/20'
                    : 'bg-slate-900 border-slate-700'
            }`}
        >
            <!-- Demo Video/GIF -->
            {#if mod.gifUrl}
                <div class="aspect-video bg-slate-700 overflow-hidden">
                    {#if mod.gifUrl.endsWith('.mp4')}
                        <video
                            autoplay
                            muted
                            loop
                            class={`w-full h-full object-cover ${
                                mod.status === 'legacy'
                                    ? 'opacity-60 grayscale-[40%] brightness-90'
                                    : ''
                            }`}
                        >
                            <source src={mod.gifUrl} type="video/mp4" />
                            <!-- Fallback for older browsers -->
                            <img
                                src={mod.gifUrl.replace('.mp4', '.gif')}
                                alt={`${mod.displayName} demo`}
                                class="w-full h-full object-cover"
                            />
                        </video>
                    {:else}
                        <img
                            src={mod.gifUrl}
                            alt={`${mod.displayName} demo`}
                            class={`w-full h-full object-cover ${
                                mod.status === 'legacy'
                                    ? 'opacity-60 grayscale-[40%] brightness-90'
                                    : ''
                            }`}
                            loading="lazy"
                        />
                    {/if}
                </div>
            {:else}
                <div class="aspect-video bg-slate-700 flex items-center justify-center">
                    <span class="text-slate-500 text-sm">No preview available</span>
                </div>
            {/if}

            <!-- Card Content -->
            <div class="p-6 flex flex-col flex-grow">
                <!-- Header with Title and Status Badge -->
                <div class="flex items-center justify-between mb-3">
                    <h3 class="text-xl font-bold text-white">{mod.displayName}</h3>
                    <span
                        class={`text-xs font-semibold px-2 py-1 rounded ${
                            mod.status === 'current'
                                ? 'bg-green-500/20 text-green-300'
                                : 'bg-yellow-500/20 text-yellow-300'
                        }`}
                    >
                        {mod.status === 'current' ? 'CURRENT' : 'LEGACY'}
                    </span>
                </div>

                <!-- Version Badge -->
                <div class="text-sm text-slate-400 mb-3">
                    v<span class="font-mono">{mod.version}</span>
                </div>

                <!-- Description -->
                <p class="text-slate-300 text-sm mb-4">{mod.description}</p>

                <!-- Features List -->
                <div class="mb-6 flex-grow">
                    <h4 class="text-xs font-semibold text-slate-300 uppercase tracking-wide mb-2">
                        Features
                    </h4>
                    <ul class="space-y-1">
                        {#each mod.features as feature (feature)}
                            <li class="text-sm text-slate-400 flex items-start">
                                <svg
                                    class="w-4 h-4 mr-2 mt-0.5 flex-shrink-0 text-green-400"
                                    fill="none"
                                    stroke="currentColor"
                                    viewBox="0 0 24 24"
                                >
                                    <path
                                        stroke-linecap="round"
                                        stroke-linejoin="round"
                                        stroke-width="2"
                                        d="M5 13l4 4L19 7"
                                    ></path>
                                </svg>
                                {feature}
                            </li>
                        {/each}
                    </ul>
                </div>

                <!-- Download Button -->
                <a
                    href={mod.downloadUrl}
                    class={`block w-full py-2 px-4 rounded-lg font-semibold text-center transition-all duration-300 mt-auto ${
                        mod.status === 'current'
                            ? 'bg-gradient-to-r from-purple-500 to-pink-500 text-white hover:from-purple-600 hover:to-pink-600 shadow-lg hover:shadow-xl'
                            : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                    }`}
                    download
                >
                    <svg
                        class="w-4 h-4 inline mr-2"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                    >
                        <path
                            stroke-linecap="round"
                            stroke-linejoin="round"
                            stroke-width="2"
                            d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
                        ></path>
                    </svg>
                    Download
                </a>
            </div>
        </div>
    {/each}
</div>

<!-- Installation Guide Section -->
<div class="bg-slate-800 rounded-xl p-8 border border-slate-700 max-w-4xl mx-auto mb-12">
    <h3 class="text-2xl font-bold text-white mb-6">Installation Guide</h3>

    <div class="space-y-6">
        <!-- Step 1: BepInEx -->
        <div>
            <h4 class="text-lg font-semibold text-white mb-2 flex items-center">
                <span
                    class="flex items-center justify-center w-6 h-6 rounded-full bg-purple-500/20 text-purple-400 text-sm font-bold mr-3"
                >
                    1
                </span>
                Install BepInEx
            </h4>
            <div class="ml-9 text-slate-300 space-y-2 text-sm">
                <p>
                    Download and install <a
                        href="https://github.com/BepInEx/BepInEx/releases"
                        target="_blank"
                        rel="noopener noreferrer"
                        class="text-purple-400 hover:text-purple-300 underline"
                    >
                        BepInEx 5.4
                    </a>
                    to your Erenshor game directory. BepInEx is a mod loader for Unity games.
                </p>
                <p class="text-slate-400">
                    Extract the BepInEx archive to your Erenshor game folder. Your directory
                    structure should look like:
                </p>
                <pre
                    class="bg-slate-900 px-3 py-2 rounded text-xs text-slate-200 overflow-x-auto mt-2"><code
                        >Erenshor/
├── BepInEx/
│   ├── config/
│   ├── plugins/
│   ├── patchers/
│   ├── core/
│   └── ...
├── doorstop_version
├── changelog.txt
├── doorstop_config.ini
├── winhttp.dll
├── Erenshor.exe
└── ...</code
                    ></pre>
            </div>
        </div>

        <!-- Step 2: Download Mod -->
        <div>
            <h4 class="text-lg font-semibold text-white mb-2 flex items-center">
                <span
                    class="flex items-center justify-center w-6 h-6 rounded-full bg-purple-500/20 text-purple-400 text-sm font-bold mr-3"
                >
                    2
                </span>
                Download & Install Mod
            </h4>
            <div class="ml-9 text-slate-300 space-y-2 text-sm">
                <p>Click the mod's Download button above to get the mod DLL file.</p>
                <p>Extract the DLL to your BepInEx plugins folder:</p>
                <div class="space-y-2">
                    <div>
                        <p class="text-slate-400 text-xs mb-1">For World Map:</p>
                        <p
                            class="font-mono bg-slate-900 px-3 py-2 rounded text-xs text-slate-200 overflow-x-auto"
                        >
                            Erenshor/BepInEx/plugins/InteractiveMapCompanion.dll
                        </p>
                    </div>
                    <div>
                        <p class="text-slate-400 text-xs mb-1">For Zone Maps:</p>
                        <p
                            class="font-mono bg-slate-900 px-3 py-2 rounded text-xs text-slate-200 overflow-x-auto"
                        >
                            Erenshor/BepInEx/plugins/InteractiveMapsCompanion.dll
                        </p>
                    </div>
                </div>
            </div>
        </div>

        <!-- Step 3: Configure BepInEx -->
        <div>
            <h4 class="text-lg font-semibold text-white mb-2 flex items-center">
                <span
                    class="flex items-center justify-center w-6 h-6 rounded-full bg-purple-500/20 text-purple-400 text-sm font-bold mr-3"
                >
                    3
                </span>
                Configure BepInEx
            </h4>
            <div class="ml-9 text-slate-300 space-y-3 text-sm">
                <p>
                    A Unity security update requires a configuration change. Open your BepInEx
                    configuration file:
                </p>
                <p
                    class="font-mono bg-slate-900 px-3 py-2 rounded text-xs text-slate-200 overflow-x-auto"
                >
                    Erenshor/BepInEx/config/BepInEx.cfg
                </p>

                <p class="text-slate-400">
                    Find the <span class="font-semibold text-white">[Chainloader]</span> section and change:
                </p>
                <pre
                    class="bg-slate-900 px-3 py-2 rounded text-xs text-slate-200 overflow-x-auto"><code
                        class="text-red-400">HideManagerGameObject = false</code
                    ></pre>
                <p class="text-slate-400">To:</p>
                <pre
                    class="bg-slate-900 px-3 py-2 rounded text-xs text-slate-200 overflow-x-auto"><code
                        class="text-green-400">HideManagerGameObject = true</code
                    ></pre>

                <p class="text-slate-400 mt-4">
                    Then find the <span class="font-semibold text-white">[Logging.Console]</span> section
                    and change:
                </p>
                <pre
                    class="bg-slate-900 px-3 py-2 rounded text-xs text-slate-200 overflow-x-auto"><code
                        class="text-red-400">Enabled = false</code
                    ></pre>
                <p class="text-slate-400">To:</p>
                <pre
                    class="bg-slate-900 px-3 py-2 rounded text-xs text-slate-200 overflow-x-auto"><code
                        class="text-green-400">Enabled = true</code
                    ></pre>
            </div>
        </div>

        <!-- Step 4: Launch Game -->
        <div>
            <h4 class="text-lg font-semibold text-white mb-2 flex items-center">
                <span
                    class="flex items-center justify-center w-6 h-6 rounded-full bg-purple-500/20 text-purple-400 text-sm font-bold mr-3"
                >
                    4
                </span>
                Launch the Game
            </h4>
            <div class="ml-9 text-slate-300 space-y-2 text-sm">
                <p>Start Erenshor. The mod will load automatically with BepInEx on game launch.</p>
                <p class="text-slate-400">
                    You should see the mod initializing in the BepInEx console.
                </p>
            </div>
        </div>

        <!-- Step 4: Enable Live Mode -->
        <div>
            <h4 class="text-lg font-semibold text-white mb-2 flex items-center">
                <span
                    class="flex items-center justify-center w-6 h-6 rounded-full bg-purple-500/20 text-purple-400 text-sm font-bold mr-3"
                >
                    5a
                </span>
                Use on the World Map
            </h4>
            <div class="ml-9 text-slate-300 space-y-2 text-sm">
                <p>
                    Open the <a href="/map" class="text-purple-400 hover:text-purple-300 underline">
                        world map
                    </a>
                    in your browser while the game is running.<br />
                    Toggle "Enable Live Mode" in the sidebar.<br />
                    The positions of your character, enemies, NPCs, and pets should appear on the map
                    in real-time.
                </p>
            </div>
        </div>

        <!-- Step 5b: Use on Zone Maps -->
        <div>
            <h4 class="text-lg font-semibold text-white mb-2 flex items-center">
                <span
                    class="flex items-center justify-center w-6 h-6 rounded-full bg-purple-500/20 text-purple-400 text-sm font-bold mr-3"
                >
                    5b
                </span>
                Use on the Zone Maps
            </h4>
            <div class="ml-9 text-slate-300 space-y-2 text-sm">
                <p>
                    Open the correct <a
                        href="/zone-maps"
                        class="text-purple-400 hover:text-purple-300 underline"
                    >
                        zone map
                    </a>
                    (e.g.,
                    <a href="/Stowaway" class="text-purple-400 hover:text-purple-300 underline">
                        /Stowaway</a
                    >) in the browser while the game is running.<br />
                    The position of your character should appear on the map in real-time.
                </p>
            </div>
        </div>
    </div>

    <!-- Troubleshooting -->
    <div class="mt-8 pt-6 border-t border-slate-700">
        <h4 class="text-lg font-semibold text-white mb-3">Troubleshooting</h4>
        <div class="space-y-3 text-sm text-slate-300">
            <div>
                <p class="font-semibold text-white mb-1">Mod not showing up</p>
                <p class="text-slate-400">
                    Check the BepInEx console (should pop up when the game launches). Look for any
                    error messages related to the mod.
                </p>
            </div>
            <div>
                <p class="font-semibold text-white mb-1">Position not updating on the map</p>
                <p class="text-slate-400">
                    Make sure you have enabled <span class="font-semibold text-white"
                        >Live Mode</span
                    > in the map sidebar.
                </p>
            </div>
            <div>
                <p class="font-semibold text-white mb-1">Need more help?</p>
                <p class="text-slate-400">
                    See the <a
                        href="https://steamcommunity.com/sharedfiles/filedetails/?id=3485536525"
                        target="_blank"
                        rel="noopener noreferrer"
                        class="text-purple-400 hover:text-purple-300 underline"
                    >
                        Erenshor Modding guide on Steam
                    </a>
                    for comprehensive setup instructions and additional troubleshooting.
                </p>
            </div>
        </div>
    </div>
</div>
