from __future__ import annotations

from dataclasses import dataclass

__all__ = ["RenderedBlock"]


@dataclass(frozen=True)
class RenderedBlock:
    page_title: str
    block_id: str
    template_key: str
    text: str
