<script lang="ts">
    import '../../app.css';
    import { page } from '$app/state';
</script>

<svelte:head>
    <title>Erenshor Interactive Maps</title>
</svelte:head>

<div class="bg-slate-950 py-16 px-4">
    <div class="max-w-7xl mx-auto">
        <!-- Tab Navigation -->
        <div class="flex justify-center mb-12">
            <!-- eslint-disable svelte/no-navigation-without-resolve -->
            <div class="bg-slate-800 rounded-xl p-2 border border-slate-700">
                <a
                    href="/"
                    class="px-8 py-3 rounded-lg font-semibold transition-all duration-300 inline-block {page
                        .url.pathname === '/'
                        ? 'bg-gradient-to-r from-purple-500 to-pink-500 text-white shadow-lg'
                        : 'text-slate-300 hover:text-white hover:bg-slate-700'}"
                >
                    Interactive Zone Maps
                </a>
                <a
                    href="/mod"
                    class="px-8 py-3 rounded-lg font-semibold transition-all duration-300 inline-block {page
                        .url.pathname === '/mod'
                        ? 'bg-gradient-to-r from-purple-500 to-pink-500 text-white shadow-lg'
                        : 'text-slate-300 hover:text-white hover:bg-slate-700'}"
                >
                    Companion Mod
                </a>
                <a
                    href="/spreadsheet"
                    class="px-8 py-3 rounded-lg font-semibold transition-all duration-300 inline-block {page
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
