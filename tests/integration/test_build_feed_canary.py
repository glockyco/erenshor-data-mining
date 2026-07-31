"""Live contract canary for SteamDB's build feed."""

from __future__ import annotations

import pytest

from erenshor.infrastructure.config import load_config
from erenshor.infrastructure.steam.build_feed import fetch_build_feed

pytestmark = pytest.mark.canary


def test_main_steamdb_build_feed_contract() -> None:
    """SteamDB's live feed retains the shape used for build provenance."""
    main_app_id = load_config().variants["main"].app_id
    builds = fetch_build_feed(main_app_id)

    assert builds, "SteamDB returned no parseable builds"
    assert all(build.build_id.isdecimal() for build in builds), "Every build must have a numeric ID"
    assert all(
        build.published_at.tzinfo is not None and build.published_at.utcoffset() is not None for build in builds
    ), "Every build must have a timezone-aware publish time"
    assert any(build.notes_title for build in builds), "At least one build must carry a notes title"
