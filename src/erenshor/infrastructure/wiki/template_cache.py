from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from .client import WikiAPIClient

__all__ = ["fetch_templates"]


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _safe_title_to_path(title: str) -> Path:
    # Store as Template/<Name>.txt or Module/<Name>.lua etc.
    if ":" in title:
        prefix, name = title.split(":", 1)
        return Path(prefix) / f"{name}.txt"
    return Path(title + ".txt")


def fetch_templates(
    store: WikiAPIClient,
    out_dir: Path,
    *,
    delay: float = 1.0,
    batch_size: int = 25,
) -> Path:
    """Fetch all templates and write a cache under out_dir.

    Writes:
      - out_dir/Template/<Name>.txt (wikitext)
      - out_dir/Templatedata/<Name>.json (when available)
      - out_dir/index.json (manifest)
    """
    out_dir = Path(out_dir)
    (out_dir / "Template").mkdir(parents=True, exist_ok=True)
    (out_dir / "Templatedata").mkdir(parents=True, exist_ok=True)

    titles = store.list_pages(namespace=10)
    entries: List[Dict[str, Any]] = []
    # Fetch wikitext in batches
    for i in range(0, len(titles), batch_size):
        batch = titles[i : i + batch_size]
        data = store.fetch_batch(batch)
        for title, content in data.items():
            if content is None:
                continue
            rel = _safe_title_to_path(title)
            dest = out_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
            entries.append(
                {
                    "title": title,
                    "file": str(rel),
                    "sha256": _sha256_text(content),
                }
            )
        if i + batch_size < len(titles) and delay > 0:
            import time as _t

            _t.sleep(delay)

    # Fetch templatedata (in their own batches)
    for i in range(0, len(titles), batch_size):
        batch = titles[i : i + batch_size]
        td = store.fetch_templatedata(batch)
        for title, payload in td.items():
            name = title.split(":", 1)[-1]
            (out_dir / "Templatedata" / f"{name}.json").write_text(
                json.dumps(payload, indent=2), encoding="utf-8"
            )

    # Write index.json
    now = datetime.now(timezone.utc).isoformat()
    (out_dir / "index.json").write_text(
        json.dumps({"fetched_at": now, "templates": entries}, indent=2),
        encoding="utf-8",
    )
    return out_dir / "index.json"
