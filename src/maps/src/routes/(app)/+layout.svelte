<script lang="ts">
    import '../../app.css';
    import { page } from '$app/state';
</script>

<svelte:head>
    <title>Erenshor Interactive Maps</title>
</svelte:head>

<div class="bg-slate-950 py-8 px-4 min-h-screen">
    <div class="max-w-7xl mx-auto">
        <!-- Tab Navigation -->
        <div class="flex justify-center mb-8">
            <!-- eslint-disable svelte/no-navigation-without-resolve -->
            <div class="bg-slate-800 rounded-xl p-2 border border-slate-700 flex flex-wrap gap-1">
                <a
                    href="/"
                    class="flex-1 basis-auto min-w-fit px-4 py-2 rounded-lg font-semibold transition-all duration-300 text-center whitespace-nowrap {page
                        .url.pathname === '/'
                        ? 'bg-gradient-to-r from-purple-500 to-pink-500 text-white shadow-lg'
                        : 'text-slate-300 hover:text-white hover:bg-slate-700'}"
                >
                    World Map
                </a>
                <a
                    href="/zone-maps"
                    class="flex-1 basis-auto min-w-fit px-4 py-2 rounded-lg font-semibold transition-all duration-300 text-center whitespace-nowrap {page
                        .url.pathname === '/zone-maps'
                        ? 'bg-gradient-to-r from-purple-500 to-pink-500 text-white shadow-lg'
                        : 'text-slate-300 hover:text-white hover:bg-slate-700'}"
                >
                    Zone Maps
                </a>
                <a
                    href="/mod"
                    class="flex-1 basis-auto min-w-fit px-4 py-2 rounded-lg font-semibold transition-all duration-300 text-center whitespace-nowrap {page
                        .url.pathname === '/mod'
                        ? 'bg-gradient-to-r from-purple-500 to-pink-500 text-white shadow-lg'
                        : 'text-slate-300 hover:text-white hover:bg-slate-700'}"
                >
                    Companion Mods
                </a>
                <a
                    href="/spreadsheet"
                    class="flex-1 basis-auto min-w-fit px-4 py-2 rounded-lg font-semibold transition-all duration-300 text-center whitespace-nowrap {page
                        .url.pathname === '/spreadsheet'
                        ? 'bg-gradient-to-r from-purple-500 to-pink-500 text-white shadow-lg'
                        : 'text-slate-300 hover:text-white hover:bg-slate-700'}"
                >
                    Spreadsheet
                </a>
            </div>
            <!-- eslint-enable svelte/no-navigation-without-resolve -->
        </div>

        <!-- Page Content -->
        <slot />
    </div>
</div>
