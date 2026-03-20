from __future__ import annotations

import base64
import io
import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

from loguru import logger
from PIL import Image, ImageDraw

CROP_PORT = 18587


def serve_crop_ui(
    master_path: Path,
    zone_key: str,
    config: dict[str, Any],
    repo_root: Path,
) -> dict[str, Any] | None:
    """Open an interactive crop UI and return the chosen selection.

    The UI shows a fixed-size selection box (sized to the tile grid at
    maxZoom) that the user moves freely over the master image to frame
    the content. Tile counts in X and Y can be adjusted via number inputs,
    which resizes the box accordingly.

    Returns ``{"x": int, "y": int, "tilesX": int, "tilesY": int}`` where
    x/y is the top-left corner of the selection in master pixels, or
    ``None`` if the user closes without applying.
    """
    overlay_bytes = _render_overlay(master_path, config)
    b64 = base64.b64encode(overlay_bytes).decode()

    result: dict[str, Any] | None = None
    shutdown_event = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            html = _build_html(zone_key, b64, master_path, config)
            self.wfile.write(html.encode())

        def do_POST(self) -> None:
            nonlocal result
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            result = json.loads(body)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
            shutdown_event.set()

        def log_message(self, fmt: str, *args: Any) -> None:
            pass  # silence request logs

    server = HTTPServer(("127.0.0.1", CROP_PORT), Handler)
    server.timeout = 1.0

    url = f"http://localhost:{CROP_PORT}"
    logger.info(f"Opening crop UI for {zone_key} at {url}")
    webbrowser.open(url)

    try:
        while not shutdown_event.is_set():
            server.handle_request()
        server.handle_request()  # drain the response
    except KeyboardInterrupt:
        logger.warning("Crop UI interrupted")
    finally:
        server.server_close()

    if result:
        logger.info(f"Crop selection for {zone_key}: {result}")
    else:
        logger.warning(f"No crop applied for {zone_key}")

    return result


def _render_overlay(master_path: Path, config: dict[str, Any]) -> bytes:
    """Draw a tile-grid overlay on the master image and return PNG bytes."""
    img = Image.open(master_path).convert("RGBA")
    draw = ImageDraw.Draw(img)
    tile_size = config.get("tileSize", 256)
    max_zoom: int = config.get("maxZoom", 0)
    px_per_tile = tile_size * (2**max_zoom)

    for x in range(0, img.width, px_per_tile):
        draw.line([(x, 0), (x, img.height)], fill=(255, 0, 0, 80), width=1)
    for y in range(0, img.height, px_per_tile):
        draw.line([(0, y), (img.width, y)], fill=(255, 0, 0, 80), width=1)

    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def _build_html(
    zone_key: str,
    b64_image: str,
    master_path: Path,
    config: dict[str, Any],
) -> str:
    """Return the single-page crop UI HTML."""
    img = Image.open(master_path)
    w, h = img.width, img.height
    img.close()

    max_zoom: int = config.get("maxZoom", 0)
    tile_size: int = config.get("tileSize", 256)
    init_tiles_x: int = config.get("baseTilesX", 1)
    init_tiles_y: int = config.get("baseTilesY", 1)
    # Pixel size of one tile at maxZoom in the master image
    px_per_tile = tile_size * (2**max_zoom)

    return f"""\
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Crop: {zone_key}</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: #1a1a1a; color: #eee; font-family: monospace;
          display: flex; flex-direction: column; align-items: center;
          padding: 20px; gap: 12px; min-height: 100vh; }}
  #controls {{ display: flex; gap: 16px; align-items: center;
               background: #2a2a2a; padding: 10px 16px; border-radius: 6px; }}
  #controls label {{ display: flex; gap: 6px; align-items: center; }}
  #controls input {{ width: 52px; background: #444; color: #eee; border: 1px solid #666;
                     padding: 4px 6px; border-radius: 3px; font: inherit; text-align: center; }}
  #readout {{ background: #2a2a2a; padding: 8px 14px; border-radius: 6px; font-size: 12px; }}
  #container {{ position: relative; display: inline-block; }}
  #img {{ display: block; max-width: calc(100vw - 40px); max-height: calc(100vh - 160px);
          object-fit: contain; user-select: none; }}
  #box {{ position: absolute; border: 2px solid #0f0; background: rgba(0,255,0,0.06);
          cursor: move; pointer-events: all; }}
  #apply {{ padding: 10px 28px; background: #0a0; color: #fff; border: none;
            cursor: pointer; font-size: 15px; border-radius: 4px; }}
  #apply:hover {{ background: #0c0; }}
  #apply:disabled {{ background: #555; cursor: default; }}
</style>
</head>
<body>
<div id="controls">
  <label>Tiles X <input id="tx" type="number" min="1" max="16" value="{init_tiles_x}"></label>
  <label>Tiles Y <input id="ty" type="number" min="1" max="16" value="{init_tiles_y}"></label>
  <span style="color:#aaa; font-size:12px">Drag the green box to frame the content</span>
</div>
<div id="readout">origin offset: x=0 y=0 &nbsp;|&nbsp; box: 0x0 px</div>
<div id="container">
  <img id="img" src="data:image/png;base64,{b64_image}" draggable="false">
  <div id="box"></div>
</div>
<button id="apply">Apply</button>

<script>
(function() {{
  const W = {w}, H = {h};
  const PX_PER_TILE = {px_per_tile};

  let tilesX = {init_tiles_x}, tilesY = {init_tiles_y};
  // Box position in master pixels (top-left corner)
  let boxX = 0, boxY = 0;
  let dragging = false, dragStartX = 0, dragStartY = 0, boxStartX = 0, boxStartY = 0;

  const img = document.getElementById('img');
  const box = document.getElementById('box');
  const readout = document.getElementById('readout');

  function boxPxW() {{ return tilesX * PX_PER_TILE; }}
  function boxPxH() {{ return tilesY * PX_PER_TILE; }}

  function imgScale() {{
    const r = img.getBoundingClientRect();
    return {{ sx: r.width / W, sy: r.height / H, left: r.left, top: r.top }};
  }}

  function clamp() {{
    boxX = Math.max(0, Math.min(W - boxPxW(), boxX));
    boxY = Math.max(0, Math.min(H - boxPxH(), boxY));
  }}

  function render() {{
    clamp();
    const s = imgScale();
    box.style.left   = (boxX * s.sx) + 'px';
    box.style.top    = (boxY * s.sy) + 'px';
    box.style.width  = (boxPxW() * s.sx) + 'px';
    box.style.height = (boxPxH() * s.sy) + 'px';
    readout.textContent =
      'origin offset: x=' + boxX + ' y=' + boxY +
      '  |  box: ' + boxPxW() + 'x' + boxPxH() + ' px' +
      '  (' + tilesX + 'x' + tilesY + ' tiles)';
  }}

  // Tile count inputs
  document.getElementById('tx').addEventListener('input', function() {{
    tilesX = Math.max(1, parseInt(this.value) || 1);
    render();
  }});
  document.getElementById('ty').addEventListener('input', function() {{
    tilesY = Math.max(1, parseInt(this.value) || 1);
    render();
  }});

  // Drag to move box
  box.addEventListener('mousedown', function(e) {{
    e.preventDefault();
    dragging = true;
    dragStartX = e.clientX;
    dragStartY = e.clientY;
    boxStartX = boxX;
    boxStartY = boxY;
  }});
  document.addEventListener('mousemove', function(e) {{
    if (!dragging) return;
    const s = imgScale();
    boxX = boxStartX + (e.clientX - dragStartX) / s.sx;
    boxY = boxStartY + (e.clientY - dragStartY) / s.sy;
    render();
  }});
  document.addEventListener('mouseup', function() {{
    if (dragging) {{
      dragging = false;
      // Snap box position to integer pixels
      boxX = Math.round(boxX);
      boxY = Math.round(boxY);
      render();
    }}
  }});

  // Rerender on window resize
  window.addEventListener('resize', render);
  img.addEventListener('load', render);

  document.getElementById('apply').addEventListener('click', function() {{
    clamp();
    boxX = Math.round(boxX);
    boxY = Math.round(boxY);
    const btn = this;
    btn.disabled = true;
    btn.textContent = 'Applying...';
    fetch(window.location.href, {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{ x: boxX, y: boxY, tilesX: tilesX, tilesY: tilesY }})
    }}).then(function(r) {{
      if (r.ok) {{
        btn.textContent = 'Applied \u2014 close this tab';
        btn.style.background = '#555';
      }}
    }}).catch(function() {{
      btn.textContent = 'Error \u2014 try again';
      btn.disabled = false;
    }});
  }});

  render();
}})();
</script>
</body>
</html>"""
