"""Publishers for deploying formatted content to external destinations.

This package provides publishers that push data to various targets:
- Google Sheets
- MediaWiki (existing, in wiki module)
- Filesystem
- Cloud storage (future)
"""

from erenshor.infrastructure.publishers.sheets import (
    GoogleSheetsPublisher,
    PublishResult,
)

__all__ = [
    "GoogleSheetsPublisher",
    "PublishResult",
]
