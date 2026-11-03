"""Shared constants for the capture pipeline."""

TILE_SIZE = 256
"""Width and height in pixels of each generated map tile."""

WS_PORT = 18587
"""Port of the MapTileCapture mod's WebSocket server (`CaptureWebSocketServer.Location`).

Interactive Map Companion uses 18585 and shares the live map on 18586.
"""
