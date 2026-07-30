"""Pure parsing tests for SteamDB's build-level RSS feed."""

from datetime import UTC, datetime

from erenshor.infrastructure.steam.build_feed import parse_build_feed, resolve_build_published_at

FEED_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">
  <channel>
    <title>SteamDB Patchnotes</title>
    <item>
      <guid isPermaLink="false">build#24362350</guid>
      <title>Erenshor update for 24 July 2026</title>
      <link>https://steamdb.info/patchnotes/24362350/</link>
      <description>SteamDB Build 24362350</description>
      <pubDate>Thu, 23 Jul 2026 21:53:44 +0000</pubDate>
    </item>
    <item>
      <guid isPermaLink="false">build#24405256</guid>
      <title>Erenshor update for 27 July 2026</title>
      <link>https://steamdb.info/patchnotes/24405256/</link>
      <description>7/26/26 - Patch Notes (SteamDB Build 24405256)</description>
      <pubDate>Mon, 27 Jul 2026 03:08:59 +0000</pubDate>
      <media:thumbnail width="1200" height="630" url="https://steamdb.info/patchnotes/24405256.png"/>
    </item>
  </channel>
</rss>
"""


def test_parser_sorts_newest_first_and_extracts_notes() -> None:
    builds = parse_build_feed(FEED_XML)

    assert [build.build_id for build in builds] == ["24405256", "24362350"]
    assert builds[0].published_at == datetime(2026, 7, 27, 3, 8, 59, tzinfo=UTC)
    assert builds[1].published_at == datetime(2026, 7, 23, 21, 53, 44, tzinfo=UTC)
    assert all(build.published_at.tzinfo is UTC for build in builds)
    assert builds[0].notes_title == "7/26/26 - Patch Notes"
    assert builds[1].notes_title is None
    assert builds[0].url == "https://steamdb.info/patchnotes/24405256/"


def test_parser_skips_items_without_guid_or_pub_date() -> None:
    xml = """\
<rss><channel>
  <item><guid>not-a-build</guid><pubDate>Mon, 27 Jul 2026 03:08:59 +0000</pubDate></item>
  <item><guid>build#100</guid></item>
  <item><guid>build#101</guid><pubDate>Mon, 27 Jul 2026 03:08:59 +0000</pubDate></item>
</channel></rss>
"""

    builds = parse_build_feed(xml)

    assert [build.build_id for build in builds] == ["101"]


def test_unknown_build_id_does_not_use_nearest_timestamp() -> None:
    builds = parse_build_feed(FEED_XML)

    assert resolve_build_published_at(builds, "24362351") is None


def test_parser_returns_empty_for_malformed_or_empty_documents() -> None:
    assert parse_build_feed("") == []
    assert parse_build_feed("<rss><channel>") == []
