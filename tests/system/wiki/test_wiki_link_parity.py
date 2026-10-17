"""Compare the offline semantic-link audit with real Scribunto and template renders."""

from __future__ import annotations

import html
import json
import re
from collections.abc import Iterator
from html.parser import HTMLParser
from typing import Any

import httpx
import mwparserfromhell
import pytest
from tests.system.wiki.conftest import API_URL

from erenshor.application.wiki_deploy.link_audit import LinkTargets, audit_links
from erenshor.application.wiki_lua.link_catalog import LinkCatalogEntry

# Each call is sent unchanged through both hosts. Expected states distinguish a
# correctly unresolved or shared link from two implementations making the same mistake.
CASES = (
    ("QuestLink|Quest Line Fixture", "shared"),
    ("ItemLink|Abyssal Plate", "resolved"),
    ("ItemLink|Priel Note", "shared"),
    ("ItemLink|Shared Item Fixture", "shared"),
    ("CharacterLink|Dire Wolf", "shared"),
    ("ItemLink|Different Image Fixture", "ambiguous"),
    ("AbilityLink|Flame Bolt", "ambiguous"),
    ("ItemLink|Priel Note (1)", "manual"),
    ("ItemLink|priel note", "manual"),
    ("ItemLink|priel_Note", "shared"),
    ("ItemLink|Priel Note#Notes", "shared"),
    ("ItemLink|Unknown Target", "manual"),
    ("ItemLink|1=Abyssal Plate", "resolved"),
    ("ItemLink|Abyssal Plate|1=Priel Note", "shared"),
    ("ItemLink|link=|page=Abyssal Plate", "resolved"),
    ("ItemLink|link=-|Abyssal Plate", "resolved"),
    ("ItemLink|item=|name=Abyssal Plate", "resolved"),
    ("ItemLink|stablekey=item:chest - 38 - abyssal plate", "resolved"),
    ("ItemLink|stableKey=item:chest - 38 - abyssal plate", "resolved"),
    ("ItemLink|stablekey=|key=item:chest - 38 - abyssal plate", "resolved"),
    ("ItemLink|id=item:chest - 38 - abyssal plate|Priel Note", "shared"),
    ("ItemLink|stable_key=item:chest - 38 - abyssal plate|Priel Note", "shared"),
    ("ItemLink|Stablekey=item:chest - 38 - abyssal plate|Priel Note", "shared"),
    ("ItemLink|stablekey=item:unknown|Abyssal Plate", "unresolved"),
    ("ItemLink|stablekey=spell:minor_lightning|Abyssal Plate", "unresolved"),
    ("ItemLink|stablekey=item:chest - 38 - abyssal plate|Priel Note", "resolved"),
    ("ItemLink|stablekey=item:chest - 38 - abyssal plate|link=Priel Note", "resolved"),
    ("ItemLink|stablekey=item:chest - 38 - abyssal plate|page=abyssal_Plate#Notes", "resolved"),
    ("ItemLink|stablekey=item:chest - 38 - abyssal plate|page=Abyssal plate", "resolved"),
    ("ItemLink|Priel Note|text=Editor label|image=Editor.webp", "shared"),
    ("AbilityLink|Flame Bolt|text=Editor label|image=Editor.webp", "ambiguous"),
    ("QuestLink|questlink=A Hermit's Request", "resolved"),
    ("QuestLink|link=|questlink=A Hermit's Request", "resolved"),
    ("ZoneLink|Blacksalt Strand", "resolved"),
    ("FactionLink|The Followers of Evil", "resolved"),
    ("ClassLink|Windblade", "resolved"),
)
KINDS = {
    "ItemLink": "item",
    "AbilityLink": "ability",
    "CharacterLink": "character",
    "QuestLink": "quest",
    "ZoneLink": "zone",
    "FactionLink": "faction",
    "ClassLink": "class",
}
TRACKING = {
    "Pages_with_unresolved_Erenshor_links": "missing_stable_key_data",
    "Pages_with_mismatched_Erenshor_link_targets": "stable_key_target_mismatch",
    "Pages_with_ambiguous_Erenshor_links": "ambiguous_manual_semantic_link",
}


def _parse(client: httpx.Client, text: str) -> dict[str, Any]:
    payload = client.post(
        API_URL,
        data={
            "action": "parse",
            "title": "Semantic Link Parity Probe",
            "text": text,
            "prop": "text|categories",
            "format": "json",
            "formatversion": 2,
        },
    ).json()
    assert "error" not in payload, payload
    assert "scribunto-error" not in payload["parse"]["text"], payload
    return payload["parse"]


def _json_result(parsed: dict[str, Any]) -> Any:
    match = re.search(r"<pre>(.*?)</pre>", parsed["text"], re.DOTALL)
    assert match is not None, parsed
    return json.loads(html.unescape(match[1]))


class _SemanticSpan(HTMLParser):
    def __init__(self, source: str) -> None:
        super().__init__()
        self.attributes: dict[str, str | None] = {}
        self.feed(source)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "span" and "data-erenshor-kind" in attributes:
            self.attributes = attributes


@pytest.fixture(scope="module")
def link_host() -> Iterator[tuple[httpx.Client, list[LinkCatalogEntry]]]:
    with httpx.Client(timeout=30) as client:
        try:
            client.get(API_URL, params={"action": "query", "format": "json"}).raise_for_status()
        except httpx.HTTPError:
            pytest.skip("Local MediaWiki is unavailable")
        records = _json_result(_parse(client, "{{#invoke:Erenshor/Link/testcases|catalog}}"))
        catalog = [
            LinkCatalogEntry(
                key=row["key"],
                kind=row["kind"],
                subtype=row.get("subtype"),
                name=row["name"],
                page=row["page"],
                image=row.get("image"),
            )
            for row in records
        ]
        assert any(row.key == "item:name-collision" for row in catalog), "Import current wiki fixtures first"
        yield client, catalog


@pytest.mark.parametrize(("call", "state"), CASES, ids=[call for call, _ in CASES])
def test_semantic_link_hosts_agree(
    link_host: tuple[httpx.Client, list[LinkCatalogEntry]], call: str, state: str
) -> None:
    client, catalog = link_host
    name, arguments = call.split("|", 1)
    kind = KINDS[name]
    source = "{{" + call + "}}"
    probe = "{{#invoke:Erenshor/Link/testcases|probe|kind=" + kind + "|" + arguments + "}}"
    observed = _json_result(_parse(client, probe))
    rendered = _parse(client, source)
    assert observed["state"] == state
    report = audit_links(generated_pages={"Probe": source}, catalog_entries=catalog, planned_titles=set())
    runtime_findings = {TRACKING[row["category"]] for row in rendered["categories"] if row["category"] in TRACKING}
    assert {finding.code for finding in report.findings} == runtime_findings
    span = _SemanticSpan(rendered["text"]).attributes
    assert span.get("data-erenshor-page") == observed.get("page")
    assert span.get("data-erenshor-key") == observed.get("resolvedKey", observed.get("requestedKey"))
    assert (
        LinkTargets(catalog).target(source)
        == re.sub(r"\s+", " ", observed["page"].replace("_", " ").strip()).casefold()
    )
    template = mwparserfromhell.parse(source).filter_templates()[0]
    if template.has("text"):
        assert observed["text"] == str(template.get("text").value)
    if template.has("image"):
        assert observed["image"] == str(template.get("image").value)
        assert "[[File:Editor.webp" in observed["rendered"]
