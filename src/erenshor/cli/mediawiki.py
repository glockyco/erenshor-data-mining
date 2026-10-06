"""MediaWiki clients that several command groups share."""

from __future__ import annotations

from typing import TYPE_CHECKING

from erenshor.infrastructure.wiki.client import MediaWikiClient

if TYPE_CHECKING:
    from erenshor.cli.context import CLIContext


def create_readonly_mediawiki_client(cli_ctx: CLIContext) -> MediaWikiClient:
    """Create a client that only reads the wiki and never logs in."""
    wiki_config = cli_ctx.config.global_.mediawiki
    return MediaWikiClient(
        api_url=wiki_config.api_url,
        bot_username=wiki_config.bot_username,
        bot_password=wiki_config.bot_password,
        batch_size=50,
        user_agent="erenshor-data-mining/1.0 (WoWMuch)",
    )
