from __future__ import annotations

from typing import Any, cast

from erenshor.tools.wiki_cargo_probe.scenarios.lifecycle import LifecycleScenario, build_lifecycle_probe
from erenshor.tools.wiki_cargo_probe.scenarios.multi_entity import MultiEntityScenario, build_multi_entity_probe
from erenshor.tools.wiki_cargo_probe.scenarios.recreate_batching import (
    RecreateBatchingScenario,
    build_recreate_batching_probe,
)
from erenshor.tools.wiki_cargo_probe.scenarios.replacement_table import (
    ReplacementTableScenario,
    build_replacement_table_probe,
)
from erenshor.tools.wiki_cargo_probe.scenarios.standard import StandardProbeScenario, build_direct_probe


class BaseFakeContext:
    def __init__(self) -> None:
        self.events: list[tuple[Any, ...]] = []
        self.created_pages: list[str] = []

    def create_page(self, title: str, content: str) -> None:
        self.events.append(("create", title, content))
        self.created_pages.append(title)

    def create_template_pages(self, templates: tuple[Any, ...]) -> None:
        for template in templates:
            self.create_page(template.title, template.content)

    def recreate_tables(self, template: str, *, create_replacement: bool = False) -> dict[str, Any]:
        self.events.append(("recreate_tables", template, create_replacement))
        return {"ok": True, "template": template, "create_replacement": create_replacement}

    def recreate_data(self, template: str, table: str, *, replace_old_rows: bool = True) -> dict[str, Any]:
        self.events.append(("recreate_data", template, table, replace_old_rows))
        return {"ok": True, "template": template, "table": table, "replace_old_rows": replace_old_rows}

    def purge_pages(self, titles: list[str] | tuple[str, ...]) -> tuple[str, ...]:
        self.events.append(("purge", tuple(titles)))
        return tuple(titles)

    def purge_pages_in_batches(self, titles: tuple[str, ...], batch_size: int = 50) -> list[tuple[str, ...]]:
        purges: list[tuple[str, ...]] = []
        for start in range(0, len(titles), batch_size):
            batch = titles[start : start + batch_size]
            purges.append(self.purge_pages(batch))
        return purges

    def parse_page_html(self, page_title: str) -> dict[str, Any]:
        self.events.append(("parse", page_title))
        return {"ok": True, "contains_probe_text": False}

    def edit_existing_page(self, title: str, content: str, summary: str) -> None:
        self.events.append(("edit", title, content, summary))

    def delete_page(self, title: str) -> dict[str, Any]:
        self.events.append(("delete", title))
        return {"ok": True}

    def forget_created_page(self, title: str) -> None:
        self.events.append(("forget", title))
        self.created_pages.remove(title)

    def cleanup_created_pages(self) -> list[dict[str, Any]]:
        cleanups = []
        for title in reversed(self.created_pages):
            self.events.append(("cleanup", title))
            cleanups.append({"title": title, "result": {"ok": True}})
        return cleanups


class StandardFakeContext(BaseFakeContext):
    def __init__(self, candidate: StandardProbeScenario) -> None:
        super().__init__()
        self.candidate = candidate
        self.query_round = 0

    def query_cargo_table(
        self, *, tables: str, fields: str, where: str | None = None, limit: int = 50
    ) -> dict[str, Any]:
        del fields, where, limit
        table_name = next(name for name, table in self.candidate.tables.items() if table == tables)
        expected = self.candidate.expected_counts[table_name]
        self.events.append(("query", tables, self.query_round))
        rows = [] if self.query_round == 1 else [{"title": {"ProbeKey": self.candidate.key}}] * expected
        if table_name == "C":
            self.query_round += 1
        return {"ok": True, "rows": rows}


class LifecycleFakeContext(BaseFakeContext):
    def __init__(self, candidate: LifecycleScenario) -> None:
        super().__init__()
        self.candidate = candidate
        self.phase = "initial"

    def edit_existing_page(self, title: str, content: str, summary: str) -> None:
        super().edit_existing_page(title, content, summary)
        if summary.startswith("Reduce"):
            self.phase = "reduced"
        elif summary.startswith("Remove"):
            self.phase = "removed"

    def delete_page(self, title: str) -> dict[str, Any]:
        result = super().delete_page(title)
        self.phase = "deleted"
        return result

    def query_cargo_table(
        self, *, tables: str, fields: str, where: str | None = None, limit: int = 50
    ) -> dict[str, Any]:
        del limit
        self.events.append(("query", tables, fields, where, self.phase))
        if fields.startswith("_pageName=Page,StableKey"):
            key = self.candidate.item_key if self.candidate.item_key in str(where) else self.candidate.removed_key
            present = self.phase != "deleted" and (
                key == self.candidate.item_key or self.phase in {"initial", "reduced"}
            )
            rows = [{"title": {"Page": self.candidate.page_title, "StableKey": key}}] if present else []
            return {"ok": True, "rows": rows}
        if "SourceKey" in fields:
            key = self.candidate.item_key if self.candidate.item_key in str(where) else self.candidate.removed_key
            rows = self._source_rows(key)
            return {"ok": True, "rows": rows}
        if "UseKey" in fields:
            key = self.candidate.item_key if self.candidate.item_key in str(where) else self.candidate.removed_key
            rows = self._use_rows(key)
            return {"ok": True, "rows": rows}
        raise AssertionError(fields)

    def _source_rows(self, key: str) -> list[dict[str, Any]]:
        if self.phase == "deleted":
            sources: tuple[str, ...] = ()
        elif key == self.candidate.item_key:
            sources = ("SourceA1", "SourceA2", "SourceA3") if self.phase == "initial" else ("SourceA1",)
        elif self.phase in {"initial", "reduced"}:
            sources = ("SourceB1",)
        else:
            sources = ()
        return [{"title": {"Page": self.candidate.page_title, "SourceKey": source}} for source in sources]

    def _use_rows(self, key: str) -> list[dict[str, Any]]:
        if self.phase == "deleted":
            uses: tuple[str, ...] = ()
        elif key == self.candidate.item_key:
            uses = ("UseA1",) if self.phase == "initial" else ()
        elif self.phase in {"initial", "reduced"}:
            uses = ("UseB1",)
        else:
            uses = ()
        return [{"title": {"Page": self.candidate.page_title, "UseKey": use}} for use in uses]


class MultiEntityFakeContext(BaseFakeContext):
    def __init__(self, candidate: MultiEntityScenario) -> None:
        super().__init__()
        self.candidate = candidate

    def query_cargo_table(
        self, *, tables: str, fields: str, where: str | None = None, limit: int = 50
    ) -> dict[str, Any]:
        del limit
        self.events.append(("query", tables, fields, where))
        if fields.startswith("_pageName=Page,StableKey"):
            key = (
                self.candidate.item_keys[0]
                if self.candidate.item_keys[0] in str(where)
                else self.candidate.item_keys[1]
            )
            return {"ok": True, "rows": [{"title": {"Page": self.candidate.page_title, "StableKey": key}}]}
        if fields == "_pageName=Page,ItemKey,SourceKey,SourceIndex":
            key = (
                self.candidate.item_keys[0]
                if self.candidate.item_keys[0] in str(where)
                else self.candidate.item_keys[1]
            )
            return {
                "ok": True,
                "rows": [{"title": {"Page": self.candidate.page_title, "SourceKey": "SharedSource", "ItemKey": key}}],
            }
        if fields == "_pageName=Page,ItemKey,UseKey,UseIndex":
            key = (
                self.candidate.item_keys[0]
                if self.candidate.item_keys[0] in str(where)
                else self.candidate.item_keys[1]
            )
            return {
                "ok": True,
                "rows": [{"title": {"Page": self.candidate.page_title, "UseKey": "SharedUse", "ItemKey": key}}],
            }
        if "SourceKey=RelationshipKey" in fields or "UseKey=RelationshipKey" in fields:
            return {
                "ok": True,
                "rows": [
                    {"title": {"Page": self.candidate.page_title, "ItemKey": self.candidate.item_keys[1]}},
                    {"title": {"Page": self.candidate.page_title, "ItemKey": self.candidate.item_keys[0]}},
                ],
            }
        raise AssertionError(fields)


class RecreateBatchingFakeContext(BaseFakeContext):
    def __init__(self, candidate: RecreateBatchingScenario) -> None:
        super().__init__()
        self.candidate = candidate
        self.count_phase = len(candidate.page_titles)
        self.recreate_table_calls = 0

    def recreate_tables(self, template: str, *, create_replacement: bool = False) -> dict[str, Any]:
        self.recreate_table_calls += 1
        if self.recreate_table_calls > len(self.candidate.recreate_templates):
            self.count_phase = 0
        return super().recreate_tables(template, create_replacement=create_replacement)

    def recreate_data(self, template: str, table: str, *, replace_old_rows: bool = True) -> dict[str, Any]:
        self.count_phase = len(self.candidate.page_titles)
        return super().recreate_data(template, table, replace_old_rows=replace_old_rows)

    def query_cargo_table(
        self, *, tables: str, fields: str, where: str | None = None, limit: int = 50
    ) -> dict[str, Any]:
        del tables, limit
        self.events.append(("query", fields, where, self.count_phase))
        if fields == "COUNT(*)=Rows":
            return {"ok": True, "rows": [{"title": {"Rows": str(self.count_phase)}}]}
        if fields.startswith("_pageName=Page,StableKey"):
            key = self._key_from_where(where)
            return {"ok": True, "rows": [{"title": {"StableKey": key}}]}
        if "SourceKey" in fields:
            key = self._key_from_where(where)
            index = self.candidate.item_keys.index(key) + 1
            return {
                "ok": True,
                "rows": [{"title": {"SourceKey": self.candidate.prefix + "BatchSource" + str(index).zfill(4)}}],
            }
        if "UseKey" in fields:
            key = self._key_from_where(where)
            index = self.candidate.item_keys.index(key) + 1
            return {
                "ok": True,
                "rows": [{"title": {"UseKey": self.candidate.prefix + "BatchUse" + str(index).zfill(4)}}],
            }
        raise AssertionError(fields)

    def _key_from_where(self, where: str | None) -> str:
        text = str(where)
        for key in self.candidate.item_keys:
            if key in text:
                return key
        raise AssertionError(text)


class ReplacementTableFakeContext(BaseFakeContext):
    def __init__(self, candidate: ReplacementTableScenario) -> None:
        super().__init__()
        self.candidate = candidate

    def recreate_tables(self, template: str, *, create_replacement: bool = False) -> dict[str, Any]:
        self.events.append(("recreate_tables", template, create_replacement))
        return {
            "ok": True,
            "create_replacement": create_replacement,
            "response": {"success": True},
        }

    def query_cargo_table(
        self, *, tables: str, fields: str, where: str | None = None, limit: int = 50
    ) -> dict[str, Any]:
        del limit
        self.events.append(("query", tables, fields, where))
        if fields == "COUNT(*)=Rows":
            count = 0 if tables == self.candidate.replacement_table else 1
            return {"ok": True, "rows": [{"title": {"Rows": str(count)}}]}
        if fields == "_pageName=Page,ProbeKey,ProbeValue":
            if tables == self.candidate.replacement_table:
                return {"ok": True, "rows": []}
            return {
                "ok": True,
                "rows": [{"title": {"ProbeKey": self.candidate.key, "ProbeValue": "Original"}}],
            }
        raise AssertionError(fields)


def test_standard_runner_executes_direct_workflow() -> None:
    candidate = build_direct_probe("UnitProbe")
    context = StandardFakeContext(candidate)

    result = candidate.run(context, poll_seconds=17)

    assert result["validation_ok"] is True
    assert result["cargorecreatedata"] == [
        {"ok": True, "template": template, "table": table, "replace_old_rows": True}
        for template, table in candidate.recreatedata_pairs
    ]
    assert [event for event in context.events if event[0] == "cleanup"] == [
        ("cleanup", candidate.page_title),
        ("cleanup", "Template:CargoStorageProbe/UnitProbe/DirectCDeclare"),
        ("cleanup", "Template:CargoStorageProbe/UnitProbe/DirectBDeclare"),
        ("cleanup", "Template:CargoStorageProbe/UnitProbe/DirectMain"),
    ]


def test_lifecycle_runner_reduces_removes_and_forgets_deleted_page() -> None:
    candidate = build_lifecycle_probe("UnitProbe")
    context = LifecycleFakeContext(candidate)

    result = candidate.run(context, poll_seconds=19)

    assert result["validation_ok"] is True
    assert ("delete", candidate.page_title) in context.events
    assert ("forget", candidate.page_title) in context.events
    assert all(event != ("cleanup", candidate.page_title) for event in context.events)


def test_multi_entity_runner_validates_shared_reverse_relationships() -> None:
    candidate = build_multi_entity_probe("UnitProbe")
    context = MultiEntityFakeContext(candidate)

    result = candidate.run(context, poll_seconds=999)

    assert result["validation_ok"] is True
    assert result["item_keys"] == list(candidate.item_keys)
    assert [event for event in context.events if event[0] == "purge"] == [("purge", (candidate.page_title,))]
    assert [event for event in context.events if event[0] == "cleanup"] == [
        ("cleanup", candidate.page_title),
        ("cleanup", "Template:CargoStorageProbe/UnitProbeMultiEntity/LifecycleUsedInStore"),
        ("cleanup", "Template:CargoStorageProbe/UnitProbeMultiEntity/LifecycleObtainedFromStore"),
        ("cleanup", "Template:CargoStorageProbe/UnitProbeMultiEntity/LifecycleMain"),
        ("cleanup", "Module:CargoStorageProbe/UnitProbeMultiEntity/Lifecycle"),
    ]


def test_recreate_batching_runner_recreates_each_table_once_then_polls_expected_counts() -> None:
    candidate = build_recreate_batching_probe("UnitProbe", 2)
    context = RecreateBatchingFakeContext(candidate)

    result = candidate.run(context, poll_seconds=17)

    assert result["validation_ok"] is True
    assert result["cargorecreatedata"] == [
        {"ok": True, "template": template, "table": table, "replace_old_rows": True}
        for template, table in candidate.recreatedata_pairs
    ]
    assert [event for event in context.events if event[0] == "recreate_data"] == [
        ("recreate_data", template, table, True) for template, table in candidate.recreatedata_pairs
    ]
    typed_result = cast("dict[str, Any]", result)
    assert typed_result["initial_counts"]["matches"] is True
    assert typed_result["counts_after_cargorecreatetables"]["matches"] is True
    assert typed_result["counts_after_cargorecreatedata"]["matches"] is True


def test_replacement_table_runner_records_hidden_rows_before_switch_in() -> None:
    candidate = build_replacement_table_probe("UnitProbe")
    context = ReplacementTableFakeContext(candidate)

    result = candidate.run(context, poll_seconds=23)
    typed_result = cast("dict[str, Any]", result)

    assert result["validation_ok"] is True
    assert result["initial_cargorecreatetables"] == {
        "ok": True,
        "create_replacement": False,
        "response": {"success": True},
    }
    assert result["create_replacement"] == {
        "ok": True,
        "create_replacement": True,
        "response": {"success": True},
    }
    assert typed_result["initial_original_count"]["count"] == 1
    expected_original_row = {
        "ok": True,
        "rows": [{"title": {"ProbeKey": candidate.key, "ProbeValue": "Original"}}],
    }
    assert result["initial_original_row"] == expected_original_row
    assert typed_result["replacement_count"]["count"] == 0
    assert result["replacement_row"] == {"ok": True, "rows": []}
    assert result["replacement_queryable_before_switch"] is False
    assert result["replacement_rows_hidden_before_switch"] is True
    assert result["switch_in_automatable"] is False
    assert result["switch_in_note"] == (
        "Replacement population and switch-in are Special:CargoTables admin steps; "
        "not API-queryable or automatable before switch-in."
    )
    assert typed_result["original_after_replacement_count"]["count"] == 1
    assert result["original_after_replacement_row"] == expected_original_row
    assert result["switch_in_contract"] == "Special:CargoTables UI after replacement population completes"
    assert [event for event in context.events if event[0] == "create"] == [
        ("create", candidate.template.title, candidate.template.content),
        ("create", candidate.page_title, candidate.page_content),
    ]
    assert [event for event in context.events if event[0] == "recreate_tables"] == [
        ("recreate_tables", candidate.template_name, False),
        ("recreate_tables", candidate.template_name, True),
    ]
    assert [event for event in context.events if event[0] == "cleanup"] == [
        ("cleanup", candidate.page_title),
        ("cleanup", candidate.template.title),
    ]


def test_standard_runner_fails_closed_when_a_recreate_operation_fails() -> None:
    candidate = build_direct_probe("UnitProbe")

    class FailingRecreateContext(StandardFakeContext):
        def recreate_tables(self, template: str, *, create_replacement: bool = False) -> dict[str, Any]:
            super().recreate_tables(template, create_replacement=create_replacement)
            return {"ok": False, "template": template, "code": "internal_api_error"}

    result = candidate.run(FailingRecreateContext(candidate), poll_seconds=1)

    assert result["validation_ok"] is False


def test_standard_runner_fails_closed_when_purge_does_not_reach_the_page() -> None:
    candidate = build_direct_probe("UnitProbe")

    class MissingPurgeContext(StandardFakeContext):
        def purge_pages(self, titles: list[str] | tuple[str, ...]) -> tuple[str, ...]:
            super().purge_pages(titles)
            return ()

    result = candidate.run(MissingPurgeContext(candidate), poll_seconds=1)

    assert result["validation_ok"] is False
