"""Unit tests for upload skip logic (local and wiki-based)."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Iterator
from unittest.mock import Mock

import pytest

from erenshor.application.services.upload_service import UploadService
from erenshor.application.upload.models import UploadResult
from erenshor.application.upload.uploader import PageUploader
from erenshor.domain.events import PageUploaded, UploadComplete
from erenshor.infrastructure.storage.page_storage import PageStorage
from erenshor.registry.core import WikiRegistry


@pytest.fixture
def mock_registry(tmp_path):
    """Create a mock registry with test pages."""
    registry = WikiRegistry(tmp_path / "registry")
    registry.pages_dir.mkdir(parents=True, exist_ok=True)
    return registry


@pytest.fixture
def mock_storage(mock_registry):
    """Create a mock storage."""
    return PageStorage(mock_registry)


@pytest.fixture
def mock_uploader():
    """Create a mock uploader."""
    client = Mock()
    return PageUploader(client)


class TestLocalBasedSkip:
    """Test local-based skip logic (no network calls)."""

    def test_skip_when_content_unchanged_and_already_pushed(
        self, mock_registry, mock_storage, mock_uploader
    ):
        """Skip upload when content hash is unchanged and page was pushed before."""
        # Setup: Create page with content that hasn't changed
        page = mock_registry.create_page("Test Page")
        content = "Test content that hasn't changed"
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        page.updated_content_hash = content_hash
        page.last_pushed = datetime(2024, 1, 1, tzinfo=timezone.utc)
        mock_registry.save()

        # Write the content to storage
        mock_storage.write(page, content)

        # Create service
        service = UploadService(mock_uploader, mock_storage, mock_registry)

        # Execute upload
        events = list(
            service.upload_pages(
                page_titles=["Test Page"],
                summary="Test",
                minor=True,
                force=False,
            )
        )

        # Verify: Should be skipped (local-based)
        assert len(events) == 2  # PageUploaded (skip) + UploadComplete
        assert isinstance(events[0], PageUploaded)
        assert events[0].action == "skipped"
        assert events[0].message == "No local changes since last push"

        assert isinstance(events[1], UploadComplete)
        assert events[1].uploaded == 0
        assert events[1].skipped == 1
        assert events[1].failed == 0

    def test_no_skip_when_content_changed(
        self, mock_registry, mock_storage, mock_uploader
    ):
        """Don't skip when content hash has changed."""
        # Setup: Create page with changed content
        page = mock_registry.create_page("Test Page")
        old_content = "Old content"
        new_content = "New content"
        old_hash = hashlib.sha256(old_content.encode()).hexdigest()

        # Set the old hash AFTER writing content
        # This simulates a scenario where the content file was modified
        # but the hash in registry wasn't updated
        path = mock_storage.pages_dir / page.safe_filename
        path.write_text(new_content, encoding="utf-8")

        page.updated_content_hash = old_hash
        page.last_pushed = datetime(2024, 1, 1, tzinfo=timezone.utc)
        mock_registry.save()

        # Mock uploader to return success
        def mock_upload(*args, **kwargs) -> Iterator[UploadResult]:
            yield UploadResult(
                title="Test Page",
                success=True,
                action="uploaded",
                message="Success",
                timestamp=datetime.now(timezone.utc),
            )

        mock_uploader.upload_pages = mock_upload

        # Create service
        service = UploadService(mock_uploader, mock_storage, mock_registry)

        # Execute upload
        events = list(
            service.upload_pages(
                page_titles=["Test Page"],
                summary="Test",
                minor=True,
                force=False,
            )
        )

        # Verify: Should NOT be skipped (content changed)
        assert len(events) == 2  # PageUploaded (uploaded) + UploadComplete
        assert isinstance(events[0], PageUploaded)
        assert events[0].action == "uploaded"

        assert isinstance(events[1], UploadComplete)
        assert events[1].uploaded == 1
        assert events[1].skipped == 0
        assert events[1].failed == 0

    def test_no_skip_when_never_pushed(
        self, mock_registry, mock_storage, mock_uploader
    ):
        """Don't skip when page was never pushed before."""
        # Setup: Create page that was never pushed
        page = mock_registry.create_page("Test Page")
        content = "Test content"
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        page.updated_content_hash = content_hash
        page.last_pushed = None  # Never pushed
        mock_registry.save()

        # Write content to storage
        mock_storage.write(page, content)

        # Mock uploader to return success
        def mock_upload(*args, **kwargs) -> Iterator[UploadResult]:
            yield UploadResult(
                title="Test Page",
                success=True,
                action="uploaded",
                message="Success",
                timestamp=datetime.now(timezone.utc),
            )

        mock_uploader.upload_pages = mock_upload

        # Create service
        service = UploadService(mock_uploader, mock_storage, mock_registry)

        # Execute upload
        events = list(
            service.upload_pages(
                page_titles=["Test Page"],
                summary="Test",
                minor=True,
                force=False,
            )
        )

        # Verify: Should NOT be skipped (never pushed)
        assert len(events) == 2
        assert isinstance(events[0], PageUploaded)
        assert events[0].action == "uploaded"

        assert isinstance(events[1], UploadComplete)
        assert events[1].uploaded == 1
        assert events[1].skipped == 0


class TestWikiBasedSkip:
    """Test wiki-based skip logic (compares with online content)."""

    def test_skip_when_wiki_content_identical(self, mock_registry, mock_storage):
        """Skip when local content matches wiki content."""
        # Setup
        page = mock_registry.create_page("Test Page")
        content = "Test content"
        mock_registry.save()
        mock_storage.write(page, content)

        # Mock client to return identical content
        mock_client = Mock()
        mock_client.fetch_page.return_value = content

        uploader = PageUploader(mock_client)
        service = UploadService(uploader, mock_storage, mock_registry)

        # Execute upload
        events = list(
            service.upload_pages(
                page_titles=["Test Page"],
                summary="Test",
                minor=True,
                force=False,
            )
        )

        # Verify: Should be skipped (wiki-based)
        skip_events = [e for e in events if isinstance(e, PageUploaded)]
        assert len(skip_events) == 1
        assert skip_events[0].action == "skipped"
        assert "wiki" in skip_events[0].message.lower()

        # Verify last_pushed was updated (wiki-based skip updates timestamp)
        page_after = mock_registry.get_page_by_title("Test Page")
        assert page_after is not None
        assert page_after.last_pushed is not None

    def test_upload_when_wiki_content_differs(self, mock_registry, mock_storage):
        """Upload when local content differs from wiki content."""
        # Setup
        page = mock_registry.create_page("Test Page")
        local_content = "New content"
        wiki_content = "Old content"
        mock_registry.save()
        mock_storage.write(page, local_content)

        # Mock client to return different content
        mock_client = Mock()
        mock_client.fetch_page.return_value = wiki_content
        mock_client.upload_page.return_value = {"newrevid": 123}

        uploader = PageUploader(mock_client)
        service = UploadService(uploader, mock_storage, mock_registry)

        # Execute upload
        events = list(
            service.upload_pages(
                page_titles=["Test Page"],
                summary="Test",
                minor=True,
                force=False,
            )
        )

        # Verify: Should be uploaded (content differs)
        upload_events = [e for e in events if isinstance(e, PageUploaded)]
        assert len(upload_events) == 1
        assert upload_events[0].action == "uploaded"

        # Verify upload was called
        mock_client.upload_page.assert_called_once()


class TestForceFlag:
    """Test --force flag behavior."""

    def test_force_bypasses_local_skip(
        self, mock_registry, mock_storage, mock_uploader
    ):
        """Force flag bypasses local-based skip."""
        # Setup: Page that would normally be skipped
        page = mock_registry.create_page("Test Page")
        content = "Test content"
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        page.updated_content_hash = content_hash
        page.last_pushed = datetime(2024, 1, 1, tzinfo=timezone.utc)
        mock_registry.save()
        mock_storage.write(page, content)

        # Mock uploader to return success
        def mock_upload(*args, **kwargs) -> Iterator[UploadResult]:
            yield UploadResult(
                title="Test Page",
                success=True,
                action="uploaded",
                message="Success",
                timestamp=datetime.now(timezone.utc),
            )

        mock_uploader.upload_pages = mock_upload

        # Create service
        service = UploadService(mock_uploader, mock_storage, mock_registry)

        # Execute upload with force=True
        events = list(
            service.upload_pages(
                page_titles=["Test Page"],
                summary="Test",
                minor=True,
                force=True,  # Force upload
            )
        )

        # Verify: Should be uploaded (not skipped)
        assert len(events) == 2
        assert isinstance(events[0], PageUploaded)
        assert events[0].action == "uploaded"

        assert isinstance(events[1], UploadComplete)
        assert events[1].uploaded == 1
        assert events[1].skipped == 0

    def test_force_bypasses_wiki_skip(self, mock_registry, mock_storage):
        """Force flag bypasses wiki-based skip."""
        # Setup
        page = mock_registry.create_page("Test Page")
        content = "Test content"
        mock_registry.save()
        mock_storage.write(page, content)

        # Mock client to return identical content (would normally skip)
        mock_client = Mock()
        mock_client.fetch_page.return_value = content
        mock_client.upload_page.return_value = {"newrevid": 123}

        uploader = PageUploader(mock_client)
        service = UploadService(uploader, mock_storage, mock_registry)

        # Execute upload with force=True
        events = list(
            service.upload_pages(
                page_titles=["Test Page"],
                summary="Test",
                minor=True,
                force=True,  # Force upload
            )
        )

        # Verify: Should be uploaded (not skipped)
        upload_events = [e for e in events if isinstance(e, PageUploaded)]
        assert len(upload_events) == 1
        assert upload_events[0].action == "uploaded"

        # Verify upload was called despite identical content
        mock_client.upload_page.assert_called_once()


class TestBatchLimitLogic:
    """Test batch limit doesn't count skipped pages."""

    def test_batch_limit_excludes_skips(
        self, mock_registry, mock_storage, mock_uploader
    ):
        """Batch limit should not count skipped pages."""
        # Setup: 3 pages - 1 will skip, 2 will upload
        pages = []
        for i in range(3):
            page = mock_registry.create_page(f"Page {i}")
            content = f"Content {i}"

            # Write content to disk first
            path = mock_storage.pages_dir / page.safe_filename
            path.write_text(content, encoding="utf-8")

            if i == 0:
                # First page: unchanged (will skip)
                content_hash = hashlib.sha256(content.encode()).hexdigest()
                page.updated_content_hash = content_hash
                page.last_pushed = datetime(2024, 1, 1, tzinfo=timezone.utc)
            else:
                # Other pages: changed (will upload)
                # Set an OLD hash so it appears changed
                page.updated_content_hash = "old_hash_that_doesnt_match"
                page.last_pushed = datetime(2024, 1, 1, tzinfo=timezone.utc)

            pages.append(page)

        mock_registry.save()

        # Mock uploader to return success for non-skipped pages
        def mock_upload(*args, **kwargs) -> Iterator[UploadResult]:
            for title, _ in args[0]:  # pages_with_content
                if "Page 0" not in title:  # Skip was already filtered out
                    yield UploadResult(
                        title=title,
                        success=True,
                        action="uploaded",
                        message="Success",
                        timestamp=datetime.now(timezone.utc),
                    )

        mock_uploader.upload_pages = mock_upload

        # Create service
        service = UploadService(mock_uploader, mock_storage, mock_registry)

        # Execute upload with batch_size=2
        # Should upload 2 pages even though 1 was skipped
        events = list(
            service.upload_pages(
                page_titles=["Page 0", "Page 1", "Page 2"],
                summary="Test",
                minor=True,
                force=False,
                batch_size=2,
            )
        )

        # Verify: 1 skip + 2 uploads
        complete_event = [e for e in events if isinstance(e, UploadComplete)][0]
        assert complete_event.skipped == 1
        assert complete_event.uploaded == 2
        assert complete_event.failed == 0

    def test_batch_limit_counts_failures(
        self, mock_registry, mock_storage, mock_uploader
    ):
        """Batch limit should count failed uploads."""
        # Setup: 3 pages that will all fail to load
        for i in range(3):
            mock_registry.create_page(f"Page {i}")
            # Don't write content - will fail

        mock_registry.save()

        # Create service
        service = UploadService(mock_uploader, mock_storage, mock_registry)

        # Execute upload with batch_size=2
        events = list(
            service.upload_pages(
                page_titles=["Page 0", "Page 1", "Page 2"],
                summary="Test",
                minor=True,
                force=False,
                batch_size=2,
            )
        )

        # Verify: Should stop after 2 failures
        complete_event = [e for e in events if isinstance(e, UploadComplete)][0]
        assert complete_event.failed == 2
        assert complete_event.uploaded == 0
        assert complete_event.skipped == 0


class TestTimestampUpdates:
    """Test last_pushed timestamp update behavior."""

    def test_timestamp_updated_on_upload(self, mock_registry, mock_storage):
        """last_pushed should be updated on successful upload."""
        # Setup
        page = mock_registry.create_page("Test Page")
        content = "Test content"
        mock_registry.save()
        mock_storage.write(page, content)

        # Mock client
        mock_client = Mock()
        mock_client.fetch_page.return_value = "different content"
        mock_client.upload_page.return_value = {"newrevid": 123}

        uploader = PageUploader(mock_client)
        service = UploadService(uploader, mock_storage, mock_registry)

        # Execute upload
        list(
            service.upload_pages(
                page_titles=["Test Page"],
                summary="Test",
                minor=True,
                force=False,
            )
        )

        # Verify: last_pushed was updated
        page_after = mock_registry.get_page_by_title("Test Page")
        assert page_after is not None
        assert page_after.last_pushed is not None

    def test_timestamp_updated_on_wiki_skip(self, mock_registry, mock_storage):
        """last_pushed should be updated on wiki-based skip."""
        # Setup
        page = mock_registry.create_page("Test Page")
        content = "Test content"
        page.last_pushed = None  # Not pushed yet
        mock_registry.save()
        mock_storage.write(page, content)

        # Mock client to return identical content
        mock_client = Mock()
        mock_client.fetch_page.return_value = content

        uploader = PageUploader(mock_client)
        service = UploadService(uploader, mock_storage, mock_registry)

        # Execute upload
        list(
            service.upload_pages(
                page_titles=["Test Page"],
                summary="Test",
                minor=True,
                force=False,
            )
        )

        # Verify: last_pushed was updated (wiki-based skip)
        page_after = mock_registry.get_page_by_title("Test Page")
        assert page_after is not None
        assert page_after.last_pushed is not None

    def test_timestamp_not_updated_on_local_skip(
        self, mock_registry, mock_storage, mock_uploader
    ):
        """last_pushed should NOT be updated on local-based skip."""
        # Setup
        page = mock_registry.create_page("Test Page")
        content = "Test content"
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        old_timestamp = datetime(2024, 1, 1, tzinfo=timezone.utc)
        page.updated_content_hash = content_hash
        page.last_pushed = old_timestamp
        mock_registry.save()
        mock_storage.write(page, content)

        # Create service
        service = UploadService(mock_uploader, mock_storage, mock_registry)

        # Execute upload
        list(
            service.upload_pages(
                page_titles=["Test Page"],
                summary="Test",
                minor=True,
                force=False,
            )
        )

        # Verify: last_pushed was NOT updated (local-based skip)
        page_after = mock_registry.get_page_by_title("Test Page")
        assert page_after is not None
        assert page_after.last_pushed == old_timestamp  # Unchanged
