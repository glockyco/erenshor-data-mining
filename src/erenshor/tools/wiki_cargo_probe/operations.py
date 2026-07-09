from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from erenshor.infrastructure.wiki.client import MediaWikiAPIError, MediaWikiClient

from .models import OWNER, TemplatePage


@dataclass(slots=True)
class ProbeRunContext:
    client: MediaWikiClient
    owner: str = OWNER
    created_pages: list[str] = field(default_factory=list)

    def page_exists(self, title: str) -> bool:
        return self.client.get_page_revision_metadata(title, assertion="user", assert_user=self.owner) is not None

    def create_page(self, title: str, content: str) -> None:
        if self.page_exists(title):
            raise RuntimeError("Refusing to overwrite existing probe page: " + title)
        self.client.edit_page(
            title,
            content,
            summary="Create temporary Cargo storage probe",
            create_only=True,
            bot=True,
        )
        self.created_pages.append(title)

    def create_template_pages(self, templates: tuple[TemplatePage, ...]) -> None:
        for template in templates:
            self.create_page(template.title, template.content)

    def edit_existing_page(self, title: str, content: str, summary: str) -> None:
        self.client.edit_page(title, content, summary=summary, create_only=False, no_create=True, bot=True)

    def forget_created_page(self, title: str) -> None:
        self.created_pages.remove(title)

    def cleanup_created_pages(self) -> list[dict[str, Any]]:
        return [{"title": title, "result": self.delete_page(title)} for title in reversed(self.created_pages)]

    def purge_pages(self, titles: tuple[str, ...] | list[str]) -> tuple[str, ...]:
        return self.client.purge_pages(
            list(titles),
            force_link_update=True,
            assertion="user",
            assert_user=self.owner,
        )

    def purge_pages_in_batches(self, titles: tuple[str, ...], batch_size: int = 50) -> list[tuple[str, ...]]:
        purges = []
        for start in range(0, len(titles), batch_size):
            purges.append(self.purge_pages(titles[start : start + batch_size]))
        return purges

    def recreate_tables(self, template: str, *, create_replacement: bool = False) -> dict[str, Any]:
        try:
            return {
                "ok": True,
                "create_replacement": create_replacement,
                "response": self.client.recreate_cargo_tables(
                    template,
                    create_replacement=create_replacement,
                    assertion="user",
                    assert_user=self.owner,
                ),
            }
        except MediaWikiAPIError as exc:
            return {
                "ok": False,
                "create_replacement": create_replacement,
                "label": "cargorecreatetables " + template,
                "code": exc.code,
                "info": exc.info,
                "error": str(exc),
            }

    def recreate_data(self, template: str, table: str, *, replace_old_rows: bool = True) -> dict[str, Any]:
        try:
            return {
                "ok": True,
                "replace_old_rows": replace_old_rows,
                "response": self.client.recreate_cargo_data(
                    template,
                    table,
                    replace_old_rows=replace_old_rows,
                    assertion="user",
                    assert_user=self.owner,
                ),
            }
        except MediaWikiAPIError as exc:
            return {
                "ok": False,
                "label": "cargorecreatedata " + template + " " + table,
                "code": exc.code,
                "info": exc.info,
                "error": str(exc),
            }

    def query_cargo_table(
        self, *, tables: str, fields: str, where: str | None = None, limit: int = 50
    ) -> dict[str, Any]:
        try:
            rows = self.client.query_cargo_table(
                tables=tables,
                fields=fields,
                where=where,
                limit=limit,
                assertion="user",
                assert_user=self.owner,
            )
            return {"ok": True, "rows": rows}
        except MediaWikiAPIError as exc:
            return {"ok": False, "code": exc.code, "info": exc.info, "error": str(exc)}

    def parse_page_html(self, page_title: str) -> dict[str, Any]:
        try:
            payload = self.client._request(
                {
                    "action": "parse",
                    "page": page_title,
                    "prop": "text",
                    "formatversion": "2",
                    "assert": "user",
                    "assertuser": self.owner,
                }
            )
            html = str(payload.get("parse", {}).get("text", ""))
            return {
                "ok": True,
                "html_length": len(html),
                "contains_probe_text": any(text in html for text in ("Temporary", "B1", "B2", "ProbeValue")),
            }
        except MediaWikiAPIError as exc:
            return {"ok": False, "code": exc.code, "info": exc.info, "error": str(exc)}

    def delete_page(self, title: str) -> dict[str, Any]:
        try:
            return {
                "ok": True,
                "response": self.client.delete_page(
                    title,
                    reason="Clean up temporary Cargo storage probe page",
                    assertion="user",
                    assert_user=self.owner,
                ),
            }
        except MediaWikiAPIError as exc:
            return {"ok": False, "label": "delete " + title, "code": exc.code, "info": exc.info, "error": str(exc)}
