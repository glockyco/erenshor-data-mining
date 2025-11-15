<script lang="ts">
	import { onDestroy } from 'svelte';
	import { type MapConfig, MAPS } from '$lib/maps';
	import { Repository } from '$lib/database.default';
	import { type LatLngExpression, type Map as LeafletMap } from 'leaflet';
	import type { Marker, SpawnPointMarker } from '$lib/map-markers';

	const { data }: { data: { mapName: string } } = $props();
	const config: MapConfig = $derived(MAPS[data.mapName]);

	type PositionData = {
		scene: string;
		x: number;
		y: number;
		z: number;
		fx: number;
		fy: number;
		fz: number;
	}

	type PlayerMarkerTransform = {
		position: LatLngExpression,
		rotation: number;
	}

	let mapContainer = $state<HTMLDivElement | null>(null);
	let mapInstance = $state<LeafletMap | null>(null);
	let playerPosition = $state<PositionData | null>(null);
	let playerMarker = $state<L.Marker | null>(null);
	let webSocket: WebSocket | null = null;
	let lastMapName = $state<string | null>(null);

	function calculateRotation(fx: number, fy: number, fz: number) {
		const angleInRadians = Math.atan2(fz, fx);
		const angleInDegrees = angleInRadians * (180 / Math.PI);
		let leafletAngle = (360 - angleInDegrees + 90) % 360;
		return (leafletAngle + 360) % 360;
	}

	let playerMarkerTransform: PlayerMarkerTransform | null = $derived(
		playerPosition == null ? null : {
			position: [playerPosition.z - config.originY, playerPosition.x - config.originX],
			rotation: calculateRotation(playerPosition.fx, playerPosition.fy, playerPosition.fz),
		});

	let playerMarkerIcon: HTMLElement | null = $derived(playerMarker == null ? null : playerMarker.getElement()?.querySelector(".player-icon") as HTMLElement);

	onDestroy(() => {
		if (mapInstance) {
			mapInstance.remove();
			mapInstance = null;
		}
		if (webSocket) {
			webSocket.close();
			webSocket = null;
		}
	});

	$effect(() => {
		if (mapInstance && playerMarker && playerPosition && playerPosition.scene != data.mapName) {
			mapInstance.removeLayer(playerMarker);
			playerMarker = null;
		} else if (playerMarkerTransform && playerMarker) {
			playerMarker.setLatLng(playerMarkerTransform.position);
			if (playerMarkerIcon) {
				playerMarkerIcon.style.transform = `rotate(${playerMarkerTransform.rotation}deg)`;
			}
		}
	});

	$effect(() => {
		if (lastMapName === data.mapName) return;
		lastMapName = data.mapName;

		mapInstance?.remove();
		mapInstance = null;
		playerMarker = null;

		import('leaflet').then(L => {
			if (!config) return;
			if (!mapContainer) return;

			const worldSizeX = config.baseTilesX * config.tileSize;
			const worldSizeY = config.baseTilesY * config.tileSize;

			mapInstance = L.map(mapContainer, {
				crs: L.CRS.Simple,
				center: [worldSizeY / 2, worldSizeX / 2],
				zoom: config.zoom,
				minZoom: config.minZoom,
				maxZoom: config.maxZoom,
				maxBounds: [[-256, -256], [worldSizeY + 256, worldSizeX + 256]]
			});

			L.tileLayer(config.tileUrl, {
				tileSize: config.tileSize,
				noWrap: true,
				bounds: [[0, 0], [worldSizeY, worldSizeX]],
			}).addTo(mapInstance);

			function createPlayerMarker(transform: PlayerMarkerTransform) {
				return L.marker(transform.position, {
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
			}

			if (playerPosition && playerPosition.scene == data.mapName && playerMarkerTransform) {
				playerMarker = createPlayerMarker(playerMarkerTransform);
				playerMarker.addTo(mapInstance);
			}

			if (!webSocket) {
				webSocket = new WebSocket("ws://localhost:18584");

				webSocket.onopen = () => {
					console.log("WebSocket connection established.");
				};

				webSocket.onmessage = event => {
					const message = JSON.parse(event.data);

					const { scene, x, y, z, fx, fy, fz } = message;
					playerPosition = { scene: scene, x: x, y: y, z: z, fx: fx, fy: fy, fz: fz };

					if (mapInstance && !playerMarker && playerPosition && playerPosition.scene == data.mapName && playerMarkerTransform) {
						playerMarker = createPlayerMarker(playerMarkerTransform);
						playerMarker.addTo(mapInstance);
					}
				};

				webSocket.onerror = () => {
					console.log("WebSocket connection error. Closing connection.");
					if (mapInstance && playerMarker) {
						mapInstance.removeLayer(playerMarker);
						playerMarker = null;
					}
					webSocket?.close();
					webSocket = null;
				};

				webSocket.onclose = () => {
					console.log("WebSocket connection closed.");
					if (mapInstance && playerMarker) {
						mapInstance.removeLayer(playerMarker);
						playerMarker = null;
					}
					webSocket = null;
				};
			}

			const repository = new Repository();
			repository.init().then(async () => {
				const achievementMarkers = await repository.getAchievementTriggerMarkers(data.mapName);
				const characterMarkers = await repository.getCharacterMarkers(data.mapName);
				const doorMarkers = await repository.getDoorMarkers(data.mapName);
				const forgeMarkers = await repository.getForgeMarkers(data.mapName);
				const itemBagMarkers = await repository.getItemBagMarkers(data.mapName);
				const miningNodeMarkers = await repository.getMiningNodeMarkers(data.mapName);
				const secretPassageMarkers = await repository.getSecretPassageMarkers(data.mapName);
				const spawnPointMarkers = await repository.getSpawnPointMarkers(data.mapName);
				const teleportMarkers = await repository.getTeleportMarkers(data.mapName);
				const treasureLocMarkers = await repository.getTreasureLocMarkers(data.mapName);
				const waterMarkers = await repository.getWaterMarkers(data.mapName);
				const wishingWellMarkers = await repository.getWishingWellMarkers(data.mapName);
				const zoneLineMarkers = await repository.getZoneLineMarkers(data.mapName);

				function getRarityRank(marker: SpawnPointMarker) {
					if (marker.hasUnique) return 2;
					if (marker.hasRare) return 1;
					return 0;
				}

				// Sort markers so unique are drawn above rare and above common
				spawnPointMarkers.sort((a, b) => getRarityRank(a) - getRarityRank(b));

				let markers: Marker[] = [
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

				function createIcon(iconClass: string, color: string, radius: number) {
					const iconMarkup = `
						<div style="background-color:${color};border:1px solid white;border-radius:50%;width:${radius * 2}px;height:${radius * 2}px;display:flex;justify-content:center;align-items:center;opacity:0.8;">
								<i class="${iconClass}" style="color:white;font-size:${radius+2}px;"></i>
						</div>`;
					return L.divIcon({
						html: iconMarkup,
						className: 'div-icon',
						iconSize: [radius * 2, radius * 2],
						popupAnchor: [0, -radius]
					});
				}

				const coordinateIdToMarker = new Map<number, L.Marker>();

				markers.forEach(marker => {
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
						case 'character':
							if (marker.isUnique) {
								color = 'green';
								layer = 'Characters (Unique)';
								iconClass = 'fa-solid fa-user';
							} else {
								color = 'green';
								layer = 'Characters (Common)';
								iconClass = 'fa-solid fa-user';
							}
							if (!marker.isEnabled) {
								color = 'gray';
							}
							break;
						case 'door':
							color = 'brown';
							layer = 'Locked Doors';
							iconClass = 'fa-solid fa-key';
							break;
						case 'forge':
							color = 'black'
							layer = 'Forges'
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
						case 'spawn-point':
							if (marker.hasUnique) {
								color = 'black';
								radius = 12;
								layer = 'Enemies (Unique)';
								iconClass = 'fa-solid fa-skull';
							} else if (marker.hasRare) {
								color = 'red';
								layer = 'Enemies (Rare)';
								iconClass = 'fa-solid fa-skull';
							} else {
								color = 'blue';
								layer = 'Enemies (Common)';
								iconClass = 'fa-solid fa-skull';
							}
							if (!marker.isEnabled) {
								color = 'gray';
							}
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
							if (!marker.isEnabled) {
								color = 'gray';
							} else {
								color = 'purple';
							}
							radius = 12;
							layer = 'Zone Connections';
							iconClass = 'fa-solid fa-dungeon';
							break;
					}

					const icon = createIcon(iconClass, color, radius);

					const m = L.marker([
						marker.position.y - config.originY,
						marker.position.x - config.originX
					], {
						icon: icon,
					});

					if (marker.popup) {
						m.bindPopup(marker.popup);
					}

					coordinateIdToMarker.set(marker.coordinateId, m);

					m.on('popupopen', () => {
						const url = new URL(window.location.href);
						url.searchParams.set('coordinateId', marker.coordinateId.toString());
						window.history.replaceState({}, '', url);
					});

					m.on('popupclose', () => {
						const url = new URL(window.location.href);
						url.searchParams.delete('coordinateId');
						window.history.replaceState({}, '', url);
					});

					if (!layerGroups[layer]) {
						layerGroups[layer] = L.layerGroup();
					}
					layerGroups[layer].addLayer(m);
				});

				const overlayMaps: { [key: string]: L.LayerGroup } = {};
				for (const [name, group] of Object.entries(layerGroups)) {
					if (group.getLayers().length > 0) {
						if (mapInstance && name !== 'Fishing (WIP)') {
							group.addTo(mapInstance);
						}
						overlayMaps[name] = group;
					}
				}

				if (mapInstance) {
					L.control.layers(undefined, overlayMaps).addTo(mapInstance);

					const urlParams = new URLSearchParams(window.location.search);
					const coordinateIdParam = urlParams.get('coordinateId');
					if (coordinateIdParam) {
						const id = Number(coordinateIdParam);
						const markerToOpen = coordinateIdToMarker.get(id);
						if (markerToOpen) {
							markerToOpen.openPopup();
							mapInstance.panTo(markerToOpen.getLatLng());
						}
					}
				}
			});
		});
	});
</script>

<svelte:head>
	<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css" />
	<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.7.2/css/all.min.css" />
</svelte:head>

{#if config}
	<div bind:this={mapContainer} style="height:100vh;width:100vw;"></div>
{:else}
	<div style="display:flex;justify-content:center;align-items:center;height:100vh;font-size:2em;color:#888;">
		Map not found
	</div>
{/if}
