"""Publishing plans every title against one listing and writes only what the plan allows."""

from __future__ import annotations

import hashlib
import io
from pathlib import Path
from typing import Any

import pytest
from PIL import Image
from tests.fakes.mediawiki import MediaWikiFake, PurgeRequest

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
from erenshor.application.services.image_publication_run import RunRecord, description, execute, revert
from erenshor.infrastructure.wiki import (
    MediaWikiAPIError,
)
from erenshor.infrastructure.wiki.client import (
    MediaWikiFile,
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
