"""Upload policy validation for safe wiki operations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Set

from erenshor.registry.core import WikiPage

__all__ = [
    "ConservativeUploadPolicy",
    "ProductionUploadPolicy",
    "UploadAction",
    "UploadPolicy",
    "UploadViolation",
    "load_upload_policy",
]


class UploadAction(Enum):
    """Types of upload actions that can be validated."""

    CREATE = "create"  # New page creation
    UPDATE = "update"  # Modify existing page
    DELETE = "delete"  # Page deletion
    SKIP = "skip"  # Skip upload (content identical)


@dataclass
class UploadViolation:
    """Represents a policy violation that prevents upload."""

    page: WikiPage
    violation_type: str
    message: str
    action: UploadAction

    def __str__(self) -> str:
        """Human-readable violation description."""
        return f"{self.action.value.title()} {self.page.title}: {self.message}"


class UploadPolicy:
    """Validation policies for safe wiki uploads."""

    def __init__(
        self,
        allow_page_creation: bool = False,
        allow_page_deletion: bool = False,
        max_pages_per_batch: int = 10,
        require_content_hash: bool = True,
        forbidden_namespaces: Optional[Set[int]] = None,
        forbidden_titles: Optional[Set[str]] = None,
        max_content_size: int = 1024 * 1024,  # 1MB
    ):
        """Initialize upload policy with safety defaults."""
        self.allow_page_creation = allow_page_creation
        self.allow_page_deletion = allow_page_deletion
        self.max_pages_per_batch = max_pages_per_batch
        self.require_content_hash = require_content_hash
        self.forbidden_namespaces = forbidden_namespaces or {
            8,
            10,
            14,
        }  # MediaWiki, Template, Category
        self.forbidden_titles = forbidden_titles or set()
        self.max_content_size = max_content_size

    def validate_upload(
        self,
        pages: List[WikiPage],
        content_by_page: dict[str, str],
        action: UploadAction = UploadAction.UPDATE,
    ) -> List[UploadViolation]:
        """Validate list of pages for upload, return violations."""
        violations: List[UploadViolation] = []

        # Check batch size limit
        if len(pages) > self.max_pages_per_batch:
            # Create a dummy violation for batch size
            first_page = pages[0] if pages else WikiPage("dummy", "0000001")
            violations.append(
                UploadViolation(
                    page=first_page,
                    violation_type="batch_size",
                    message=f"Batch size {len(pages)} exceeds limit of {self.max_pages_per_batch}",
                    action=action,
                )
            )

        for page in pages:
            violations.extend(
                self._validate_single_page(
                    page, content_by_page.get(page.title, ""), action
                )
            )

        return violations

    def _validate_single_page(
        self, page: WikiPage, content: str, action: UploadAction
    ) -> List[UploadViolation]:
        """Validate individual page for upload."""
        violations: List[UploadViolation] = []

        # Check action permissions
        if action == UploadAction.CREATE and not self.allow_page_creation:
            violations.append(
                UploadViolation(
                    page=page,
                    violation_type="creation_forbidden",
                    message="Page creation is not allowed by current policy",
                    action=action,
                )
            )

        if action == UploadAction.DELETE and not self.allow_page_deletion:
            violations.append(
                UploadViolation(
                    page=page,
                    violation_type="deletion_forbidden",
                    message="Page deletion is not allowed by current policy",
                    action=action,
                )
            )

        # Check namespace restrictions
        if page.namespace in self.forbidden_namespaces:
            violations.append(
                UploadViolation(
                    page=page,
                    violation_type="forbidden_namespace",
                    message=f"Namespace {page.namespace} is forbidden by policy",
                    action=action,
                )
            )

        # Check title restrictions
        if page.title in self.forbidden_titles:
            violations.append(
                UploadViolation(
                    page=page,
                    violation_type="forbidden_title",
                    message=f"Title '{page.title}' is forbidden by policy",
                    action=action,
                )
            )

        # Check content hash requirement
        if self.require_content_hash and not page.updated_content_hash:
            violations.append(
                UploadViolation(
                    page=page,
                    violation_type="missing_content_hash",
                    message="Page missing required content hash for safe upload",
                    action=action,
                )
            )

        # Check content size limits
        if len(content) > self.max_content_size:
            violations.append(
                UploadViolation(
                    page=page,
                    violation_type="content_too_large",
                    message=f"Content size {len(content)} bytes exceeds limit of {self.max_content_size}",
                    action=action,
                )
            )

        return violations


class ConservativeUploadPolicy(UploadPolicy):
    """Very restrictive policy for initial deployments."""

    def __init__(self) -> None:
        """Initialize with maximum safety restrictions."""
        super().__init__(
            allow_page_creation=False,
            allow_page_deletion=False,
            max_pages_per_batch=1,  # Only one page at a time
            require_content_hash=True,
            forbidden_namespaces={
                8,
                10,
                14,
                2,
                3,
                4,
                5,
                6,
                7,
            },  # Only allow main namespace
            max_content_size=512 * 1024,  # 512KB limit
        )


class ProductionUploadPolicy(UploadPolicy):
    """Balanced policy for production use."""

    def __init__(self) -> None:
        """Initialize with reasonable production restrictions."""
        super().__init__(
            allow_page_creation=True,
            allow_page_deletion=False,  # Still no deletion
            max_pages_per_batch=25,
            require_content_hash=True,
            forbidden_namespaces={8, 10, 14},  # MediaWiki, Template, Category
            max_content_size=2 * 1024 * 1024,  # 2MB limit
        )


def load_upload_policy(policy_name: str = "conservative") -> UploadPolicy:
    """Load upload policy by name."""
    from typing import Callable

    policies: dict[str, Callable[[], UploadPolicy]] = {
        "conservative": ConservativeUploadPolicy,
        "production": ProductionUploadPolicy,
        "permissive": lambda: UploadPolicy(
            allow_page_creation=True,
            allow_page_deletion=True,
            max_pages_per_batch=100,
            require_content_hash=False,
            forbidden_namespaces=set(),
        ),
    }

    if policy_name not in policies:
        raise ValueError(
            f"Unknown policy '{policy_name}'. Available: {list(policies.keys())}"
        )

    return policies[policy_name]()
