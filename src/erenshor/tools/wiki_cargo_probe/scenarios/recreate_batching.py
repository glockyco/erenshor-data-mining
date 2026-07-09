from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from ..markup import lifecycle_item_call
from ..models import OWNER, TemplatePage, manual_cleanup_urls
from ..queries import batch_sample_matches, query_batch_samples, wait_for_batch_counts
from .lifecycle import build_lifecycle_probe

if TYPE_CHECKING:
    from ..operations import ProbeRunContext


@dataclass(frozen=True, slots=True)
class RecreateBatchingScenario:
    kind: Literal["recreate-batching"]
    prefix: str
    page_titles: tuple[str, ...]
    page_contents: tuple[str, ...]
    template_base: str
    tables: dict[str, str]
    templates: tuple[TemplatePage, ...]
    recreate_templates: tuple[str, ...]
    recreatedata_pairs: tuple[tuple[str, str], ...]
    item_keys: tuple[str, ...]
    sample_item_keys: tuple[str, ...]

    @property
    def template_pages(self) -> tuple[TemplatePage, ...]:
        return self.templates

    @property
    def table_names(self) -> tuple[str, ...]:
        return tuple(self.tables.values())

    def run(self, context: ProbeRunContext, poll_seconds: int) -> dict[str, object]:
        expected_count = len(self.page_titles)
        result: dict[str, Any] = {
            "kind": self.kind,
            "page_count": expected_count,
            "sample_item_keys": list(self.sample_item_keys),
            "tables": self.tables,
            "manual_table_cleanup_urls": manual_cleanup_urls(tuple(self.tables.values())),
        }
        try:
            context.create_template_pages(self.templates)
            result["initial_cargorecreatetables"] = [
                context.recreate_tables(template) for template in self.recreate_templates
            ]
            for title, content in zip(self.page_titles, self.page_contents, strict=True):
                context.create_page(title, content)
            result["purged"] = context.purge_pages_in_batches(self.page_titles)
            result["initial_counts"] = wait_for_batch_counts(context, self, poll_seconds, expected_count)
            result["initial_sample_state"] = query_batch_samples(context, self)
            result["initial_samples_match"] = batch_sample_matches(self, result["initial_sample_state"])
            result["post_page_cargorecreatetables"] = [
                context.recreate_tables(template) for template in self.recreate_templates
            ]
            result["counts_after_cargorecreatetables"] = wait_for_batch_counts(context, self, poll_seconds, 0)
            result["cargorecreatedata"] = [
                context.recreate_data(template, table) for template, table in self.recreatedata_pairs
            ]
            result["counts_after_cargorecreatedata"] = wait_for_batch_counts(
                context, self, poll_seconds, expected_count
            )
            result["sample_state_after_cargorecreatedata"] = query_batch_samples(context, self)
            result["samples_after_cargorecreatedata_match"] = batch_sample_matches(
                self, result["sample_state_after_cargorecreatedata"]
            )
            result["validation_ok"] = (
                result["initial_counts"].get("matches")
                and result["initial_samples_match"]
                and result["counts_after_cargorecreatetables"].get("matches")
                and all(response.get("ok") for response in result["cargorecreatedata"])
                and result["counts_after_cargorecreatedata"].get("matches")
                and result["samples_after_cargorecreatedata_match"]
            )
        finally:
            result["page_cleanup"] = context.cleanup_created_pages()
        return result


def _batch_item_key(prefix: str, index: int) -> str:
    return prefix + "BatchItem" + str(index).zfill(4)


def _batch_source_key(prefix: str, index: int) -> str:
    return prefix + "BatchSource" + str(index).zfill(4)


def _batch_use_key(prefix: str, index: int) -> str:
    return prefix + "BatchUse" + str(index).zfill(4)


def _sample_batch_keys(item_keys: tuple[str, ...]) -> tuple[str, ...]:
    if len(item_keys) <= 2:
        return item_keys
    return (item_keys[0], item_keys[len(item_keys) // 2], item_keys[-1])


def batch_page_content(template_base: str, prefix: str, index: int) -> str:
    return (
        lifecycle_item_call(
            template_base,
            _batch_item_key(prefix, index),
            "Batch Item " + str(index).zfill(4),
            (_batch_source_key(prefix, index),),
            (_batch_use_key(prefix, index),),
        )
        + "\n"
    )


def build_recreate_batching_probe(prefix: str, page_count: int) -> RecreateBatchingScenario:
    if page_count < 1:
        raise ValueError("page_count must be at least 1")
    storage = build_lifecycle_probe(prefix + "Batch")
    page_titles = tuple(
        "User:" + OWNER + "/CargoStorageProbe/" + prefix + "/RecreateBatching/Page" + str(index).zfill(4)
        for index in range(1, page_count + 1)
    )
    item_keys = tuple(_batch_item_key(prefix, index) for index in range(1, page_count + 1))
    page_contents = tuple(
        batch_page_content(storage.template_base, prefix, index) for index in range(1, page_count + 1)
    )
    return RecreateBatchingScenario(
        kind="recreate-batching",
        prefix=prefix,
        page_titles=page_titles,
        page_contents=page_contents,
        template_base=storage.template_base,
        tables=storage.tables,
        templates=storage.templates,
        recreate_templates=storage.recreate_templates,
        recreatedata_pairs=storage.recreatedata_pairs,
        item_keys=item_keys,
        sample_item_keys=_sample_batch_keys(item_keys),
    )
