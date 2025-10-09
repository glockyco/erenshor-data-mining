"""Registry module - backward compatibility only.

This module exists for backward compatibility only.
New code should import from:
- domain.entities.page (EntityRef, WikiPage)
- domain.value_objects.entity_type (EntityType)
- application.services.registry (WikiRegistry)
- infrastructure.storage.page_storage (PageStorage)
"""

# Backward compatibility exports
from erenshor.domain.entities.page import EntityRef, WikiPage
from erenshor.domain.value_objects.entity_type import EntityType
from erenshor.infrastructure.storage.page_storage import PageStorage

from .core import WikiRegistry
from .links import RegistryLinkResolver
from .migration import MappingImporter, RegistryBuilder

__all__ = [
    "EntityRef",
    "EntityType",
    "WikiPage",
    "WikiRegistry",
    "PageStorage",
    "MappingImporter",
    "RegistryBuilder",
    "RegistryLinkResolver",
]
