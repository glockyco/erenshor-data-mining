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
) -> dict[str, int] | None:
    """Open an interactive browser crop UI and return the chosen rect.

    Returns ``{"top": int, "right": int, "bottom": int, "left": int}`` on
    success, or ``None`` if the user closes the browser without applying.
    """
    overlay_bytes = _render_overlay(master_path, config)
    b64 = base64.b64encode(overlay_bytes).decode()

    result: dict[str, int] | None = None
    shutdown_event = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            html = _build_html(zone_key, b64, master_path)
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
        # Serve until crop is applied or user interrupts.
        # After shutdown_event fires, process one more request so the
        # HTTP 200 response is delivered before we close the socket.
        while not shutdown_event.is_set():
            server.handle_request()
        server.handle_request()  # drain the response
    except KeyboardInterrupt:
        logger.warning("Crop UI interrupted")
    finally:
        server.server_close()

    if result:
        logger.info(f"Crop rect for {zone_key}: {result}")
    else:
        logger.warning(f"No crop applied for {zone_key}")

    return result


def _render_overlay(master_path: Path, config: dict[str, Any]) -> bytes:
    """Draw a tile-grid overlay on the master image and return PNG bytes."""
    img = Image.open(master_path).convert("RGBA")
    draw = ImageDraw.Draw(img)
    tile_size = config.get("tileSize", 256)

    # Draw grid lines
    for x in range(0, img.width, tile_size):
        draw.line([(x, 0), (x, img.height)], fill=(255, 0, 0, 80), width=1)
    for y in range(0, img.height, tile_size):
        draw.line([(0, y), (img.width, y)], fill=(255, 0, 0, 80), width=1)

    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def _build_html(zone_key: str, b64_image: str, master_path: Path) -> str:
    """Return the single-page crop UI HTML."""
    img = Image.open(master_path)
    w, h = img.width, img.height
    img.close()

    return f"""\
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Crop: {zone_key}</title>
<style>
  body {{ margin: 0; background: #1a1a1a; color: #eee; font-family: monospace;
          display: flex; justify-content: center; align-items: flex-start;
          padding: 20px; box-sizing: border-box; min-height: 100vh; }}
  #container {{ position: relative; display: inline-block; }}
  #img {{ display: block; max-width: calc(100vw - 40px); max-height: calc(100vh - 40px);
           object-fit: contain; }}
  #overlay {{ position: absolute; border: 2px dashed #0f0; pointer-events: none; }}
  #readout {{ position: fixed; top: 10px; right: 10px; background: #333; padding: 10px;
              border-radius: 4px; z-index: 10; }}
  #apply {{ position: fixed; bottom: 20px; right: 20px; padding: 12px 24px;
            background: #0a0; color: #fff; border: none; cursor: pointer;
            font-size: 16px; border-radius: 4px; z-index: 10; }}
  #apply:hover {{ background: #0c0; }}
</style>
</head>
<body>
<div id="readout">
  <div>top: <span id="rt">0</span></div>
  <div>right: <span id="rr">0</span></div>
  <div>bottom: <span id="rb">0</span></div>
  <div>left: <span id="rl">0</span></div>
</div>
<button id="apply">Apply Crop</button>
<div id="container">
  <img id="img" src="data:image/png;base64,{b64_image}" draggable="false">
  <div id="overlay"></div>
</div>
<script>
(function() {{
  const W = {w}, H = {h};
  let sx = 0, sy = 0, ex = W, ey = H, dragging = false;
  const ov = document.getElementById('overlay');
  const img = document.getElementById('img');

  function pxToImg(clientX, clientY) {{
    const r = img.getBoundingClientRect();
    const scaleX = W / r.width, scaleY = H / r.height;
    return [
      Math.round(Math.max(0, Math.min(W, (clientX - r.left) * scaleX))),
      Math.round(Math.max(0, Math.min(H, (clientY - r.top) * scaleY)))
    ];
  }}

  function update() {{
    const l = Math.min(sx, ex), t = Math.min(sy, ey);
    const rr = Math.max(sx, ex), b = Math.max(sy, ey);
    const r = img.getBoundingClientRect();
    const scaleX = r.width / W, scaleY = r.height / H;
    ov.style.left = (l * scaleX) + 'px';
    ov.style.top = (t * scaleY) + 'px';
    ov.style.width = ((rr - l) * scaleX) + 'px';
    ov.style.height = ((b - t) * scaleY) + 'px';
    document.getElementById('rt').textContent = t;
    document.getElementById('rr').textContent = W - rr;
    document.getElementById('rb').textContent = H - b;
    document.getElementById('rl').textContent = l;
  }}

  img.addEventListener('mousedown', function(e) {{
    e.preventDefault();
    [sx, sy] = pxToImg(e.clientX, e.clientY);
    dragging = true;
  }});
  document.addEventListener('mousemove', function(e) {{
    if (!dragging) return;
    [ex, ey] = pxToImg(e.clientX, e.clientY);
    update();
  }});
  document.addEventListener('mouseup', function() {{ dragging = false; }});

  document.getElementById('apply').addEventListener('click', function() {{
    const l = Math.min(sx, ex), t = Math.min(sy, ey);
    const rr = Math.max(sx, ex), b = Math.max(sy, ey);
    const btn = document.getElementById('apply');
    btn.disabled = true;
    btn.textContent = 'Applying...';
    fetch(window.location.href, {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{top: t, right: W - rr, bottom: H - b, left: l}})
    }}).then(function(r) {{
      if (r.ok) {{
        btn.textContent = 'Applied \u2014 close this tab';
        btn.style.background = '#666';
      }}
    }}).catch(function() {{
      btn.textContent = 'Error \u2014 try again';
      btn.disabled = false;
    }});
  }});

  update();
}})();
</script>
</body>
</html>"""
