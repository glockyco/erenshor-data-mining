"""Publishing plans every title against one listing and writes only what the plan allows."""

from __future__ import annotations

import hashlib
import io
import os
import stat
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

import httpx
import pytest
from PIL import Image
from tests.fakes.mediawiki import MediaWikiFake, PurgeRequest

from erenshor.application.pictures import identify
from erenshor.application.services import image_publication_run
from erenshor.application.services.image_publication import (
    Catalog,
    LivePictureCache,
    LiveWiki,
    Orphan,
    Picture,
    PlannedTitle,
    PublishPlan,
    plan_publication,
    write_contact_sheets,
)
from erenshor.application.services.image_publication_run import RunRecord, description, execute, revert
from erenshor.infrastructure.time import MockClock
from erenshor.infrastructure.wiki import (
    MediaWikiAPIError,
    MediaWikiEditVerificationError,
    MediaWikiNetworkError,
)
from erenshor.infrastructure.wiki.client import (
    MediaWikiClient,
    MediaWikiFile,
    MediaWikiPageRevision,
)
from erenshor.infrastructure.wiki.content import normalize_saved_text
from erenshor.infrastructure.wiki.rate_limit import MediaWikiRequestPolicy

BOT = "WoWBot"
OPERATOR = "WoWMuch"
OWNERS = (BOT, OPERATOR)


def _png(color: tuple[int, int, int, int], size: tuple[int, int] = (16, 16), level: int = 6) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGBA", size, color).save(buffer, "PNG", compress_level=level)
    return buffer.getvalue()


def _sha1(data: bytes) -> str:
    return hashlib.sha1(data, usedforsecurity=False).hexdigest()


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


def _plan(catalog: Catalog, wiki: MediaWikiFake, cache: LivePictureCache) -> PublishPlan:
    return plan_publication(catalog, wiki.listing(), BOT, OWNERS, cache, wiki.is_file_used)


def _run(catalog: Catalog, wiki: MediaWikiFake, cache: LivePictureCache, directory: Path) -> RunRecord:
    record = RunRecord(directory)
    execute(_plan(catalog, wiki, cache), catalog, wiki, wiki, record, "Publish")
    return record


@pytest.fixture
def setup(tmp_path: Path) -> tuple[_Catalog, MediaWikiFake, LivePictureCache, Path]:
    wiki = MediaWikiFake(edit_account=BOT)
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


def test_a_live_picture_whose_bytes_do_not_match_its_listed_sha1_draws_as_unreadable(setup: Any) -> None:
    """wiki.gg's CDN has served a title's old or wrong bytes under its current, versioned URL (observed
    2026-10-08); one such title must not stop the sheet from showing the rest."""
    pictures, wiki, cache, tmp_path = setup
    pictures.add(_png((200, 0, 0, 255)), "File:Thorned Branch.png")
    pictures.add(_png((0, 200, 0, 255)), "File:Azure Willow Seed.png")
    wiki.put_file("File:Thorned Branch.png", OLD)
    wiki.put_file("File:Azure Willow Seed.png", OLD)
    catalog = pictures.build()
    plan = _plan(catalog, wiki, cache)
    real_download = wiki.download
    wiki.download = lambda url: SCROLL if url == "u:File:Thorned Branch.png" else real_download(url)  # type: ignore[method-assign]

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
    assert wiki.purged == [PurgeRequest(("File:Thorned Branch.png",), False, None, None)]


def test_a_new_file_gets_a_description_with_the_games_copyright_notice(setup: Any) -> None:
    pictures, wiki, cache, tmp_path = setup
    pictures.add(_png((1, 2, 3, 255)), "File:Hotbar Frame.png")

    _run(pictures.build(), wiki, cache, tmp_path / "run")

    assert "{{License|Game}}" in wiki.pages["File:Hotbar Frame.png"]


@pytest.mark.parametrize(
    ("entity_key", "title", "shows"),
    [
        ("item:bow - 10 - molorai bow", "File:Molorai Bow render.png", "the item by itself"),
        (
            "item:foot - 12 - wolfhide boots",
            "File:Wolfhide Boots render (female).png",
            "the item by itself, as the female body wears it",
        ),
        ("character:faith", "File:Faith render.png", "the character"),
    ],
)
def test_a_render_description_says_what_it_shows(entity_key: str, title: str, shows: str) -> None:
    render = Picture("hash", "render", 1024, 1024, "sha1", "capture.png", Path("x.png"), "item-1", "24405256")

    text = description(render, "24405256", entity_key, title)

    assert f"Rendered from the game's model of {shows} (game build 24405256, capture preset item-1)" in text


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
    pictures.add(SCROLL, "File:Spell Scroll Antidote.png", "File:Spell Scroll Annihilate.png")
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


@pytest.mark.parametrize("change", ["delete", "move"])
def test_a_plan_that_moves_or_deletes_refuses_to_run_without_the_administrator_account(setup: Any, change: str) -> None:
    pictures, wiki, cache, tmp_path = setup
    if change == "delete":
        pictures.add(_png((1, 1, 1, 255)), "File:Spell Scroll Aetherstorm.png")
        wiki.put_file("File:Spell Scroll- Aetherstorm.png", OLD)
    else:
        _antidote(pictures, wiki)
    catalog = pictures.build()

    with pytest.raises(ValueError, match="needs the administrator account"):
        execute(_plan(catalog, wiki, cache), catalog, wiki, None, RunRecord(tmp_path / "run"), "Publish")

    assert (wiki.uploads, wiki.archive) == (0, {})


def test_titles_that_redirect_to_an_editors_file_with_the_picture_stay(setup: Any) -> None:
    pictures, wiki, cache, _ = setup
    brute = _png((7, 7, 7, 255))
    pictures.add(brute, "File:Summoned Brute render.png", kind="character")
    wiki.put_file("File:Brute.png", brute, user="Snedn")
    wiki.put_redirect("File:Summoned Brute render.png", "File:Brute.png")

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


def test_an_old_title_shows_a_picture_throughout_the_deletion_of_its_copy(setup: Any) -> None:
    pictures, wiki, cache, tmp_path = setup
    pictures.add(SCROLL, "File:Spell Scroll Antidote.png", "File:Spell Scroll Annihilate.png")
    wiki.put_file("File:Spell Scroll Antidote.png", SCROLL)
    wiki.put_file("File:Spell Scroll Annihilate.png", OLD)
    wiki.put_redirect("File:Spell Scroll: Annihilate.png", "File:Spell Scroll Annihilate.png")
    wiki.watched = ("File:Spell Scroll Antidote.png", "File:Spell Scroll: Annihilate.png")

    _run(pictures.build(), wiki, cache, tmp_path / "run")

    assert wiki.dark == set()


def test_a_title_that_redirects_through_another_redirect_is_pointed_at_the_file(setup: Any) -> None:
    pictures, wiki, cache, tmp_path = setup
    pictures.add(SCROLL, "File:Spell Scroll Antidote.png", "File:Antidote Scroll.png")
    wiki.put_file("File:Spell Scroll Antidote.png", SCROLL)
    wiki.put_redirect("File:Spell Scroll Antidote (old).png", "File:Spell Scroll Antidote.png")
    wiki.put_redirect("File:Antidote Scroll.png", "File:Spell Scroll Antidote (old).png")
    catalog = pictures.build()

    plan = _plan(catalog, wiki, cache)
    execute(plan, catalog, wiki, wiki, RunRecord(tmp_path / "run"), "Publish")

    assert _verdicts(plan)["File:Antidote Scroll.png"] == "redirect"
    assert wiki.shows_a_picture("File:Antidote Scroll.png")


def test_a_revert_restores_replaced_bytes_deleted_copies_orphans_and_redirects(setup: Any) -> None:
    pictures, wiki, cache, tmp_path = setup
    pictures.add(_png((200, 0, 0, 255)), "File:Thorned Branch.png")
    pictures.add(SCROLL, "File:Spell Scroll Antidote.png", "File:Spell Scroll Annihilate.png")
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


def test_a_file_whose_description_page_redirects_gets_its_description(setup: Any) -> None:
    pictures, wiki, cache, tmp_path = setup
    pictures.add(SCROLL, "File:A Collection of Notes.png")
    wiki.put_file("File:A collection of notes.png", OLD, user=OPERATOR, comment="")
    wiki.put_file("File:A Collection of Notes.png", SCROLL, user=BOT, comment="Game picture")
    wiki.put_redirect("File:A Collection of Notes.png", "File:A collection of notes.png")
    catalog = pictures.build()

    plan = _plan(catalog, wiki, cache)
    run = RunRecord(tmp_path / "run")
    execute(plan, catalog, wiki, wiki, run, "Publish")

    assert _verdicts(plan)["File:A Collection of Notes.png"] == "describe"
    assert "{{License|Game}}" in wiki.pages["File:A Collection of Notes.png"]
    assert _verdicts(_plan(catalog, wiki, cache))["File:A Collection of Notes.png"] == "unchanged"
    revert(RunRecord.load(run.directory), wiki, wiki, RunRecord(tmp_path / "revert"), OWNERS, "Revert")
    assert wiki.pages["File:A Collection of Notes.png"] == "#REDIRECT [[File:A collection of notes.png]]"


def test_a_copy_that_hides_its_redirect_to_a_planned_title_is_deleted(setup: Any) -> None:
    pictures, wiki, cache, tmp_path = setup
    medal = _png((30, 60, 200, 255))
    pictures.add(medal, "File:Azure Loyalty Medal.png")
    wiki.put_file("File:Azure Loyalty Medal.png", medal)
    wiki.put_file("File:Azure Loyalty Medal .png", OLD)
    wiki.put_redirect("File:Azure Loyalty Medal .png", "File:Azure Loyalty Medal.png")
    wiki.used.add("File:Azure Loyalty Medal .png")

    plan = _plan(pictures.build(), wiki, cache)
    execute(plan, pictures.build(), wiki, wiki, RunRecord(tmp_path / "run"), "Publish")

    assert _verdicts(plan)["File:Azure Loyalty Medal .png"] == "retire"
    assert "File:Azure Loyalty Medal .png" not in wiki.files
    assert wiki.shows_a_picture("File:Azure Loyalty Medal .png")


def test_a_title_shows_the_file_that_its_redirect_names() -> None:
    # An old title redirects to the file that took its place.
    file = MediaWikiFile("File:Summoned Treant.png", "s", "WoWBot", "", 1, 1, 1, "t", "u")
    live = LiveWiki({file.title: file}, {"File:Summoned: Treant.png": file.title}, frozenset())

    assert live.shown("File:Summoned: Treant.png") is file
    assert live.shown("File:Faith.png") is None


def _antidote(pictures: _Catalog, wiki: MediaWikiFake) -> None:
    """A spell's file at its plain title, with an item's old title redirecting to it, and the two role titles."""
    pictures.add(SCROLL, "File:Spell Scroll Antidote icon.png", kind="item")
    pictures.add(SCROLL, "File:Antidote icon.png", kind="spell")
    wiki.put_file("File:Antidote.png", _png((40, 200, 40, 128)))
    wiki.put_file("File:Antidote.png", SCROLL)
    wiki.put_redirect("File:Spell Scroll Antidote.png", "File:Antidote.png")


def test_a_file_whose_title_changes_moves_with_its_history_and_its_redirects_follow(setup: Any) -> None:
    pictures, wiki, cache, tmp_path = setup
    _antidote(pictures, wiki)
    wiki.watched = ("File:Antidote.png",)
    catalog = pictures.build()

    plan = _plan(catalog, wiki, cache)
    execute(plan, catalog, wiki, wiki, RunRecord(tmp_path / "run"), "Publish")

    assert _verdicts(plan) == {
        "File:Antidote icon.png": "move",
        "File:Spell Scroll Antidote icon.png": "redirect",
        "File:Spell Scroll Antidote.png": "redirect",
    }
    assert (plan.orphans, wiki.uploads) == ((), 0)
    assert len(wiki.files["File:Antidote icon.png"]) == 2
    for title in ("File:Antidote.png", "File:Spell Scroll Antidote.png", "File:Spell Scroll Antidote icon.png"):
        assert wiki.pages[title] == "#REDIRECT [[File:Antidote icon.png]]"
    assert wiki.purged == [PurgeRequest(("File:Antidote icon.png", "File:Antidote.png"), False, None, None)]
    assert wiki.dark == set()
    assert set(_verdicts(_plan(catalog, wiki, cache)).values()) == {"unchanged"}


def test_the_file_that_most_redirects_name_moves_and_another_copy_goes(setup: Any) -> None:
    pictures, wiki, cache, tmp_path = setup
    _antidote(pictures, wiki)
    wiki.put_file("File:Antidote (copy).png", SCROLL)
    catalog = pictures.build()

    plan = _plan(catalog, wiki, cache)
    execute(plan, catalog, wiki, wiki, RunRecord(tmp_path / "run"), "Publish")

    assert [item.source for item in plan.titles if item.verdict == "move"] == ["File:Antidote.png"]
    assert [orphan.title for orphan in plan.orphans] == ["File:Antidote (copy).png"]
    assert "File:Antidote (copy).png" in wiki.archive


def test_an_editors_file_that_holds_the_picture_is_never_moved(setup: Any) -> None:
    pictures, wiki, cache, _ = setup
    faith = _png((250, 200, 250, 255))
    pictures.add(faith, "File:Faith render.png", kind="character")
    wiki.put_file("File:Faith.png", faith, user="Ulor", comment="")

    assert _verdicts(_plan(pictures.build(), wiki, cache)) == {"File:Faith render.png": "create"}


def test_a_reverted_move_puts_the_file_back_without_a_redirect_and_restores_its_redirects(setup: Any) -> None:
    pictures, wiki, cache, tmp_path = setup
    _antidote(pictures, wiki)
    run = _run(pictures.build(), wiki, cache, tmp_path / "run")

    revert(RunRecord.load(run.directory), wiki, wiki, RunRecord(tmp_path / "revert"), OWNERS, "Revert")

    assert len(wiki.files["File:Antidote.png"]) == 2
    assert "File:Antidote icon.png" not in wiki.pages
    assert wiki.pages["File:Spell Scroll Antidote.png"] == "#REDIRECT [[File:Antidote.png]]"
    assert wiki.shows_a_picture("File:Spell Scroll Antidote.png")


def test_a_move_whose_answer_was_lost_counts_when_the_file_arrived(setup: Any) -> None:
    pictures, wiki, cache, tmp_path = setup
    _antidote(pictures, wiki)
    wiki.lose_move_answers = True
    catalog = pictures.build()

    plan = _plan(catalog, wiki, cache)
    record = RunRecord(tmp_path / "run")
    execute(plan, catalog, wiki, wiki, record, "Publish")

    assert [
        (entry["action"], entry["done"]) for entry in record.entries if entry["title"] == "File:Antidote icon.png"
    ] == [("move", True)]
    assert wiki.pages["File:Spell Scroll Antidote.png"] == "#REDIRECT [[File:Antidote icon.png]]"


def test_a_failed_purge_does_not_undo_an_upload(setup: Any) -> None:
    """The wiki's own CDN cache sometimes keeps stale bytes under a correct, versioned URL after a write
    (observed on 2026-10-08), so every write purges its title; a purge failure must not undo the write."""
    pictures, wiki, cache, tmp_path = setup
    pictures.add(_png((200, 0, 0, 255)), "File:Thorned Branch.png")

    def failing_purge(titles: Any, force_link_update: bool = True) -> tuple[str, ...]:
        raise MediaWikiAPIError("purge rate-limited")

    wiki.purge_pages = failing_purge  # type: ignore[method-assign]
    record = _run(pictures.build(), wiki, cache, tmp_path / "run")

    assert [(entry["action"], entry["done"]) for entry in record.entries] == [("create", True)]
    assert "File:Thorned Branch.png" in wiki.files


def _fail_image_edit_verification(
    wiki: MediaWikiFake,
    monkeypatch: pytest.MonkeyPatch,
    *,
    parent_known: bool = True,
    written_known: bool = True,
) -> list[MediaWikiEditVerificationError]:
    """A native edit can merge over an editor's newer revision before verification rejects it."""
    errors: list[MediaWikiEditVerificationError] = []

    def edit(title: str, content: str, base_revision: MediaWikiPageRevision, summary: str | None = None) -> int:
        wiki.put_page(title, "editor's actual preimage", user="Editor")
        parent = wiki.get_page_snapshots([title])[title]
        wiki.put_page(title, content, user=BOT)
        written = wiki.get_page_snapshots([title])[title]
        assert written.revision is not None
        error = MediaWikiEditVerificationError(
            "native edit used an unexpected parent",
            new_revision_id=written.revision.revision_id,
            written_snapshot=written if written_known else None,
            actual_parent_snapshot=parent if parent_known else None,
        )
        errors.append(error)
        raise error

    monkeypatch.setattr(wiki, "safe_edit_page", edit)
    return errors


@pytest.mark.parametrize("action", ["describe", "redirect", "revert redirect", "revert describe", "revert retire"])
def test_image_edit_mismatch_retains_ack_parent_and_reviewed_preimage(
    setup: Any, monkeypatch: pytest.MonkeyPatch, action: str
) -> None:
    pictures, wiki, _, tmp_path = setup
    title = "File:Notes.png"
    target = "File:Old Notes.png"
    wiki.put_redirect(title, target)
    reviewed = wiki.get_page_snapshots([title])[title]
    errors = _fail_image_edit_verification(wiki, monkeypatch)
    record = RunRecord(tmp_path / "run")
    original_text = reviewed.source_text

    with pytest.raises(MediaWikiEditVerificationError) as caught:
        if action == "redirect":
            image_publication_run.redirect(title, "File:New Notes.png", target, wiki, record, "Publish")
        elif action == "describe":
            image_hash = pictures.add(SCROLL, title)
            image_publication_run._describe(
                PlannedTitle(title, "describe", image_hash, title, "", redirect_target=target),
                pictures.build(),
                wiki,
                record,
                "Publish",
            )
        elif action == "revert redirect":
            image_publication_run._restore_redirect(
                {"title": title, "target": target, "old_text": "reviewed old redirect", "api_url": wiki.api_url},
                wiki,
                record,
                "Revert",
            )
        elif action == "revert describe":
            image_publication_run._restore_description(
                {
                    "title": title,
                    "text": original_text,
                    "old_text": "reviewed old description",
                    "api_url": wiki.api_url,
                },
                wiki,
                record,
                "Revert",
            )
        else:
            wiki.put_file(title, OLD)
            wiki.delete_page(title, "fixture")
            wiki.put_redirect(title, target)
            image_publication_run._restore_copy(
                {"title": title, "file": target, "description": "reviewed deleted description"},
                wiki,
                wiki,
                record,
                "Revert",
            )

    assert caught.value is errors[0]
    (entry,) = RunRecord.load(record.directory).entries
    assert entry["done"] is True
    assert entry["verified"] is False
    assert entry["requires_rollback"] is True
    assert entry["revision"] == errors[0].new_revision_id == wiki.revisions[title]
    assert entry["old_text"] == original_text
    assert entry["reviewed_snapshot"]["source_text"] == original_text
    assert entry["actual_parent_snapshot"]["source_text"] == "editor's actual preimage"
    assert entry["actual_parent_snapshot"]["content_model"] == "wikitext"
    assert entry["actual_parent_snapshot"]["revision"]["user"] == "Editor"
    assert (
        entry["written_snapshot"]["revision"]["parent_revision_id"]
        == (entry["actual_parent_snapshot"]["revision"]["revision_id"])
    )
    assert entry["reason"] == str(errors[0])
    if action == "revert retire":
        assert entry["undeleted"] is True
        assert title in wiki.files


@pytest.mark.parametrize("proof", ["complete", "unknown parent", "unknown written", "model changed", "later revision"])
def test_reviewed_image_recovery_restores_actual_parent_or_refuses(
    setup: Any, monkeypatch: pytest.MonkeyPatch, proof: str
) -> None:
    _, wiki, _, tmp_path = setup
    title = "File:Notes.png"
    wiki.put_redirect(title, "File:Old.png")
    errors = _fail_image_edit_verification(
        wiki, monkeypatch, parent_known=proof != "unknown parent", written_known=proof != "unknown written"
    )
    run = RunRecord(tmp_path / "run")
    with pytest.raises(MediaWikiEditVerificationError):
        image_publication_run.redirect(title, "File:New.png", "File:Old.png", wiki, run, "Publish")
    monkeypatch.undo()
    saved = RunRecord.load(run.directory)
    if proof == "model changed":
        saved.entries[0]["actual_parent_snapshot"]["content_model"] = "javascript"
    elif proof == "later revision":
        wiki.put_page(title, wiki.pages[title], user=BOT)
    before = wiki.revisions[title]
    recovery = RunRecord(tmp_path / "recovery")

    revert(saved, wiki, None, recovery, OWNERS, "Reviewed recovery")

    assert len(errors) == 1
    (entry,) = recovery.entries
    if proof == "complete":
        assert entry["done"] is True
        assert wiki.pages[title] == "editor's actual preimage"
        assert wiki.revisions[title] != before
    else:
        assert entry["done"] is False
        assert wiki.pages[title] == "#REDIRECT [[File:New.png]]"
        assert wiki.revisions[title] == before


def test_image_verification_failure_stops_dependencies_and_retains_confirmed_upload(
    setup: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    pictures, wiki, cache, tmp_path = setup
    title = "File:A Collection of Notes.png"
    pictures.add(SCROLL, title)
    wiki.put_file(title, OLD)
    wiki.put_redirect(title, "File:A collection of notes.png")
    wiki.put_file("File:Orphan.png", OLD)
    catalog = pictures.build()
    plan = _plan(catalog, wiki, cache)
    assert _verdicts(plan)[title] == "update"
    assert plan.orphans
    errors = _fail_image_edit_verification(wiki, monkeypatch)
    record = RunRecord(tmp_path / "run")

    with pytest.raises(MediaWikiEditVerificationError) as caught:
        execute(plan, catalog, wiki, wiki, record, "Publish")

    assert caught.value is errors[0]
    assert [entry["action"] for entry in record.entries] == ["update", "describe"]
    assert wiki.uploads == 1
    assert "File:Orphan.png" in wiki.files
    assert (record.directory / record.entries[0]["replaced"]).read_bytes() == OLD
    assert RunRecord.load(record.directory).entries == record.entries


def test_image_ack_survives_missing_evidence_and_ledger_io_failure(setup: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    _, wiki, _, tmp_path = setup
    title = "File:Notes.png"
    wiki.put_redirect(title, "File:Old.png")
    errors = _fail_image_edit_verification(wiki, monkeypatch, parent_known=False, written_known=False)
    record = RunRecord(tmp_path / "run")
    durable_write = image_publication_run.durable_write_text
    checkpoints = 0

    def fail_ledger(path: Path, text: str) -> None:
        nonlocal checkpoints
        checkpoints += 1
        if checkpoints > 1:
            raise OSError("ledger disk unavailable")
        durable_write(path, text)

    monkeypatch.setattr(image_publication_run, "durable_write_text", fail_ledger)
    with pytest.raises(MediaWikiEditVerificationError) as caught:
        image_publication_run.redirect(title, "File:New.png", "File:Old.png", wiki, record, "Publish")

    assert caught.value is errors[0]
    (entry,) = record.entries
    assert entry["revision"] == wiki.revisions[title] == errors[0].new_revision_id
    assert entry["written_snapshot"] is None
    assert entry["actual_parent_snapshot"] is None
    assert entry["done"] is True
    assert "ledger disk unavailable" in caught.value.__notes__[0]


def test_image_recovery_verification_failure_retains_its_own_ack_and_stops(
    setup: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, wiki, _, tmp_path = setup
    title = "File:Notes.png"
    wiki.put_redirect(title, "File:Old.png")
    errors = _fail_image_edit_verification(wiki, monkeypatch)
    run = RunRecord(tmp_path / "run")
    with pytest.raises(MediaWikiEditVerificationError):
        image_publication_run.redirect(title, "File:New.png", "File:Old.png", wiki, run, "Publish")
    recovery = RunRecord(tmp_path / "recovery")

    with pytest.raises(MediaWikiEditVerificationError) as caught:
        revert(RunRecord.load(run.directory), wiki, None, recovery, OWNERS, "Reviewed recovery")

    assert caught.value is errors[1]
    (entry,) = RunRecord.load(recovery.directory).entries
    assert entry["requires_rollback"] is True
    assert entry["revision"] == errors[1].new_revision_id
    assert entry["old_text"] == "#REDIRECT [[File:New.png]]"
    assert entry["actual_parent_snapshot"]["source_text"] == "editor's actual preimage"
    assert run.entries[0]["old_text"] == "#REDIRECT [[File:Old.png]]"


def test_unknown_image_parent_blocks_earlier_upload_recovery(setup: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    pictures, wiki, cache, tmp_path = setup
    title = "File:A Collection of Notes.png"
    pictures.add(SCROLL, title)
    wiki.put_file(title, OLD)
    wiki.put_redirect(title, "File:A collection of notes.png")
    catalog = pictures.build()
    _fail_image_edit_verification(wiki, monkeypatch, parent_known=False)
    run = RunRecord(tmp_path / "run")
    with pytest.raises(MediaWikiEditVerificationError):
        execute(_plan(catalog, wiki, cache), catalog, wiki, wiki, run, "Publish")
    recovery = RunRecord(tmp_path / "recovery")

    revert(RunRecord.load(run.directory), wiki, None, recovery, OWNERS, "Reviewed recovery")

    assert wiki.uploads == 1
    assert wiki.files[title][0].data == SCROLL
    assert len(recovery.entries) == 1
    assert recovery.entries[0]["done"] is False
    assert "parent revision is not proven" in recovery.entries[0]["reason"]


class _NativeImageAPI:
    """Exercise image consumers through the real native client with a lost POST response."""

    title = "File:Notes.png"
    old_target = "File:Old.png"
    new_target = "File:New.png"

    def __init__(self, directory: Path, *, outcome: str = "lost", commit: bool = True, create: bool = False) -> None:
        self.directory = directory
        self.outcome = outcome
        self.commit = commit
        self.fail_reads = False
        self.requests: list[tuple[str, dict[str, str]]] = []
        self.history: dict[int, dict[str, Any]] = {}
        self.current = 0 if create else 1234
        if not create:
            self.history[1234] = self._revision(1234, 1233, f"#REDIRECT [[{self.old_target}]]")

    def _revision(self, revision: int, parent: int, text: str) -> dict[str, Any]:
        return {
            "revid": revision,
            "parentid": parent,
            "timestamp": "2026-10-17T00:00:00Z",
            "user": BOT,
            "slots": {"main": {"contentmodel": "wikitext", "*": normalize_saved_text(text)}},
        }

    def handle(self, request: httpx.Request) -> httpx.Response:
        params = (
            {key: values[0] for key, values in parse_qs(request.content.decode()).items()}
            if request.method == "POST"
            else dict(request.url.params)
        )
        self.requests.append((request.method, params))
        if request.method == "POST":
            assert params["action"] == "edit"
            assert params["title"] == self.title
            pending = RunRecord.load(self.directory).entries[-1]
            assert pending["done"] is None
            assert pending["pending_mutation"] is True
            assert pending["intended_source"] == params["text"]
            old = self.current
            if self.commit:
                self.current = max(1234, self.current) + 1
                self.history[self.current] = self._revision(self.current, old, params["text"])
            if self.outcome == "success":
                return httpx.Response(
                    200, json={"edit": {"result": "Success", "oldrevid": old, "newrevid": self.current}}
                )
            self.fail_reads = True
            if self.outcome == "interrupt":
                raise KeyboardInterrupt("operator interrupted the POST")
            if self.outcome == "protocol":
                raise httpx.RemoteProtocolError("POST response lost", request=request)
            raise httpx.ReadTimeout("POST response lost", request=request)
        if params.get("meta") == "tokens":
            return httpx.Response(200, json={"query": {"tokens": {"csrftoken": "fixture-token"}}})
        assert params.get("prop") in ("revisions", "revisions|info")
        if self.fail_reads:
            raise httpx.ReadTimeout("attribution read unavailable", request=request)
        if (
            self.outcome == "preflight changed"
            and params.get("prop") == "revisions"
            and "content" not in params.get("rvprop", "").split("|")
        ):
            self.current = 1235
            self.history[self.current] = self._revision(self.current, 1234, f"#REDIRECT [[{self.new_target}]]")
            self.history[self.current]["user"] = "Editor"
        if "revids" in params:
            revisions = [self.history[int(value)] for value in params["revids"].split("|")]
        else:
            assert params["titles"] == self.title
            if not self.current:
                return httpx.Response(
                    200,
                    json={
                        "curtimestamp": "2026-10-17T00:00:01Z",
                        "query": {"pages": {"-1": {"title": self.title, "missing": ""}}},
                    },
                )
            revisions = [self.history[self.current]]
        return httpx.Response(
            200,
            json={
                "curtimestamp": "2026-10-17T00:00:01Z",
                "query": {
                    "pages": {
                        "42": {
                            "pageid": 42,
                            "title": self.title,
                            "contentmodel": "wikitext",
                            "revisions": revisions,
                        }
                    }
                },
            },
        )

    def client(self) -> MediaWikiClient:
        return MediaWikiClient(
            api_url="https://fixture.invalid/api.php",
            bot_username=f"{BOT}@Publish",
            clock=MockClock(),
            transport=httpx.MockTransport(self.handle),
            request_policy=MediaWikiRequestPolicy(max_retries=1),
        )


@pytest.mark.parametrize("outcome", ["lost", "protocol", "interrupt"])
@pytest.mark.parametrize("commit", [False, True])
@pytest.mark.parametrize(("action", "create"), [("redirect", False), ("redirect", True), ("describe", False)])
def test_native_image_unknown_outcome_is_durable_and_stops_dependencies(
    tmp_path: Path, outcome: str, commit: bool, action: str, create: bool
) -> None:
    run = RunRecord(tmp_path / "run")
    api = _NativeImageAPI(run.directory, outcome=outcome, commit=commit, create=create)
    administrator = MediaWikiFake()
    administrator.put_file("File:Orphan.png", OLD)
    pictures = _Catalog(tmp_path / "catalog")
    image_hash = pictures.add(SCROLL, api.title)
    first = (
        PlannedTitle(api.title, "describe", image_hash, api.title, "", redirect_target=api.old_target)
        if action == "describe"
        else PlannedTitle(api.title, "redirect", "", api.new_target, "", redirect_target=api.old_target)
    )
    plan = PublishPlan(
        (
            first,
            PlannedTitle("File:Later.png", "redirect", "", api.new_target, ""),
        ),
        (Orphan("File:Orphan.png", _sha1(OLD), "t"),),
        (),
    )
    expected_error = KeyboardInterrupt if outcome == "interrupt" else MediaWikiNetworkError
    with api.client() as writer:
        with pytest.raises(expected_error):
            execute(plan, pictures.build(), writer, administrator, run, "Publish")
        (pending,) = RunRecord.load(run.directory).entries
        assert pending["done"] is None
        assert pending["pending_mutation"] is True
        assert pending["mutation_state"] == "ambiguous"
        assert pending["edit_account"] == BOT
        assert pending["reviewed_snapshot"]["source_text"] == (None if create else f"#REDIRECT [[{api.old_target}]]")
        assert pending["intended_content_model"] == "wikitext"
        assert pending["intended_source_sha256"] == hashlib.sha256(pending["intended_source"].encode()).hexdigest()
        recovery = RunRecord(tmp_path / "recovery")
        revert(RunRecord.load(run.directory), writer, administrator, recovery, OWNERS, "Revert")
        assert RunRecord.load(run.directory).entries[0]["pending_mutation"] is True
        assert recovery.entries[0]["action"] == f"reconcile {action}"
        assert recovery.entries[0]["done"] is False
        if not commit:
            api.fail_reads = False
            revert(RunRecord.load(run.directory), writer, administrator, recovery, OWNERS, "Revert")
            assert RunRecord.load(run.directory).entries[0]["pending_mutation"] is True
    assert len([request for request in api.requests if request[0] == "POST"]) == 1
    assert all(params.get("titles") != "File:Later.png" for _, params in api.requests)
    assert "File:Orphan.png" in administrator.files
    assert administrator.archive == {}


@pytest.mark.parametrize("create", [False, True])
def test_native_image_ack_resolves_the_same_intent_once(tmp_path: Path, create: bool) -> None:
    run = RunRecord(tmp_path / "run")
    api = _NativeImageAPI(run.directory, outcome="success", create=create)
    with api.client() as writer:
        image_publication_run.redirect(api.title, api.new_target, api.old_target, writer, run, "Publish")
    (entry,) = RunRecord.load(run.directory).entries
    assert entry["done"] is True
    assert entry["pending_mutation"] is False
    assert entry["verified"] is True
    assert entry["revision"] == api.current
    assert sum(bool(entry.get("done")) for entry in run.entries) == 1


@pytest.mark.parametrize(
    "proof",
    [
        "complete",
        "other actor",
        "unknown parent",
        "different parent",
        "model",
        "source",
        "unicode whitespace",
        "endpoint",
    ],
)
def test_native_image_pending_recovery_requires_strong_evidence_before_upload_undo(tmp_path: Path, proof: str) -> None:
    run = RunRecord(tmp_path / "run")
    api = _NativeImageAPI(run.directory)
    run.add({"title": "File:Earlier.png", "action": "update", "done": True, "new_sha1": "earlier-upload"})
    with api.client() as writer:
        with pytest.raises(MediaWikiNetworkError):
            image_publication_run.redirect(api.title, api.new_target, api.old_target, writer, run, "Publish")
        api.fail_reads = False
        api.outcome = "success"
        if proof == "other actor":
            api.history[api.current]["user"] = "Editor"
        elif proof == "unknown parent":
            api.history[api.current].pop("parentid")
        elif proof == "different parent":
            api.history[api.current]["parentid"] = 1233
        elif proof == "model":
            api.history[api.current]["slots"]["main"]["contentmodel"] = "javascript"
        elif proof == "source":
            api.history[api.current]["slots"]["main"]["*"] = "editor content"
        elif proof == "unicode whitespace":
            api.history[api.current]["slots"]["main"]["*"] += "\u00a0"
        elif proof == "endpoint":
            writer.api_url = "https://another.invalid/api.php"
        saved = RunRecord.load(run.directory)
        recovery = RunRecord(tmp_path / "recovery")
        if proof == "complete":
            api.directory = recovery.directory
            revert(saved, writer, None, recovery, OWNERS, "Revert", titles=[api.title])
            assert api.history[api.current]["slots"]["main"]["*"] == f"#REDIRECT [[{api.old_target}]]"
            (restored,) = recovery.entries
            assert restored["done"] is True
            original = RunRecord.load(run.directory)
            assert len(original.entries) == 2
            assert original.entries[1]["pending_mutation"] is False
            assert original.entries[1]["mutation_state"] == "reconciled"
            assert original.entries[1]["actual_parent_snapshot"]["revision"]["revision_id"] == 1234
            assert len([request for request in api.requests if request[0] == "POST"]) == 2
        else:
            revert(saved, writer, None, recovery, OWNERS, "Revert")
            assert RunRecord.load(run.directory).entries[1]["pending_mutation"] is True
            assert recovery.entries[0]["done"] is False
            assert len([request for request in api.requests if request[0] == "POST"]) == 1


@pytest.mark.parametrize(
    "action", ["describe", "revert redirect", "revert describe", "revert retire", "revert unverified"]
)
def test_image_helpers_checkpoint_intent_before_interrupted_native_edit(
    setup: Any, monkeypatch: pytest.MonkeyPatch, action: str
) -> None:
    pictures, wiki, _, tmp_path = setup
    title = "File:Notes.png"
    target = "File:Old.png"
    wiki.put_redirect(title, target)
    page = wiki.get_page_snapshots([title])[title]
    record = RunRecord(tmp_path / "run")
    calls = 0

    def interrupted(*args: Any, **kwargs: Any) -> int:
        nonlocal calls
        calls += 1
        (pending,) = RunRecord.load(record.directory).entries
        assert pending["pending_mutation"] is True
        assert pending["done"] is None
        assert pending["reviewed_snapshot"]["source_text"] == page.source_text
        raise KeyboardInterrupt("interrupted native edit")

    monkeypatch.setattr(wiki, "safe_edit_page", interrupted)
    with pytest.raises(KeyboardInterrupt):
        if action == "describe":
            image_hash = pictures.add(SCROLL, title)
            image_publication_run._describe(
                PlannedTitle(title, "describe", image_hash, title, "", redirect_target=target),
                pictures.build(),
                wiki,
                record,
                "Publish",
            )
        elif action == "revert redirect":
            image_publication_run._restore_redirect(
                {"title": title, "target": target, "old_text": "old source", "api_url": wiki.api_url},
                wiki,
                record,
                "Revert",
            )
        elif action == "revert describe":
            image_publication_run._restore_description(
                {"title": title, "text": page.source_text, "old_text": "old source", "api_url": wiki.api_url},
                wiki,
                record,
                "Revert",
            )
        elif action == "revert retire":
            wiki.put_file(title, OLD)
            wiki.delete_page(title, "fixture")
            wiki.put_redirect(title, target)
            image_publication_run._restore_copy(
                {"title": title, "file": target, "description": "old source"}, wiki, wiki, record, "Revert"
            )
        else:
            from dataclasses import asdict

            assert page.revision is not None
            parent = page
            wiki.put_page(title, "written text")
            written = wiki.get_page_snapshots([title])[title]
            assert written.revision is not None
            page = written
            image_publication_run._restore_unverified_edit(
                {
                    "title": title,
                    "action": "redirect",
                    "api_url": wiki.api_url,
                    "revision": written.revision.revision_id,
                    "actual_parent_snapshot": asdict(parent),
                    "written_snapshot": asdict(written),
                },
                wiki,
                record,
                "Revert",
            )
    assert calls == 1
    (pending,) = RunRecord.load(record.directory).entries
    assert pending["pending_mutation"] is True
    assert pending["done"] is None


def test_image_intent_checkpoint_failure_prevents_native_write(setup: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    _, wiki, _, tmp_path = setup
    title = "File:Notes.png"
    wiki.put_redirect(title, "File:Old.png")
    revision = wiki.revisions[title]

    def fail_checkpoint(self: RunRecord) -> None:
        raise OSError("intent cannot be persisted")

    monkeypatch.setattr(RunRecord, "save", fail_checkpoint)
    with pytest.raises(OSError, match="intent cannot be persisted"):
        image_publication_run.redirect(
            title, "File:New.png", "File:Old.png", wiki, RunRecord(tmp_path / "run"), "Publish"
        )
    assert wiki.revisions[title] == revision


def test_image_description_recovery_normalizes_saved_text_but_keeps_unicode_whitespace(setup: Any) -> None:
    _, wiki, _, tmp_path = setup
    title = "File:Notes.png"
    text = "Summary\r\nLicense\u00a0\r\n"
    wiki.put_page(title, text)
    run = RunRecord(tmp_path / "run")
    image_publication_run._restore_description(
        {"title": title, "text": text, "old_text": "raw\r\npreimage\u00a0", "api_url": wiki.api_url},
        wiki,
        run,
        "Revert",
    )
    assert wiki.pages[title] == "raw\npreimage\u00a0"
    assert run.entries[0]["intended_source"] == "raw\r\npreimage\u00a0"
    wiki.put_page(title, "Summary\nLicense")
    refused = RunRecord(tmp_path / "refused")
    before = wiki.revisions[title]
    image_publication_run._restore_description(
        {"title": title, "text": text, "old_text": "old", "api_url": wiki.api_url}, wiki, refused, "Revert"
    )
    assert wiki.revisions[title] == before
    assert refused.entries[0]["done"] is False


def test_native_image_explicit_preflight_rejection_does_not_adopt_matching_editor_revision(tmp_path: Path) -> None:
    run = RunRecord(tmp_path / "run")
    api = _NativeImageAPI(run.directory, outcome="preflight changed")
    with api.client() as writer:
        image_publication_run.redirect(api.title, api.new_target, api.old_target, writer, run, "Publish")
        (entry,) = RunRecord.load(run.directory).entries
        assert entry["done"] is False
        assert entry["pending_mutation"] is False
        assert entry["mutation_state"] == "rejected"
        recovery = RunRecord(tmp_path / "recovery")
        revert(RunRecord.load(run.directory), writer, None, recovery, OWNERS, "Revert")
    assert api.history[api.current]["user"] == "Editor"
    assert not any(method == "POST" for method, _ in api.requests)
    assert recovery.entries == []


@pytest.mark.parametrize("failure", [None, "file_fsync", "directory_fsync"])
def test_image_native_edit_waits_for_durable_intent(
    setup: Any, monkeypatch: pytest.MonkeyPatch, failure: str | None
) -> None:
    _, wiki, _, tmp_path = setup
    title = "File:Notes.png"
    wiki.put_redirect(title, "File:Old.png")
    original_revision = wiki.revisions[title]
    record = RunRecord(tmp_path / "nested" / "run")
    events: list[str] = []
    original_fsync = os.fsync
    original_replace = os.replace
    original_edit = wiki.safe_edit_page

    def observe_fsync(descriptor: int) -> None:
        kind = "directory_fsync" if stat.S_ISDIR(os.fstat(descriptor).st_mode) else "file_fsync"
        if kind == failure:
            raise OSError(f"{kind} unavailable")
        original_fsync(descriptor)
        events.append(kind)

    def observe_replace(source: Any, destination: Any, *args: Any, **kwargs: Any) -> None:
        original_replace(source, destination, *args, **kwargs)
        if Path(destination) == record.directory / "run.json":
            events.append("replace")

    def observe_edit(title: str, content: str, base_revision: MediaWikiPageRevision, summary: str | None = None) -> int:
        expected_directories = 1 + len(record.directory.absolute().parents)
        assert events == ["file_fsync", "replace", *(["directory_fsync"] * expected_directories)]
        (pending,) = RunRecord.load(record.directory).entries
        assert pending["pending_mutation"] is True
        assert pending["done"] is None
        assert pending["intended_source"] == content
        events.append("native_edit")
        return original_edit(title, content, base_revision, summary=summary)

    monkeypatch.setattr(os, "fsync", observe_fsync)
    monkeypatch.setattr(os, "replace", observe_replace)
    monkeypatch.setattr(wiki, "safe_edit_page", observe_edit)

    if failure is not None:
        with pytest.raises(OSError, match=f"{failure} unavailable"):
            image_publication_run.redirect(title, "File:New.png", "File:Old.png", wiki, record, "Publish")
        assert "native_edit" not in events
        assert wiki.revisions[title] == original_revision
    else:
        image_publication_run.redirect(title, "File:New.png", "File:Old.png", wiki, record, "Publish")
        assert events.count("native_edit") == 1
        assert RunRecord.load(record.directory).entries[0]["pending_mutation"] is False


@pytest.mark.parametrize("action", ["redirect", "describe", "acknowledged"])
@pytest.mark.parametrize("binding", ["other endpoint", "missing endpoint"])
def test_known_image_edit_endpoint_binding_blocks_all_earlier_recovery(
    setup: Any, monkeypatch: pytest.MonkeyPatch, action: str, binding: str
) -> None:
    from copy import deepcopy

    pictures, wiki, _, tmp_path = setup
    title = "File:Notes.png"
    wiki.put_file(title, SCROLL)
    wiki.put_redirect(title, "File:Old.png")
    run = RunRecord(tmp_path / "run")
    run.add(
        {
            "title": title,
            "action": "update",
            "done": True,
            "new_sha1": _sha1(SCROLL),
            "old_sha1": _sha1(OLD),
            "replaced": "old.bin",
        }
    )
    (run.directory / "old.bin").write_bytes(OLD)
    if action == "acknowledged":
        _fail_image_edit_verification(wiki, monkeypatch)
        with pytest.raises(MediaWikiEditVerificationError):
            image_publication_run.redirect(title, "File:New.png", "File:Old.png", wiki, run, "Publish")
        monkeypatch.undo()
    elif action == "describe":
        image_hash = pictures.add(SCROLL, title)
        image_publication_run._describe(
            PlannedTitle(title, "describe", image_hash, title, "", redirect_target="File:Old.png"),
            pictures.build(),
            wiki,
            run,
            "Publish",
        )
    else:
        image_publication_run.redirect(title, "File:New.png", "File:Old.png", wiki, run, "Publish")
    clone = deepcopy(wiki)
    if binding == "other endpoint":
        clone.api_url = "https://clone.invalid/api.php"
    else:
        run.entries[-1].pop("api_url")
        run.save()
    before = clone.revisions[title]
    recovery = RunRecord(tmp_path / "recovery")

    revert(RunRecord.load(run.directory), clone, None, recovery, OWNERS, "Revert")

    assert clone.revisions[title] == before
    assert clone.uploads == 0
    assert clone.files[title][0].data == SCROLL
    assert recovery.entries[0]["done"] is False
    assert "endpoint is not proven" in recovery.entries[0]["reason"]


@pytest.mark.parametrize("interruption", ["upload failure", "before receipt checkpoint", "before original checkpoint"])
def test_original_image_run_resumes_after_parent_restoration(
    setup: Any, monkeypatch: pytest.MonkeyPatch, interruption: str
) -> None:
    pictures, wiki, cache, tmp_path = setup
    title = "File:A Collection of Notes.png"
    pictures.add(SCROLL, title)
    wiki.put_file(title, OLD)
    wiki.put_redirect(title, "File:A collection of notes.png")
    catalog = pictures.build()
    _fail_image_edit_verification(wiki, monkeypatch)
    run = RunRecord(tmp_path / "run")
    with pytest.raises(MediaWikiEditVerificationError):
        execute(_plan(catalog, wiki, cache), catalog, wiki, wiki, run, "Publish")
    monkeypatch.undo()
    first = RunRecord(tmp_path / "first-recovery")
    native_update = RunRecord.update

    def interrupted_update(self: RunRecord, entry: dict[str, Any], **values: Any) -> None:
        if (
            interruption == "before receipt checkpoint"
            and self.directory == first.directory
            and values.get("verified") is True
        ):
            raise KeyboardInterrupt("before recovery receipt checkpoint")
        if (
            interruption == "before original checkpoint"
            and self.directory == run.directory
            and "restoration_revision" in values
        ):
            raise KeyboardInterrupt("before original restoration checkpoint")
        native_update(self, entry, **values)

    def interrupted_upload(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise MediaWikiNetworkError("upload recovery interrupted")

    with monkeypatch.context() as patch:
        patch.setattr(RunRecord, "update", interrupted_update)
        if interruption == "upload failure":
            patch.setattr(wiki, "upload_file", interrupted_upload)
            revert(RunRecord.load(run.directory), wiki, None, first, OWNERS, "Revert")
        else:
            with pytest.raises(KeyboardInterrupt):
                revert(RunRecord.load(run.directory), wiki, None, first, OWNERS, "Revert")
    assert wiki.pages[title] == "editor's actual preimage"
    assert wiki.files[title][0].data == SCROLL
    original = RunRecord.load(run.directory)
    assert original.entries[1]["restoration_record"] == str(first.directory.resolve())
    assert original.entries[1]["restoration_entry"] == 0
    if interruption == "upload failure":
        assert original.entries[1]["requires_rollback"] is False
        assert original.entries[1]["restoration_revision"] == wiki.revisions[title]
    else:
        assert "restoration_revision" not in original.entries[1]
    assert first.directory.joinpath("run.json").is_file()

    def no_replay(*args: Any, **kwargs: Any) -> int:
        pytest.fail("completed page restoration must not be replayed")

    monkeypatch.setattr(wiki, "safe_edit_page", no_replay)
    second = RunRecord(tmp_path / "second-recovery")
    revert(RunRecord.load(run.directory), wiki, None, second, OWNERS, "Revert")

    assert wiki.files[title][0].data == OLD
    assert wiki.pages[title] == "editor's actual preimage"
    assert RunRecord.load(run.directory).entries[1]["requires_rollback"] is False
    assert RunRecord.load(run.directory).entries[1]["restoration_revision"] is not None
    assert [(entry["action"], entry["done"]) for entry in second.entries] == [("revert update", True)]
    assert RunRecord.load(first.directory).entries[0]["pending_mutation"] is False


@pytest.mark.parametrize("proof", ["other actor", "unknown parent"])
def test_image_restoration_crash_recovery_does_not_adopt_matching_text_without_ancestry(
    setup: Any, monkeypatch: pytest.MonkeyPatch, proof: str
) -> None:
    pictures, wiki, cache, tmp_path = setup
    title = "File:A Collection of Notes.png"
    pictures.add(SCROLL, title)
    wiki.put_file(title, OLD)
    wiki.put_redirect(title, "File:A collection of notes.png")
    catalog = pictures.build()
    _fail_image_edit_verification(wiki, monkeypatch)
    run = RunRecord(tmp_path / "run")
    with pytest.raises(MediaWikiEditVerificationError):
        execute(_plan(catalog, wiki, cache), catalog, wiki, wiki, run, "Publish")
    monkeypatch.undo()
    first = RunRecord(tmp_path / "first-recovery")
    native_update = RunRecord.update

    def lose_receipt(self: RunRecord, entry: dict[str, Any], **values: Any) -> None:
        if self.directory == first.directory and values.get("verified") is True:
            raise KeyboardInterrupt("lost restoration receipt")
        native_update(self, entry, **values)

    with monkeypatch.context() as patch:
        patch.setattr(RunRecord, "update", lose_receipt)
        with pytest.raises(KeyboardInterrupt):
            revert(RunRecord.load(run.directory), wiki, None, first, OWNERS, "Revert")
    if proof == "other actor":
        wiki.put_page(title, wiki.pages[title], user="Editor")
    else:
        wiki.page_parents.pop(title)
    before = wiki.revisions[title]
    second = RunRecord(tmp_path / "second-recovery")

    revert(RunRecord.load(run.directory), wiki, None, second, OWNERS, "Revert")

    assert wiki.revisions[title] == before
    assert wiki.files[title][0].data == SCROLL
    assert "restoration_revision" not in RunRecord.load(run.directory).entries[1]
    assert RunRecord.load(first.directory).entries[0]["pending_mutation"] is True
    assert second.entries[0]["done"] is False
