"""Wiki service for orchestrating wiki page fetch/generate/deploy workflow.

This module provides the WikiService class that coordinates the three-stage wiki
workflow by delegating to specialized services:

1. Fetch: WikiFetchService downloads existing pages from MediaWiki
2. Generate: WikiGenerateService creates new wiki pages from database
3. Deploy: WikiDeployService uploads generated pages to MediaWiki

The service uses local file storage (WikiStorage) to enable:
- Reviewing generated content before deployment
- Interrupting and resuming workflows
- Testing and validation without hitting the wiki
- Tracking what changed between versions

Example:
    >>> from erenshor.application.services.wiki_service import WikiService
    >>> from erenshor.infrastructure.wiki.client import MediaWikiClient
    >>> from pathlib import Path
    >>>
    >>> # Initialize service
    >>> wiki_client = MediaWikiClient(api_url="https://erenshor.wiki.gg/api.php")
    >>> storage = WikiStorage(Path("variants/main/wiki"))
    >>> service = WikiService(
    ...     wiki_client=wiki_client,
    ...     storage=storage,
    ...     item_repo=item_repo,
    ...     character_repo=character_repo,
    ...     spell_repo=spell_repo,
    ...     skill_repo=skill_repo,
    ...     registry_resolver=registry_resolver,
    ... )
    >>>
    >>> # Three-stage workflow
    >>> service.fetch_all()
    >>> service.generate_all()
    >>> # Review files in variants/main/wiki/generated/
    >>> service.deploy_all()
"""

from loguru import logger
from rich.console import Console

from erenshor.application.services.wiki_deploy_service import WikiDeployService
from erenshor.application.services.wiki_fetch_service import WikiFetchService
from erenshor.application.services.wiki_generate_service import WikiGenerateService
from erenshor.application.services.wiki_page import OperationResult
from erenshor.application.services.wiki_storage import WikiStorage
from erenshor.infrastructure.database.repositories.characters import CharacterRepository
from erenshor.infrastructure.database.repositories.factions import FactionRepository
from erenshor.infrastructure.database.repositories.items import ItemRepository
from erenshor.infrastructure.database.repositories.loot_tables import LootTableRepository
from erenshor.infrastructure.database.repositories.skills import SkillRepository
from erenshor.infrastructure.database.repositories.spawn_points import SpawnPointRepository
from erenshor.infrastructure.database.repositories.spells import SpellRepository
from erenshor.infrastructure.wiki.client import MediaWikiClient
from erenshor.registry.resolver import RegistryResolver


class WikiServiceError(Exception):
    """Base exception for wiki service errors."""

    pass


class WikiService:
    """Service for orchestrating wiki page fetch/generate/deploy workflow.

    This service coordinates the three-stage wiki workflow by delegating to
    specialized services:
    1. Fetch: WikiFetchService downloads pages from MediaWiki
    2. Generate: WikiGenerateService creates pages from DB
    3. Deploy: WikiDeployService uploads pages to MediaWiki

    Example:
        >>> service = WikiService(
        ...     wiki_client=wiki_client,
        ...     storage=storage,
        ...     item_repo=item_repo,
        ...     character_repo=character_repo,
        ...     spell_repo=spell_repo,
        ...     skill_repo=skill_repo,
        ...     registry_resolver=registry_resolver,
        ... )
        >>> service.fetch_all()
        >>> service.generate_all()
        >>> service.deploy_all()
    """

    def __init__(
        self,
        wiki_client: MediaWikiClient,
        storage: WikiStorage,
        item_repo: ItemRepository,
        character_repo: CharacterRepository,
        spell_repo: SpellRepository,
        skill_repo: SkillRepository,
        faction_repo: FactionRepository,
        spawn_repo: SpawnPointRepository,
        loot_repo: LootTableRepository,
        registry_resolver: RegistryResolver,
        console: Console | None = None,
    ) -> None:
        """Initialize wiki service.

        Args:
            wiki_client: MediaWiki API client for fetching/updating pages.
            storage: Local file storage for wiki pages.
            item_repo: Repository for fetching items from database.
            character_repo: Repository for fetching characters from database.
            spell_repo: Repository for fetching spells from database.
            skill_repo: Repository for fetching skills from database.
            faction_repo: Repository for faction data.
            spawn_repo: Repository for spawn point data.
            loot_repo: Repository for loot table data.
            registry_resolver: Registry resolver for page title resolution.
            console: Rich console for output (optional).
        """
        console = console or Console()

        # Initialize specialized services
        self._fetch_service = WikiFetchService(
            wiki_client=wiki_client,
            storage=storage,
            item_repo=item_repo,
            character_repo=character_repo,
            spell_repo=spell_repo,
            skill_repo=skill_repo,
            registry_resolver=registry_resolver,
            console=console,
        )

        self._generate_service = WikiGenerateService(
            storage=storage,
            item_repo=item_repo,
            character_repo=character_repo,
            spell_repo=spell_repo,
            skill_repo=skill_repo,
            faction_repo=faction_repo,
            spawn_repo=spawn_repo,
            loot_repo=loot_repo,
            registry_resolver=registry_resolver,
            console=console,
        )

        self._deploy_service = WikiDeployService(
            wiki_client=wiki_client,
            storage=storage,
            console=console,
        )

        logger.debug("WikiService initialized")

    def fetch_all(
        self,
        dry_run: bool = False,
        limit: int | None = None,
        force_refetch: bool = False,
        page_titles: list[str] | None = None,
    ) -> OperationResult:
        """Fetch wiki pages for all entities or specified page titles.

        Delegates to WikiFetchService.

        Args:
            dry_run: If True, simulate fetch without actually downloading.
            limit: Maximum number of pages to fetch (for testing).
            force_refetch: If True, re-fetch pages even if already cached.
            page_titles: If specified, only fetch these specific page titles.

        Returns:
            OperationResult with summary statistics and warnings/errors.
        """
        return self._fetch_service.fetch_all(
            dry_run=dry_run,
            limit=limit,
            force_refetch=force_refetch,
            page_titles=page_titles,
        )

    def generate_all(
        self,
        dry_run: bool = False,
        limit: int | None = None,
        page_titles: list[str] | None = None,
    ) -> OperationResult:
        """Generate wiki pages for all entities or specified page titles.

        Delegates to WikiGenerateService.

        Args:
            dry_run: If True, generate content but don't save to storage.
            limit: Maximum number of pages to generate (for testing).
            page_titles: If specified, only generate these specific page titles.

        Returns:
            OperationResult with summary statistics and warnings/errors.
        """
        return self._generate_service.generate_all(
            dry_run=dry_run,
            limit=limit,
            page_titles=page_titles,
        )

    def deploy_all(
        self,
        dry_run: bool = False,
        limit: int | None = None,
        page_titles: list[str] | None = None,
    ) -> OperationResult:
        """Deploy generated wiki pages to MediaWiki.

        Delegates to WikiDeployService.

        Args:
            dry_run: If True, simulate deployment without actually uploading.
            limit: Maximum number of pages to deploy (for testing).
            page_titles: If specified, only deploy these specific page titles.

        Returns:
            OperationResult with summary statistics and warnings/errors.
        """
        return self._deploy_service.deploy_all(
            dry_run=dry_run,
            limit=limit,
            page_titles=page_titles,
        )
