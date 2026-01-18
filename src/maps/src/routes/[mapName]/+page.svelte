<script lang="ts">
    import { page } from '$app/stores';
    import { goto } from '$app/navigation';
    import { onDestroy } from 'svelte';
    import { MAPS } from '$lib/maps';
    import { Repository } from '$lib/database.default';
    import { type LatLngExpression, type Map as LeafletMap } from 'leaflet';
    import type { Marker, EnemyMarker, NpcMarker } from '$lib/map-markers';

    // Derived from SvelteKit stores
    const mapName = $derived($page.params.mapName);
    const markerKey = $derived($page.url.searchParams.get('marker'));
    const config = $derived(mapName ? MAPS[mapName] : undefined);

    type PositionData = {
        scene: string;
        x: number;
        y: number;
        z: number;
        fx: number;
        fy: number;
        fz: number;
    };

    type PlayerMarkerTransform = {
        position: LatLngExpression;
        rotation: number;
    };

    // Local state
    let mapContainer = $state<HTMLDivElement | null>(null);
    let mapInstance = $state<LeafletMap | null>(null);
    let stableKeyToMarker = $state<Map<string, L.Marker>>(new Map());
    let playerPosition = $state<PositionData | null>(null);
    let playerMarker = $state<L.Marker | null>(null);
    let webSocket: WebSocket | null = null;
    // Load rotation mode from localStorage, defaulting to 'compass'
    let rotationMode = $state<'compass' | 'coordinates'>(
        (typeof window !== 'undefined' &&
            (localStorage.getItem('mapRotationMode') as 'compass' | 'coordinates')) ||
            'compass'
    );
    let trueNorthBearing = $state(0); // Store the zone's true north bearing

    // Track initialization to prevent re-init on query param changes
    let lastInitializedMapName = $state<string | null>(null);

    // Derived state
    function calculateRotation(fx: number, fy: number, fz: number) {
        const angleInRadians = Math.atan2(fz, fx);
        const angleInDegrees = angleInRadians * (180 / Math.PI);
        let leafletAngle = (360 - angleInDegrees + 90) % 360;
        return (leafletAngle + 360) % 360;
    }

    const playerMarkerTransform = $derived<PlayerMarkerTransform | null>(
        playerPosition == null || !config
            ? null
            : {
                  position: [playerPosition.z - config.originY, playerPosition.x - config.originX],
                  rotation: calculateRotation(
                      playerPosition.fx,
                      playerPosition.fy,
                      playerPosition.fz
                  )
              }
    );

    // Effect 1: Map initialization (only when mapName changes)
    $effect(() => {
        const container = mapContainer;
        const currentMapName = mapName;

        if (!container || !config || !currentMapName) return;

        // Skip re-initialization if same map
        if (lastInitializedMapName === currentMapName) return;

        // Mark as initializing IMMEDIATELY to prevent duplicate runs
        lastInitializedMapName = currentMapName;

        // Clean up previous map instance
        mapInstance?.remove();
        mapInstance = null;
        playerMarker = null;
        stableKeyToMarker = new Map(); // Clear marker map

        // Initialize new map
        import('leaflet').then(async (L) => {
            // Import leaflet-rotate for rotation support
            // @ts-expect-error - leaflet-rotate has no type declarations
            await import('leaflet-rotate');

            // Create map instance
            const worldSizeX = config.baseTilesX * config.tileSize;
            const worldSizeY = config.baseTilesY * config.tileSize;

            // Load and create markers
            const repository = new Repository();
            await repository.init();

            // Get north bearing for this zone
            const northBearing = await repository.getZoneNorthBearing(currentMapName);
            // Convert from Unity rotation to Leaflet bearing
            // Unity Z-axis maps to down on our Leaflet map, so we need to flip
            trueNorthBearing = (180 - northBearing + 360) % 360;

            const map = L.map(container, {
                crs: L.CRS.Simple,
                center: [worldSizeY / 2, worldSizeX / 2],
                zoom: config.zoom,
                minZoom: config.minZoom,
                maxZoom: config.maxZoom,
                maxBounds: [
                    [-256, -256],
                    [worldSizeY + 256, worldSizeX + 256]
                ],
                rotate: true,
                bearing: rotationMode === 'compass' ? (180 - northBearing + 360) % 360 : 0,
                rotateControl: false, // Disable default rotation control
                touchRotate: true, // Keep touch rotation enabled
                shiftKeyRotate: true, // Enable shift+drag rotation
                bearingSnap: 0, // Disable snapping to allow free rotation
                zoomControl: false // Disable default zoom control (we'll add it back in the right order)
            });

            L.tileLayer(config.tileUrl, {
                tileSize: config.tileSize,
                noWrap: true,
                bounds: [
                    [0, 0],
                    [worldSizeY, worldSizeX]
                ],
                // TileLayer needs its own minZoom/maxZoom for negative zoom support
                minZoom: config.minZoom,
                maxZoom: config.maxZoom
            }).addTo(map);

            // Initialize WebSocket for player position
            if (!webSocket) {
                webSocket = new WebSocket('ws://localhost:18584');

                webSocket.onopen = () => {
                    console.log('WebSocket connection established.');
                };

                webSocket.onmessage = (event) => {
                    const message = JSON.parse(event.data);
                    const { scene, x, y, z, fx, fy, fz } = message;
                    playerPosition = { scene, x, y, z, fx, fy, fz };
                };

                webSocket.onerror = () => {
                    console.log('WebSocket connection error. Closing connection.');
                    if (map && playerMarker) {
                        map.removeLayer(playerMarker);
                        playerMarker = null;
                    }
                    webSocket?.close();
                    webSocket = null;
                };

                webSocket.onclose = () => {
                    console.log('WebSocket connection closed.');
                    if (map && playerMarker) {
                        map.removeLayer(playerMarker);
                        playerMarker = null;
                    }
                    webSocket = null;
                };
            }

            const [
                achievementMarkers,
                characterMarkers,
                doorMarkers,
                forgeMarkers,
                itemBagMarkers,
                miningNodeMarkers,
                secretPassageMarkers,
                spawnPointMarkers,
                teleportMarkers,
                treasureLocMarkers,
                waterMarkers,
                wishingWellMarkers,
                zoneLineMarkers
            ] = await Promise.all([
                repository.getAchievementTriggerMarkers(currentMapName),
                repository.getCharacterMarkers(currentMapName),
                repository.getDoorMarkers(currentMapName),
                repository.getForgeMarkers(currentMapName),
                repository.getItemBagMarkers(currentMapName),
                repository.getMiningNodeMarkers(currentMapName),
                repository.getSecretPassageMarkers(currentMapName),
                repository.getSpawnPointMarkers(currentMapName),
                repository.getTeleportMarkers(currentMapName),
                repository.getTreasureLocMarkers(currentMapName),
                repository.getWaterMarkers(currentMapName),
                repository.getWishingWellMarkers(currentMapName),
                repository.getZoneLineMarkers(currentMapName)
            ]);

            // Sort spawn points by rarity
            spawnPointMarkers.sort((a, b) => {
                // Enemies always come before NPCs
                if (a.category === 'enemy' && b.category === 'npc') return -1;
                if (a.category === 'npc' && b.category === 'enemy') return 1;

                // Sort enemies by rarity (unique > rare > common)
                if (a.category === 'enemy' && b.category === 'enemy') {
                    const rankA = (a as EnemyMarker).isUnique
                        ? 2
                        : (a as EnemyMarker).isRare
                          ? 1
                          : 0;
                    const rankB = (b as EnemyMarker).isUnique
                        ? 2
                        : (b as EnemyMarker).isRare
                          ? 1
                          : 0;
                    return rankA - rankB;
                }

                return 0;
            });

            const allMarkers: Marker[] = [
                ...waterMarkers,
                ...zoneLineMarkers,
                ...secretPassageMarkers,
                ...forgeMarkers,
                ...teleportMarkers,
                ...wishingWellMarkers,
                ...doorMarkers,
                ...characterMarkers,
                ...miningNodeMarkers,
                ...treasureLocMarkers,
                ...itemBagMarkers,
                ...achievementMarkers,
                ...spawnPointMarkers
            ];

            const layerGroups: { [key: string]: L.LayerGroup } = {};
            // eslint-disable-next-line svelte/prefer-svelte-reactivity -- pre-existing Leaflet code
            const markerMap = new Map<string, L.Marker>();

            function createIcon(iconClass: string, color: string, radius: number) {
                const iconMarkup = `
					<div style="background-color:${color};border:1px solid white;border-radius:50%;width:${radius * 2}px;height:${radius * 2}px;display:flex;justify-content:center;align-items:center;opacity:0.8;">
						<i class="${iconClass}" style="color:white;font-size:${radius + 2}px;"></i>
					</div>`;
                return L.divIcon({
                    html: iconMarkup,
                    className: 'div-icon',
                    iconSize: [radius * 2, radius * 2],
                    popupAnchor: [0, -radius]
                });
            }

            allMarkers.forEach((marker) => {
                let color = 'white';
                let radius = 8;
                let layer = 'Default';
                let iconClass = 'fa-solid fa-circle';

                switch (marker.category) {
                    case 'achievement-trigger':
                        color = 'hotpink';
                        layer = 'Achievement Triggers';
                        iconClass = 'fa-solid fa-medal';
                        break;
                    case 'npc':
                        color = 'green';
                        layer = 'NPCs';
                        iconClass = 'fa-solid fa-user';
                        if (!(marker as NpcMarker).isEnabled) color = 'gray';
                        break;
                    case 'door':
                        color = 'brown';
                        layer = 'Locked Doors';
                        iconClass = 'fa-solid fa-key';
                        break;
                    case 'forge':
                        color = 'black';
                        layer = 'Forges';
                        iconClass = 'fa-solid fa-fire';
                        break;
                    case 'item-bag':
                        color = 'gold';
                        layer = 'Item Bags';
                        iconClass = 'fa-solid fa-sack-dollar';
                        break;
                    case 'mining-node':
                        color = 'turquoise';
                        layer = 'Mining Nodes';
                        iconClass = 'fa-solid fa-gem';
                        break;
                    case 'secret-passage':
                        color = 'black';
                        layer = 'Secret Passages';
                        iconClass = 'fa-solid fa-question';
                        break;
                    case 'enemy':
                        if ((marker as EnemyMarker).isUnique) {
                            color = 'black';
                            radius = 12;
                            layer = 'Enemies (Unique)';
                        } else if ((marker as EnemyMarker).isRare) {
                            color = 'red';
                            layer = 'Enemies (Rare)';
                        } else {
                            color = 'blue';
                            layer = 'Enemies (Common)';
                        }
                        iconClass = 'fa-solid fa-skull';
                        if (!(marker as EnemyMarker).isEnabled) color = 'gray';
                        break;
                    case 'teleport':
                        color = 'black';
                        layer = 'Teleport Destinations';
                        iconClass = 'fa-solid fa-compass';
                        break;
                    case 'treasure-loc':
                        color = 'orange';
                        radius = 12;
                        layer = 'Lost Treasures';
                        iconClass = 'fa-solid fa-map-location-dot';
                        break;
                    case 'water':
                        color = 'lightblue';
                        layer = 'Fishing (WIP)';
                        iconClass = 'fa-solid fa-fish-fins';
                        break;
                    case 'wishing-well':
                        color = 'black';
                        layer = 'Wishing Well';
                        iconClass = 'fa-solid fa-droplet';
                        break;
                    case 'zone-line':
                        color = marker.isEnabled ? 'purple' : 'gray';
                        radius = 12;
                        layer = 'Zone Connections';
                        iconClass = 'fa-solid fa-dungeon';
                        break;
                }

                const icon = createIcon(iconClass, color, radius);

                const m = L.marker(
                    [marker.position.y - config.originY, marker.position.x - config.originX],
                    {
                        icon
                    }
                );

                if (marker.popup) {
                    m.bindPopup(marker.popup);
                }

                markerMap.set(marker.stableKey, m);

                // Use SvelteKit navigation instead of manual history manipulation
                m.on('popupopen', () => {
                    goto(`?marker=${marker.stableKey}`, {
                        replaceState: true,
                        noScroll: true,
                        keepFocus: true
                    });
                });

                m.on('popupclose', () => {
                    goto('?', {
                        replaceState: true,
                        noScroll: true,
                        keepFocus: true
                    });
                });

                if (!layerGroups[layer]) {
                    layerGroups[layer] = L.layerGroup();
                }
                layerGroups[layer].addLayer(m);
            });

            // Add layer control
            const overlayMaps: { [key: string]: L.LayerGroup } = {};
            for (const [name, group] of Object.entries(layerGroups)) {
                if (group.getLayers().length > 0) {
                    if (name !== 'Fishing (WIP)') {
                        group.addTo(map);
                    }
                    overlayMaps[name] = group;
                }
            }

            L.control.layers(undefined, overlayMaps).addTo(map);

            // Add custom rotation mode control
            const RotationModeControl = L.Control.extend({
                options: {
                    position: 'topleft'
                },
                onAdd: function () {
                    const container = L.DomUtil.create('div', 'leaflet-bar leaflet-control');
                    container.style.backgroundColor = 'white';
                    container.style.padding = '5px 10px';
                    container.style.cursor = 'pointer';
                    container.style.fontWeight = 'bold';
                    container.style.fontSize = '14px';

                    const updateLabel = () => {
                        container.innerHTML =
                            rotationMode === 'compass'
                                ? '🧭 Match Compass'
                                : '📍 Match Coordinates';
                    };

                    updateLabel();

                    // Add tooltip
                    container.title =
                        'Toggle between compass-aligned view and coordinate-aligned view';

                    container.onclick = () => {
                        // Toggle between compass and coordinates
                        if (rotationMode === 'compass') {
                            rotationMode = 'coordinates';
                            map.setBearing(0, { animate: true, duration: 0.5 });
                        } else {
                            rotationMode = 'compass';
                            map.setBearing(trueNorthBearing, { animate: true, duration: 0.5 });
                        }
                        // Save preference to localStorage
                        localStorage.setItem('mapRotationMode', rotationMode);
                        updateLabel();
                    };

                    return container;
                }
            });

            map.addControl(new RotationModeControl());

            // Add zoom control after rotation control so it appears below
            L.control.zoom({ position: 'topleft' }).addTo(map);

            // Add back to overview button (icon only) - below zoom controls
            const BackButtonControl = L.Control.extend({
                options: {
                    position: 'topleft'
                },
                onAdd: function () {
                    const container = L.DomUtil.create('div', 'leaflet-bar leaflet-control');
                    const button = L.DomUtil.create('a', 'leaflet-control-zoom-in', container);
                    button.innerHTML = '<i class="fa-solid fa-house" style="font-size: 14px;"></i>';
                    button.href = '#';
                    button.title = 'Back to map overview';
                    button.setAttribute('role', 'button');
                    button.setAttribute('aria-label', 'Back to map overview');
                    button.style.display = 'flex';
                    button.style.alignItems = 'center';
                    button.style.justifyContent = 'center';

                    L.DomEvent.on(button, 'click', (e) => {
                        L.DomEvent.preventDefault(e);

                        goto('/');
                    });

                    return container;
                }
            });

            map.addControl(new BackButtonControl());

            // Update state
            mapInstance = map;
            stableKeyToMarker = markerMap;
        });
    });

    // Effect 2: Handle marker changes (popup open/close)
    $effect(() => {
        const key = markerKey;
        const map = mapInstance;
        const markers = stableKeyToMarker;

        if (!map || markers.size === 0) return;

        if (key) {
            const marker = markers.get(key);
            if (marker && !marker.isPopupOpen()) {
                marker.openPopup();
                map.panTo(marker.getLatLng());
            }
        } else {
            // Close all popups when marker is cleared
            map.closePopup();
        }
    });

    // Effect 2b: Clear marker when navigating to a different map
    let previousMapName = $state<string | null>(null);
    $effect(() => {
        const key = markerKey;

        // Only clear marker if we're actually changing maps (not initial load)
        if (previousMapName !== null && previousMapName !== mapName && key) {
            goto('?', {
                replaceState: true,
                noScroll: true,
                keepFocus: true
            });
        }

        previousMapName = mapName ?? null;
    });

    // Effect 3: Player marker updates
    $effect(() => {
        const map = mapInstance;
        const position = playerPosition;
        const transform = playerMarkerTransform;

        if (!map) return;

        // Remove player marker if on different scene
        if (playerMarker && position && position.scene !== mapName) {
            map.removeLayer(playerMarker);
            playerMarker = null;
            return;
        }

        // Create player marker if needed
        if (!playerMarker && position && position.scene === mapName && transform) {
            import('leaflet').then((L) => {
                const marker = L.marker(transform.position, {
                    icon: L.divIcon({
                        className: 'player-marker',
                        html: `
							<div class="player-icon" style="background-color:lime;border:1px solid white;border-radius:50%;width:24px;height:24px;display:flex;justify-content:center;align-items:center;transform:rotate(${transform.rotation}deg)">
								<i class="fa-solid fa-up-long" style="color:white;font-size:14px;"></i>
							</div>
						`,
                        iconSize: [24, 24]
                    })
                });
                marker.addTo(map);
                playerMarker = marker;
            });
        }

        // Update player marker position/rotation
        if (playerMarker && transform) {
            playerMarker.setLatLng(transform.position);
            const icon = playerMarker.getElement()?.querySelector('.player-icon') as HTMLElement;
            if (icon) {
                icon.style.transform = `rotate(${transform.rotation}deg)`;
            }
        }
    });

    // Cleanup
    onDestroy(() => {
        mapInstance?.remove();
        webSocket?.close();
    });
</script>

<svelte:head>
    <link
        rel="stylesheet"
        href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css"
    />
    <link
        rel="stylesheet"
        href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.7.2/css/all.min.css"
    />
</svelte:head>

{#if config}
    <div bind:this={mapContainer} style="height:100vh;width:100vw;"></div>
{:else}
    <div
        style="display:flex;justify-content:center;align-items:center;height:100vh;font-size:2em;color:#888;"
    >
        Map not found
    </div>
{/if}
