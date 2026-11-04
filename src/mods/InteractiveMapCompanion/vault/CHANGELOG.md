# Changelog

## v2026.1104.0

- Show the live map on your phone or another PC on the same network. Choose **Live** on the map, then **Show on another device**, and scan the code or open the address it shows.
- Live is now a button at the top right of the map instead of a switch in the sidebar.
- The in-game overlay opens the map with Live already on.
- Other devices can only connect while you share the map. The `Server.AllowLanConnections` setting is gone.

## v2026.718.0

- Fixed the overlay shortcut not responding.
- Removed repeated browser paint statistics from the debug log.
- Links can now open any page, with the Back and Map buttons available to return.

## v2026.717.0

- Added back, forward, and map navigation buttons to the in-game browser window.
- Reduced redundant browser input updates while the pointer is stationary.

## v2026.716.0

- Added native Lunaris support for live map tracking and the in-game overlay.
- Added configurable server, tracking, overlay, and logging settings through the Lunaris config UI.
- Ensured unloading the mod closes the local server and browser overlay cleanly.
