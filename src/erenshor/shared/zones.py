"""
Zone display name mapping helpers.

Maps internal scene names to wiki-friendly zone page names.
"""

from __future__ import annotations

from typing import Dict

__all__ = ["get_zone_display_name"]


ZONE_NAME_MAP: Dict[str, str] = {
    "Abyssal": "Abyssal Lake",
    "Azure": "Port Azure",
    "Azynthi": "Azynthi's Garden|Azynthi's Garden (Dimensional Rift)",
    "AzynthiClear": "Azynthi's Garden",
    "Blight": "The Blight",
    "Bonepits": "The Bone Pits",
    "Brake": "Faerie's Brake",
    "Braxonia": "Fallen Braxonia",
    "Braxonian": "Braxonian Desert",
    "DuskenPortal": "Mysterious Portal|Mysterious Portal (1)",
    "Duskenlight": "Duskenlight Coast",
    "Elderstone": "Elderstone Mines",
    "FernallaField": "Fernalla's Revival Plains",
    "FernallaPortal": "Mysterious Portal|Mysterious Portal (2)",
    "Hidden": "Hidden Hills",
    "Jaws": "Jaws of Sivakaya",
    "Krakengard": "Old Krakengard",
    "Loomingwood": "Loomingwood",
    "Malaroth": "Malaroth's Nesting Grounds",
    "PrielPlateau": "Prielian Cascade",
    "Ripper": "Ripper's Keep",
    "RipperPortal": "Mysterious Portal|Mysterious Portal (3)",
    "Rockshade": "Rockshade Hold",
    "Rottenfoot": "Rottenfoot",
    "SaltedStrand": "Blacksalt Strand",
    "ShiveringStep": "Shivering Step",
    "ShiveringTomb": "Shivering Tomb",
    "Silkengrass": "Silkengrass Meadowlands",
    "Soluna": "Soluna's Landing",
    "Stowaway": "Stowaway's Step",
    "Tutorial": "Island Tomb",
    "Undercity": "Lost Cellar",
    "Underspine": "Underspine Hollow",
    "Vitheo": "Vitheo's Watch",
    "VitheosEnd": "Vitheo's Rest",
    "Willowwatch": "Willowwatch Ridge",
    "Windwashed": "Windwashed Pass",
}


def get_zone_display_name(scene_name: str) -> str:
    if not scene_name:
        return scene_name
    return ZONE_NAME_MAP.get(scene_name, scene_name)
