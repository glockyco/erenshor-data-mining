"""Translate between shipped spell types and the readable catalog labels."""

_BARD_LABELS = {
    "SongDissonance": "Dissonance",
    "SongInspiration": "Inspiration",
    "SongCombo": "Song Combo",
    "SongGeneric": "Song",
}
_GAME_TYPES = {label: kind for kind, label in _BARD_LABELS.items()}


def catalog_spell_type(kind: str) -> str:
    return _BARD_LABELS.get(kind, kind)


def game_spell_type(label: str) -> str:
    return _GAME_TYPES.get(label, label)
