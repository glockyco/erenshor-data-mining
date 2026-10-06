"""Publishing plans every title against one listing and writes only what the plan allows."""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from erenshor.application.pictures import identify
from erenshor.application.services.image_publication import (
    Catalog,
    LivePictureCache,
    LiveWiki,
    Picture,
    PublishPlan,
    plan_publication,
    write_contact_sheets,
)
from erenshor.application.services.image_publication_run import RunRecord, execute, revert
from erenshor.infrastructure.wiki import MediaWikiEditError, MediaWikiUploadWarningError
from erenshor.infrastructure.wiki.client import (
    MediaWikiFile,
    MediaWikiFileVersion,
    MediaWikiPageRevision,
    MediaWikiPageSnapshot,
)

BOT = "WoWBot"
OPERATOR = "WoWMuch"
OWNERS = (BOT, OPERATOR)


def _png(color: tuple[int, int, int, int], size: tuple[int, int] = (16, 16), level: int = 6) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGBA", size, color).save(buffer, "PNG", compress_level=level)
    return buffer.getvalue()


def _sha1(data: bytes) -> str:
    return hashlib.sha1(data, usedforsecurity=False).hexdigest()


def _target(text: str) -> str | None:
    return text.removeprefix("#REDIRECT [[").removesuffix("]]") if text.startswith("#REDIRECT") else None


@dataclass
class _Version:
    data: bytes
    user: str
    comment: str


@dataclass
class FakeWiki:
    """Files with their versions and File pages, read, written, and deleted like the wiki's API."""

    files: dict[str, list[_Version]] = field(default_factory=dict)
    pages: dict[str, str] = field(default_factory=dict)
    revisions: dict[str, int] = field(default_factory=dict)
    archive: dict[str, tuple[list[_Version], str]] = field(default_factory=dict)
    used: set[str] = field(default_factory=set)
    warn: dict[str, dict[str, str]] = field(default_factory=dict)
    fail_after_uploads: int | None = None
    uploads: int = 0
    watched: tuple[str, ...] = ()
    dark: set[str] = field(default_factory=set)
    _stash: dict[str, tuple[str, bytes, str]] = field(default_factory=dict)

    # Arranging the wiki

    def put_file(self, title: str, data: bytes, user: str = BOT, comment: str = "Automated icon upload") -> None:
        self.files.setdefault(title, []).insert(0, _Version(data, user, comment))
        self._write_page(title, self.pages.get(title, "an old description"))

    def put_redirect(self, title: str, target: str) -> None:
        self._write_page(title, f"#REDIRECT [[{target}]]")

    def _write_page(self, title: str, text: str) -> None:
        self.pages[title] = text
        self.revisions[title] = self.revisions.get(title, 0) + 1

    def shows_a_picture(self, title: str) -> bool:
        """Whether a page that embeds the title shows a picture; MediaWiki follows one file redirect."""
        target = _target(self.pages.get(title, ""))
        return title in self.files or (target is not None and target in self.files)

    def _wrote(self) -> None:
        self.dark.update(title for title in self.watched if not self.shows_a_picture(title))

    # Reads

    def listing(self) -> LiveWiki:
        files = {}
        for title, versions in self.files.items():
            latest = versions[0]
            with Image.open(io.BytesIO(latest.data)) as image:
                width, height = image.size
            files[title] = MediaWikiFile(
                title,
                _sha1(latest.data),
                latest.user,
                latest.comment,
                len(latest.data),
                width,
                height,
                "t",
                f"u:{title}",
            )
        redirects = {
            title: target
            for title, text in self.pages.items()
            if title not in self.files and (target := _target(text)) is not None
        }
        return LiveWiki(files, redirects, frozenset(title for title in self.pages if title not in redirects))

    def download(self, url: str) -> bytes:
        return self.files[url.removeprefix("u:")][0].data

    def is_file_used(self, title: str) -> bool:
        return title in self.used

    def get_file_versions(self, title: str, limit: int = 50) -> tuple[MediaWikiFileVersion, ...]:
        versions = self.files.get(title, [])[:limit]
        return tuple(MediaWikiFileVersion(_sha1(v.data), v.user, v.comment, "t", f"u:{title}") for v in versions)

    def get_page_snapshots(self, titles: Any) -> dict[str, MediaWikiPageSnapshot]:
        snapshots = {}
        for title in titles:
            text = self.pages.get(title)
            revision = (
                MediaWikiPageRevision(title, 1, self.revisions[title], "t", "s", BOT) if text is not None else None
            )
            snapshots[title] = MediaWikiPageSnapshot(title, text, revision, "s")
        return snapshots

    # Writes of the bot

    def upload_file(
        self, file_path: str, filename: str, comment: str, text: str = "", ignore_warnings: bool = False
    ) -> dict[str, Any]:
        if self.fail_after_uploads is not None and self.uploads >= self.fail_after_uploads:
            raise KeyboardInterrupt
        title = f"File:{filename}"
        data = Path(file_path).read_bytes()
        warnings = dict(self.warn.get(title, {}))
        if title in self.files:
            warnings["exists"] = filename
            if any(_sha1(version.data) == _sha1(data) for version in self.files[title][1:]):
                warnings["duplicateversions"] = "an earlier version"
        if any(_sha1(v[0].data) == _sha1(data) for t, v in self.files.items() if t != title):
            warnings["duplicate"] = "another file"
        if warnings and not ignore_warnings:
            self._stash["key"] = (title, data, text)
            raise MediaWikiUploadWarningError(warnings, "key")
        self._store(title, data, comment, text)
        return {"result": "Success"}

    def confirm_upload(self, filekey: str, filename: str, comment: str, text: str = "") -> dict[str, Any]:
        title, data, stashed_text = self._stash.pop(filekey)
        assert title == f"File:{filename}"
        self._store(title, data, comment, stashed_text)
        return {"result": "Success"}

    def _store(self, title: str, data: bytes, comment: str, text: str) -> None:
        self.uploads += 1
        self.files.setdefault(title, []).insert(0, _Version(data, BOT, comment))
        if title not in self.pages:
            self._write_page(title, text)
        self._wrote()

    def safe_create_page(self, title: str, content: str, start_timestamp: str, summary: str | None = None) -> int:
        if title in self.pages:
            raise MediaWikiEditError(f"{title} exists")
        self._write_page(title, content)
        self._wrote()
        return self.revisions[title]

    def safe_edit_page(
        self, title: str, content: str, base_revision: MediaWikiPageRevision, summary: str | None = None
    ) -> int:
        if self.revisions.get(title) != base_revision.revision_id:
            raise MediaWikiEditError(f"{title} changed")
        self._write_page(title, content)
        self._wrote()
        return self.revisions[title]

    # Deletions of the administrator

    def delete_page(self, title: str, reason: str) -> None:
        self.archive[title] = (self.files.pop(title, []), self.pages.pop(title))
        self.revisions.pop(title)
        self._wrote()

    def undelete_page(self, title: str, reason: str) -> None:
        """Restore a deleted page; a newer page at the title keeps its text, as with MediaWiki's merge."""
        versions, text = self.archive.pop(title)
        if versions:
            self.files[title] = versions
        if title not in self.pages:
            self._write_page(title, text)


class _Catalog:
    """Pictures written to disk and the titles that name them."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.pictures: dict[str, Picture] = {}
        self.titles: dict[str, str] = {}
        self.entities: dict[str, str | None] = {}

    def add(self, data: bytes, *titles: str, kind: str = "item", source: str = "Assets/Texture2D/1_1.png") -> str:
        identity = identify(data)
        path = self.directory / f"{identity.pixel_hash}.png"
        self.directory.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        self.pictures[identity.pixel_hash] = Picture(
            identity.pixel_hash, "icon", identity.width, identity.height, _sha1(data), source, path
        )
        for title in titles:
            self.titles[title] = identity.pixel_hash
            self.entities[title] = f"{kind}:{title}"
        return identity.pixel_hash

    def build(self) -> Catalog:
        return Catalog("24405256", self.pictures, self.titles, self.entities)


def _plan(catalog: Catalog, wiki: FakeWiki, cache: LivePictureCache) -> PublishPlan:
    return plan_publication(catalog, wiki.listing(), BOT, OWNERS, cache, wiki.is_file_used)


def _run(catalog: Catalog, wiki: FakeWiki, cache: LivePictureCache, directory: Path) -> RunRecord:
    record = RunRecord(directory)
    execute(_plan(catalog, wiki, cache), catalog, wiki, wiki, record, "Publish")
    return record


@pytest.fixture
def setup(tmp_path: Path) -> tuple[_Catalog, FakeWiki, LivePictureCache, Path]:
    wiki = FakeWiki()
    return _Catalog(tmp_path / "catalog"), wiki, LivePictureCache(wiki.download, tmp_path / "live"), tmp_path


def _verdicts(plan: PublishPlan) -> dict[str, str]:
    return {item.title: item.verdict for item in plan.titles}


OLD = _png((10, 10, 10, 255), size=(150, 150))
SCROLL = _png((40, 200, 40, 255))


def test_a_game_update_that_changes_two_icons_plans_two_updates_and_shows_both(setup: Any) -> None:
    pictures, wiki, cache, tmp_path = setup
    pictures.add(_png((200, 0, 0, 255)), "File:Thorned Branch.png")
    pictures.add(_png((0, 200, 0, 255)), "File:Azure Willow Seed.png")
    same = _png((0, 0, 200, 255))
    pictures.add(same, "File:Copper Ore.png")
    wiki.put_file("File:Thorned Branch.png", OLD)
    wiki.put_file("File:Azure Willow Seed.png", OLD)
    wiki.put_file("File:Copper Ore.png", same)
    catalog = pictures.build()

    plan = _plan(catalog, wiki, cache)

    assert _verdicts(plan) == {
        "File:Thorned Branch.png": "update",
        "File:Azure Willow Seed.png": "update",
        "File:Copper Ore.png": "unchanged",
    }
    (sheet,) = write_contact_sheets(plan, catalog, wiki.listing(), cache, tmp_path / "run")
    with Image.open(sheet) as image:
        assert image.height == 24 + 2 * 80


def test_an_update_records_its_provenance_and_keeps_the_description(setup: Any) -> None:
    pictures, wiki, cache, tmp_path = setup
    image_hash = pictures.add(_png((200, 0, 0, 255)), "File:Thorned Branch.png", source="Assets/Texture2D/4_8.png")
    wiki.put_file("File:Thorned Branch.png", OLD)

    _run(pictures.build(), wiki, cache, tmp_path / "run")

    latest = wiki.files["File:Thorned Branch.png"][0]
    assert image_hash in latest.comment
    assert "Assets/Texture2D/4_8.png" in latest.comment
    assert "24405256" in latest.comment
    assert wiki.pages["File:Thorned Branch.png"] == "an old description"


def test_a_new_file_gets_a_description_with_the_games_copyright_notice(setup: Any) -> None:
    pictures, wiki, cache, tmp_path = setup
    pictures.add(_png((1, 2, 3, 255)), "File:Hotbar Frame.png")

    _run(pictures.build(), wiki, cache, tmp_path / "run")

    assert "{{License|Game}}" in wiki.pages["File:Hotbar Frame.png"]


def test_the_same_pixels_in_another_encoding_are_unchanged_and_downloaded_once(setup: Any) -> None:
    pictures, wiki, cache, _ = setup
    pictures.add(_png((5, 6, 7, 255), level=1), "File:Copper Ore.png")
    wiki.put_file("File:Copper Ore.png", _png((5, 6, 7, 255), level=9))
    catalog = pictures.build()

    assert _verdicts(_plan(catalog, wiki, cache)) == {"File:Copper Ore.png": "unchanged"}
    assert _verdicts(_plan(catalog, wiki, cache)) == {"File:Copper Ore.png": "unchanged"}
    assert cache.downloads == 1


def test_an_editors_newer_version_is_a_conflict_that_names_them_and_stays(setup: Any) -> None:
    pictures, wiki, cache, tmp_path = setup
    pictures.add(_png((200, 0, 0, 255)), "File:Thorned Branch.png")
    wiki.put_file("File:Thorned Branch.png", OLD)
    screenshot = _png((9, 9, 9, 255), size=(300, 300))
    wiki.put_file("File:Thorned Branch.png", screenshot, user="Ulor", comment="A better picture")
    catalog = pictures.build()

    plan = _plan(catalog, wiki, cache)
    execute(plan, catalog, wiki, wiki, RunRecord(tmp_path / "run"), "Publish")

    (item,) = plan.titles
    assert (item.verdict, item.reason) == ("conflict", "Ulor uploaded the file")
    assert wiki.files["File:Thorned Branch.png"][0].data == screenshot


def test_a_new_item_that_shares_a_picture_redirects_to_its_file_without_an_upload(setup: Any) -> None:
    pictures, wiki, cache, tmp_path = setup
    pictures.add(SCROLL, "File:Spell Scroll Aetherstorm.png", "File:Spell Scroll Brand New.png")
    wiki.put_file("File:Spell Scroll Aetherstorm.png", SCROLL)
    catalog = pictures.build()

    plan = _plan(catalog, wiki, cache)
    execute(plan, catalog, wiki, wiki, RunRecord(tmp_path / "run"), "Publish")

    assert _verdicts(plan)["File:Spell Scroll Brand New.png"] == "redirect"
    assert wiki.uploads == 0
    assert wiki.pages["File:Spell Scroll Brand New.png"] == "#REDIRECT [[File:Spell Scroll Aetherstorm.png]]"


def test_a_changed_shared_picture_is_one_new_version_that_every_title_shows(setup: Any) -> None:
    pictures, wiki, cache, tmp_path = setup
    titles = [f"File:Spell Scroll {name}.png" for name in ("Aetherstorm", "Burning Chains", "Dire Wolf")]
    pictures.add(SCROLL, *titles)
    wiki.put_file(titles[0], OLD)
    for title in titles[1:]:
        wiki.put_redirect(title, titles[0])
    catalog = pictures.build()

    plan = _plan(catalog, wiki, cache)
    execute(plan, catalog, wiki, wiki, RunRecord(tmp_path / "run"), "Publish")

    assert sorted(_verdicts(plan).values()) == ["unchanged", "unchanged", "update"]
    assert wiki.uploads == 1
    assert set(_verdicts(_plan(catalog, wiki, cache)).values()) == {"unchanged"}


def test_a_copy_of_the_old_pipeline_is_deleted_and_its_title_redirects(setup: Any) -> None:
    pictures, wiki, cache, tmp_path = setup
    pictures.add(SCROLL, "File:Spell Scroll Antidote.png", "File:Spell Scroll: Annihilate.png")
    wiki.put_file("File:Spell Scroll Antidote.png", SCROLL)
    wiki.put_file("File:Spell Scroll Annihilate.png", OLD, user=OPERATOR, comment="")
    wiki.put_redirect("File:Spell Scroll: Annihilate.png", "File:Spell Scroll Annihilate.png")
    catalog = pictures.build()

    plan = _plan(catalog, wiki, cache)
    execute(plan, catalog, wiki, wiki, RunRecord(tmp_path / "run"), "Publish")

    assert _verdicts(plan) == {
        "File:Spell Scroll Antidote.png": "unchanged",
        "File:Spell Scroll Annihilate.png": "retire",
        "File:Spell Scroll: Annihilate.png": "redirect",
    }
    assert wiki.archive["File:Spell Scroll Annihilate.png"][0][0].data == OLD
    for title in ("File:Spell Scroll Annihilate.png", "File:Spell Scroll: Annihilate.png"):
        assert wiki.pages[title] == "#REDIRECT [[File:Spell Scroll Antidote.png]]"
    assert set(_verdicts(_plan(catalog, wiki, cache)).values()) == {"unchanged"}


def test_a_redirect_outside_the_catalog_that_names_a_deleted_copy_points_at_the_file(setup: Any) -> None:
    pictures, wiki, cache, tmp_path = setup
    pictures.add(SCROLL, "File:Spell Scroll Antidote.png", "File:Royal Carapace.png")
    wiki.put_file("File:Spell Scroll Antidote.png", SCROLL)
    wiki.put_file("File:Royal Carapace.png", OLD)
    wiki.put_redirect("File:RoyalCarapace.png", "File:Royal Carapace.png")
    wiki.watched = ("File:RoyalCarapace.png",)

    _run(pictures.build(), wiki, cache, tmp_path / "run")

    assert wiki.pages["File:RoyalCarapace.png"] == "#REDIRECT [[File:Spell Scroll Antidote.png]]"
    assert wiki.dark == set()


def test_the_bots_orphans_go_with_their_redirects_and_the_operators_unused_files_stay(setup: Any) -> None:
    pictures, wiki, cache, tmp_path = setup
    pictures.add(_png((1, 1, 1, 255)), "File:Spell Scroll Aetherstorm.png")
    wiki.put_file("File:Spell Scroll- Aetherstorm.png", OLD)
    wiki.put_redirect("File:Spell Scroll-: Aetherstorm.png", "File:Spell Scroll- Aetherstorm.png")
    wiki.put_file("File:Charms.png", OLD)
    wiki.used.add("File:Charms.png")
    wiki.put_file("File:Raids.png", _png((2, 2, 2, 255), size=(512, 512)), user=OPERATOR, comment="")
    wiki.put_file("File:An Editors Screenshot.png", OLD, user="Ulor")
    catalog = pictures.build()

    plan = _plan(catalog, wiki, cache)
    execute(plan, catalog, wiki, wiki, RunRecord(tmp_path / "run"), "Publish")

    assert [(orphan.title, orphan.redirects) for orphan in plan.orphans] == [
        ("File:Spell Scroll- Aetherstorm.png", ("File:Spell Scroll-: Aetherstorm.png",))
    ]
    assert plan.unused == ("File:Raids.png",)
    assert set(wiki.archive) == {"File:Spell Scroll- Aetherstorm.png", "File:Spell Scroll-: Aetherstorm.png"}
    assert {"File:Charms.png", "File:Raids.png", "File:An Editors Screenshot.png"} <= set(wiki.files)


def test_an_orphan_that_a_page_starts_to_show_before_the_run_stays(setup: Any) -> None:
    pictures, wiki, cache, tmp_path = setup
    pictures.add(_png((1, 1, 1, 255)), "File:Spell Scroll Aetherstorm.png")
    wiki.put_file("File:Spell Scroll- Aetherstorm.png", OLD)
    catalog = pictures.build()
    plan = _plan(catalog, wiki, cache)
    wiki.used.add("File:Spell Scroll- Aetherstorm.png")
    record = RunRecord(tmp_path / "run")

    execute(plan, catalog, wiki, wiki, record, "Publish")

    assert "File:Spell Scroll- Aetherstorm.png" in wiki.files
    assert record.entries[-1]["reason"] == "a page shows the file since the plan"


def test_a_plan_that_deletes_refuses_to_run_without_the_deletion_account(setup: Any) -> None:
    pictures, wiki, cache, tmp_path = setup
    pictures.add(_png((1, 1, 1, 255)), "File:Spell Scroll Aetherstorm.png")
    wiki.put_file("File:Spell Scroll- Aetherstorm.png", OLD)
    catalog = pictures.build()

    with pytest.raises(ValueError, match="needs the deletion account"):
        execute(_plan(catalog, wiki, cache), catalog, wiki, None, RunRecord(tmp_path / "run"), "Publish")

    assert wiki.uploads == 0


def test_a_title_with_a_colon_uploads_without_it_and_redirects(setup: Any) -> None:
    pictures, wiki, cache, tmp_path = setup
    pictures.add(_png((7, 7, 7, 255)), "File:Summoned: Brute.png", kind="character")

    _run(pictures.build(), wiki, cache, tmp_path / "run")

    assert "File:Summoned Brute.png" in wiki.files
    assert wiki.pages["File:Summoned: Brute.png"] == "#REDIRECT [[File:Summoned Brute.png]]"


def test_titles_that_redirect_to_an_editors_file_with_the_picture_stay(setup: Any) -> None:
    pictures, wiki, cache, _ = setup
    brute = _png((7, 7, 7, 255))
    pictures.add(brute, "File:Summoned: Brute.png", kind="character")
    wiki.put_file("File:Brute.png", brute, user="Snedn")
    wiki.put_redirect("File:Summoned: Brute.png", "File:Brute.png")

    plan = _plan(pictures.build(), wiki, cache)

    assert set(_verdicts(plan).values()) == {"unchanged"}


def test_an_interrupted_run_leaves_only_the_rest_to_the_next_plan(setup: Any) -> None:
    pictures, wiki, cache, tmp_path = setup
    pictures.add(_png((200, 0, 0, 255)), "File:Thorned Branch.png")
    pictures.add(_png((0, 200, 0, 255)), "File:Azure Willow Seed.png")
    wiki.put_file("File:Thorned Branch.png", OLD)
    wiki.put_file("File:Azure Willow Seed.png", OLD)
    catalog = pictures.build()
    wiki.fail_after_uploads = 1

    with pytest.raises(KeyboardInterrupt):
        _run(catalog, wiki, cache, tmp_path / "run")

    assert sorted(_verdicts(_plan(catalog, wiki, cache)).values()) == ["unchanged", "update"]
    assert cache.downloads == 0


def test_a_title_that_changed_after_the_plan_is_skipped(setup: Any) -> None:
    pictures, wiki, cache, tmp_path = setup
    pictures.add(_png((200, 0, 0, 255)), "File:Thorned Branch.png")
    wiki.put_file("File:Thorned Branch.png", OLD)
    catalog = pictures.build()
    plan = _plan(catalog, wiki, cache)
    screenshot = _png((9, 9, 9, 255), size=(300, 300))
    wiki.put_file("File:Thorned Branch.png", screenshot, user="Ulor")
    record = RunRecord(tmp_path / "run")

    execute(plan, catalog, wiki, wiki, record, "Publish")

    assert wiki.files["File:Thorned Branch.png"][0].data == screenshot
    assert record.entries == [
        {
            "title": "File:Thorned Branch.png",
            "action": "update",
            "done": False,
            "reason": "the file changed since the plan, now uploaded by Ulor",
        }
    ]


def test_an_unexpected_upload_warning_skips_the_upload(setup: Any) -> None:
    pictures, wiki, cache, tmp_path = setup
    pictures.add(_png((200, 0, 0, 255)), "File:Thorned Branch.png")
    wiki.put_file("File:Thorned Branch.png", OLD)
    wiki.warn["File:Thorned Branch.png"] = {"duplicate-archive": "Thorned Branch (old).png"}

    record = _run(pictures.build(), wiki, cache, tmp_path / "run")

    assert wiki.files["File:Thorned Branch.png"][0].data == OLD
    assert record.entries[0]["reason"] == "MediaWiki warned: duplicate-archive, exists"


def test_a_title_with_a_colon_shows_a_picture_throughout_the_deletion_of_its_copy(setup: Any) -> None:
    pictures, wiki, cache, tmp_path = setup
    pictures.add(SCROLL, "File:Spell Scroll Antidote.png", "File:Spell Scroll: Annihilate.png")
    wiki.put_file("File:Spell Scroll Antidote.png", SCROLL)
    wiki.put_file("File:Spell Scroll Annihilate.png", OLD)
    wiki.put_redirect("File:Spell Scroll: Annihilate.png", "File:Spell Scroll Annihilate.png")
    wiki.watched = ("File:Spell Scroll Antidote.png", "File:Spell Scroll: Annihilate.png")

    _run(pictures.build(), wiki, cache, tmp_path / "run")

    assert wiki.dark == set()


def test_a_title_that_redirects_through_another_redirect_is_pointed_at_the_file(setup: Any) -> None:
    pictures, wiki, cache, tmp_path = setup
    pictures.add(SCROLL, "File:Spell Scroll Antidote.png", "File:Spell Scroll: Antidote.png")
    wiki.put_file("File:Spell Scroll Antidote.png", SCROLL)
    wiki.put_redirect("File:Spell Scroll Antidote (old).png", "File:Spell Scroll Antidote.png")
    wiki.put_redirect("File:Spell Scroll: Antidote.png", "File:Spell Scroll Antidote (old).png")
    catalog = pictures.build()

    plan = _plan(catalog, wiki, cache)
    execute(plan, catalog, wiki, wiki, RunRecord(tmp_path / "run"), "Publish")

    assert _verdicts(plan)["File:Spell Scroll: Antidote.png"] == "redirect"
    assert wiki.shows_a_picture("File:Spell Scroll: Antidote.png")


def test_a_revert_restores_replaced_bytes_deleted_copies_orphans_and_redirects(setup: Any) -> None:
    pictures, wiki, cache, tmp_path = setup
    pictures.add(_png((200, 0, 0, 255)), "File:Thorned Branch.png")
    pictures.add(SCROLL, "File:Spell Scroll Antidote.png", "File:Spell Scroll: Annihilate.png")
    wiki.put_file("File:Thorned Branch.png", OLD)
    wiki.put_file("File:Spell Scroll Antidote.png", SCROLL)
    old_copy = _png((3, 3, 3, 255), size=(150, 150))
    wiki.put_file("File:Spell Scroll Annihilate.png", old_copy)
    wiki.put_redirect("File:Spell Scroll: Annihilate.png", "File:Spell Scroll Annihilate.png")
    wiki.put_file("File:Spell Scroll- Aetherstorm.png", OLD)
    run = _run(pictures.build(), wiki, cache, tmp_path / "run")

    revert(RunRecord.load(run.directory), wiki, wiki, RunRecord(tmp_path / "revert"), OWNERS, "Revert")

    assert wiki.files["File:Thorned Branch.png"][0].data == OLD
    assert wiki.files["File:Spell Scroll Annihilate.png"][0].data == old_copy
    assert wiki.pages["File:Spell Scroll Annihilate.png"] == "an old description"
    assert wiki.pages["File:Spell Scroll: Annihilate.png"] == "#REDIRECT [[File:Spell Scroll Annihilate.png]]"
    assert wiki.shows_a_picture("File:Spell Scroll: Annihilate.png")
    assert "File:Spell Scroll- Aetherstorm.png" in wiki.files
