"""
Infrastructure Layer.

Handles external integrations including database access, wiki API,
storage operations, and external service configurations. This layer
provides implementations for interfaces defined in other layers.

Modules:
- config: Configuration management
- database: SQLite database access and repositories
- publishers: External publishing (Google Sheets, MediaWiki)
- storage: File system storage operations
- wiki: MediaWiki API client
"""
