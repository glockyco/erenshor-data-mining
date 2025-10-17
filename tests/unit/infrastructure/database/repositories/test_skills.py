"""Tests for SkillRepository."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from erenshor.infrastructure.database.connection import DatabaseConnection

if TYPE_CHECKING:
    from pathlib import Path


pytestmark = pytest.mark.skip(reason="Skills table not present in integration database fixture yet")


@pytest.fixture
def skill_repo(integration_db: Path):
    """Create SkillRepository with integration database."""
    from erenshor.infrastructure.database.repositories.skills import SkillRepository

    db = DatabaseConnection(integration_db, read_only=False)
    return SkillRepository(db)


def test_placeholder():
    """Placeholder test - Skills repository tests will be enabled once Skills table is added to integration fixture."""
    pass
