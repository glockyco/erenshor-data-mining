"""Domain protocols (interfaces)."""

from erenshor.domain.protocols.renderer import TemplateRenderer
from erenshor.domain.protocols.repositories import (
    CharacterRepository,
    ItemRepository,
    SpellRepository,
)
from erenshor.domain.protocols.storage import PageStorage

__all__ = [
    "ItemRepository",
    "CharacterRepository",
    "SpellRepository",
    "PageStorage",
    "TemplateRenderer",
]
