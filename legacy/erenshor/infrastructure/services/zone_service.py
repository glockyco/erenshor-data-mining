from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Dict

from erenshor.infrastructure.config.paths import get_path_resolver
from erenshor.shared.zones import get_zone_display_name as _fallback_zone_name

__all__ = ["ZoneService"]


logger = logging.getLogger(__name__)


@dataclass
class ZoneService:
    names: Dict[str, str]

    @classmethod
    def load(cls) -> "ZoneService":
        """Load zone names from config using PathResolver."""
        resolver = get_path_resolver()
        zones_file = resolver.zones_json

        if not zones_file.exists():
            return cls(names={})

        try:
            data = json.loads(zones_file.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return cls(names={str(k): str(v) for k, v in data.items()})
        except Exception as e:
            logger.warning(
                f"Failed to load zone names from {zones_file}: {e}. Using empty mapping."
            )
        return cls(names={})

    def get_display_name(self, scene_name: str) -> str:
        if not scene_name:
            return scene_name
        return self.names.get(scene_name, _fallback_zone_name(scene_name))
