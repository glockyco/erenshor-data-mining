"""Behavioral contracts for approval, ordering, failure propagation, and recovery."""

from __future__ import annotations

import json
import sqlite3
import tomllib
from pathlib import Path
from typing import Any, ClassVar

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from erenshor.application.publish import coordinator
from erenshor.application.publish.models import (
    PublishError,
    PublishSelection,
    SurfaceUncertainError,
    canonical,
    sha256,
)
from erenshor.cli.context import CLIContext
from erenshor.infrastructure.config.schema import Config


class RejectedError(RuntimeError):
    evidence: ClassVar[dict[str, bool]] = {"safe_to_resume": True}


class RecordedProvider:
    """Disposable provider state with explicit revision and rejection behavior."""

    def __init__(self) -> None:
        self.state: dict[str, dict[str, Any]] = {}
        self.writes: list[str] = []
        self.fail: str | None = None
        self.uncertain: str | None = None
        self.check_failure: str | None = None
        self.reconciled: list[str] = []
        self.initial_batches = 0
        self.resume_batches = 0

    def prepare(self, ctx: CLIContext, selection: dict[str, Any], run_dir: Path) -> list[dict[str, Any]]:
        del run_dir
        targets = [("map", target) for target in selection.get("targets", [])]
        if selection.get("tabs"):
            targets.append(("sheet", ctx.config.variants[ctx.variant].google_sheets.spreadsheet_id))
        targets += [
            ("wiki_repo", title) for title in selection.get("repo_titles", []) + selection.get("data_titles", [])
        ]
        targets += [("wiki_article", title) for title in selection.get("article_titles", [])]
        operations = []
        for kind, target in targets:
            key = f"{kind}:{target}"
            base = self.state.setdefault(key, {"revision": 1, "text": "old"})
            operations.append(
                {
                    "id": key,
                    "kind": kind,
                    "target": target,
                    "dependencies": [],
                    "payload": {
                        "text": "reviewed " + target,
                        "rows": [["Name", "Chance"], [target, 0.5]],
                        "requests": [{"updateTable": {"tableId": "existing"}}],
                        "tabs": [{"sheet_name": tab, "rows": [[tab, 0.5]]} for tab in selection.get("tabs", [])],
                    },
                    "expected_base": dict(base),
                    "recovery": "Retain provider preimage. No cross-service rollback.",
                    "inputs": [],
                    "destination": {"service": target},
                }
            )
        return operations

    def check(
        self, ctx: CLIContext, operation: dict[str, Any], payload: dict[str, Any], receipts: dict[str, Any]
    ) -> None:
        del ctx, payload, receipts
        if operation["id"] == self.check_failure:
            raise PublishError("Live catalog is stale")
        if self.state[operation["id"]] != operation["expected_base"]:
            raise PublishError("Editor revision changed")

    def check_many(self, ctx, operations, receipts):
        self.initial_batches += 1
        for operation, payload in operations:
            try:
                self.check(ctx, operation, payload, receipts)
            except Exception as error:
                error.operation_id = operation["id"]
                raise

    def reconcile_many(self, ctx, operations, receipts):
        self.resume_batches += 1
        for operation, payload, receipt in operations:
            self.reconcile(ctx, operation, payload, receipt, receipts)

    def execute(
        self, ctx: CLIContext, operation: dict[str, Any], payload: dict[str, Any], receipts: dict[str, Any]
    ) -> dict[str, Any]:
        del ctx, receipts
        key = operation["id"]
        if key == self.fail:
            raise RejectedError("Provider rejected operation before writing")
        self.writes.append(key)
        self.state[key] = {"revision": 2, "text": payload["text"]}
        if key == self.uncertain:
            raise SurfaceUncertainError("Accepted write but response was lost", {"request": key})
        return dict(self.state[key])

    def reconcile(
        self,
        ctx: CLIContext,
        operation: dict[str, Any],
        payload: dict[str, Any],
        receipt: dict[str, Any],
        receipts: dict[str, Any],
    ) -> None:
        del ctx, payload, receipts
        self.reconciled.append(operation["id"])
        if self.state[operation["id"]] != receipt:
            raise PublishError("Completed destination changed after its receipt")


@pytest.fixture
def publication(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[CLIContext, RecordedProvider, Path]:
    root = Path(__file__).resolve().parents[2]
    config = Config.model_validate(tomllib.loads((root / "config.toml").read_text()))
    config.variants["main"].google_sheets.spreadsheet_id = "fixture-spreadsheet"
    (tmp_path / "src" / "erenshor").mkdir(parents=True)
    (tmp_path / "src" / "erenshor" / "publisher.py").write_text("reviewed code\n")
    database = tmp_path / "variants" / "main" / "erenshor-main.sqlite"
    database.parent.mkdir(parents=True)
    with sqlite3.connect(database) as connection:
        connection.executescript(
            "CREATE TABLE items (id INTEGER); INSERT INTO items VALUES (1);"
            "CREATE TABLE code_facts_meta (game_build_id TEXT);"
            "INSERT INTO code_facts_meta VALUES ('fixture-build');"
        )
    ctx = CLIContext(config=config, variant="main", dry_run=False, repo_root=tmp_path)
    provider = RecordedProvider()
    monkeypatch.setattr(coordinator, "_surface", lambda kind: provider)
    return ctx, provider, database.parent


def selected(**surfaces: Any) -> PublishSelection:
    return PublishSelection.model_validate({"schema_version": 1, "summary": "Refresh selected sources", **surfaces})


def prepare(publication: tuple[CLIContext, RecordedProvider, Path], selection: PublishSelection, name: str = "run"):
    ctx, provider, root = publication
    plan = coordinator.prepare_publish(selection, ctx, root / name)
    return ctx, provider, plan, root / name / "plan.json"


@pytest.mark.parametrize(
    "extra",
    [
        {},
        {"maps": {"targets": []}},
        {"maps": {"targets": ["all"]}},
        {"maps": {"targets": ["canonical", "canonical"]}},
        {"sheets": {"tabs": ["items", "items"]}},
        {"wiki": {"repo_titles": ["Template:Item"]}},
        {"wiki": {"repo_titles": ["Module:X"], "article_titles": ["Module:X"]}},
        {"wiki": {"page_edits_file": "/tmp/edits.toml"}},
        {"wiki": {"repo_titles": ["Module:X"], "accept_drift": ["Module:Y"]}},
        {"commands": ["anything"]},
    ],
)
def test_selection_rejects_unbounded_or_ambiguous_input(extra: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        selected(**extra)


def test_maps_only_does_not_expand_other_surfaces(publication) -> None:
    ctx, provider, plan, path = prepare(publication, selected(maps={"targets": ["canonical"]}))
    assert [op.id for op in plan.operations] == ["map:canonical"]
    assert provider.writes == []
    report = coordinator.inspect_publish(path, ctx)
    assert report["operations"][0]["payload"]["text"] == "reviewed canonical"
    assert not (path.parent / "journal.jsonl").exists()


def test_equivalent_input_order_produces_identical_digest(publication) -> None:
    ctx, _, root = publication
    first = coordinator.prepare_publish(selected(sheets={"tabs": ["items", "spells"]}), ctx, root / "first")
    second = coordinator.prepare_publish(selected(sheets={"tabs": ["spells", "items"]}), ctx, root / "second")
    assert first.digest == second.digest
    assert [op.id for op in first.operations] == ["sheet:fixture-spreadsheet"]
    payload = coordinator.payload_for(first.operations[0], ctx, root / "first")
    assert [tab["sheet_name"] for tab in payload["tabs"]] == ["items", "spells"]


def test_exact_sheet_wire_body_has_reviewable_hash_bound_sidecar(publication, monkeypatch) -> None:
    ctx, provider, root = publication
    prepare_surface = provider.prepare
    body = b'{"requests":[{"updateCells":{"start":{"sheetId":7},"rows":[]}}]}'
    body_digest = sha256(body)

    def with_wire_body(ctx, selection, run_dir):
        drafts = prepare_surface(ctx, selection, run_dir)
        drafts[0]["payload"].update(
            batch_body=body.decode("utf-8"),
            batch_body_sha256=body_digest,
            batch_body_bytes=len(body),
        )
        return drafts

    monkeypatch.setattr(provider, "prepare", with_wire_body)
    plan = coordinator.prepare_publish(selected(sheets={"tabs": ["items"]}), ctx, root / "wire-body")
    run_dir = root / "wire-body"
    operation = plan.operations[0]
    payload = coordinator.payload_for(operation, ctx, run_dir)
    sidecar = Path(payload["batch_body_path"])
    assert sidecar.read_bytes() == body
    assert sidecar.name == f"{body_digest}.batch.json"
    assert operation.inputs[f"$RUN/payloads/{sidecar.name}"] == body_digest
    assert (run_dir / "review-summary.json").exists()
    sidecar.write_bytes(body + b"\n")
    with pytest.raises(PublishError):
        coordinator.apply_publish(run_dir / "plan.json", plan.digest, ctx)
    assert provider.writes == []


@pytest.mark.parametrize("surface", ["wiki", "maps", "sheets"])
def test_review_never_discloses_url_credentials(publication, surface: str) -> None:
    ctx, provider, root = publication
    secret_url = "https://review-user:private-review-secret@fixture.invalid/api.php"
    if surface == "wiki":
        ctx.config.global_.mediawiki.api_url = secret_url
        selection = selected(wiki={"data_titles": ["Module:Erenshor/Data/Links"]})
    elif surface == "maps":
        ctx.config.variants[ctx.variant].maps.legacy_base_url = secret_url
        selection = selected(maps={"targets": ["legacy"]})
    else:
        ctx.config.variants[ctx.variant].maps.base_url = secret_url
        selection = selected(sheets={"tabs": ["items"]})
    with pytest.raises(PublishError) as failure:
        coordinator.prepare_publish(selection, ctx, root / "secret-url")
    assert "private-review-secret" not in str(failure.value)
    assert "review-user" not in str(failure.value)
    assert not (root / "secret-url").exists()
    assert provider.writes == []


def test_missing_approval_never_writes(publication) -> None:
    ctx, provider, _, path = prepare(publication, selected(maps={"targets": ["canonical"]}))
    with pytest.raises(PublishError, match="human approval"):
        coordinator.apply_publish(path, None, ctx)
    assert provider.writes == []
    assert not (path.parent / "journal.jsonl").exists()


@pytest.mark.parametrize("change", ["database", "source", "config", "payload", "payload_whitespace", "plan"])
def test_changed_reviewed_inputs_refuse_before_any_write(publication, change: str) -> None:
    ctx, provider, plan, path = prepare(publication, selected(sheets={"tabs": ["items"]}))
    if change == "database":
        with sqlite3.connect(ctx.config.variants["main"].resolved_database(ctx.repo_root)) as connection:
            connection.execute("INSERT INTO items VALUES (2)")
    elif change == "source":
        (ctx.repo_root / "src" / "erenshor" / "publisher.py").write_text("changed code\n")
    elif change == "config":
        ctx.config.variants["main"].google_sheets.spreadsheet_id = "different-destination"
    elif change in {"payload", "payload_whitespace"}:
        payload = path.parent / plan.operations[0].payload_path
        payload.write_bytes(payload.read_bytes() + b" " if change == "payload_whitespace" else b'{"text":"tampered"}')
    else:
        value = json.loads(path.read_bytes())
        value["operations"][0]["destination"] = {"service": "other"}
        path.write_bytes(canonical(value))
    with pytest.raises(PublishError):
        coordinator.apply_publish(path, plan.digest, ctx)
    assert provider.writes == []


def test_stale_catalog_blocks_every_surface_before_mutation(publication) -> None:
    ctx, provider, plan, path = prepare(
        publication,
        selected(wiki={"article_titles": ["Item"]}, maps={"targets": ["canonical"]}, sheets={"tabs": ["items"]}),
    )
    provider.check_failure = "wiki_article:Item"
    with pytest.raises(PublishError, match="catalog"):
        coordinator.apply_publish(path, plan.digest, ctx)
    assert provider.writes == []


def test_middle_failure_blocks_unrelated_later_operations_and_resume_narrows(publication) -> None:
    ctx, provider, plan, path = prepare(
        publication,
        selected(
            wiki={"repo_titles": ["Module:X"], "article_titles": ["Item"]},
            maps={"targets": ["canonical"]},
            sheets={"tabs": ["items"]},
        ),
    )
    provider.fail = "wiki_article:Item"
    with pytest.raises(PublishError, match="stopped at wiki_article:Item"):
        coordinator.apply_publish(path, plan.digest, ctx)
    assert provider.writes == ["wiki_repo:Module:X"]
    status = coordinator.status_publish(path, ctx)
    assert [op["state"] for op in status["operations"]] == ["succeeded", "failed", "blocked", "blocked"]
    provider.fail = None
    coordinator.resume_publish(path, plan.digest, ctx)
    assert provider.writes == ["wiki_repo:Module:X", "wiki_article:Item", "map:canonical", "sheet:fixture-spreadsheet"]
    assert all(op["state"] == "succeeded" for op in coordinator.status_publish(path, ctx)["operations"])


def test_canonical_success_legacy_failure_resumes_only_legacy(publication) -> None:
    ctx, provider, plan, path = prepare(publication, selected(maps={"targets": ["legacy", "canonical"]}))
    provider.fail = "map:legacy"
    with pytest.raises(PublishError):
        coordinator.apply_publish(path, plan.digest, ctx)
    provider.fail = None
    coordinator.resume_publish(path, plan.digest, ctx)
    assert provider.writes == ["map:canonical", "map:legacy"]


@pytest.mark.parametrize("changed", ["completed", "remaining"])
def test_resume_refuses_editor_changes_without_overwriting(publication, changed: str) -> None:
    ctx, provider, plan, path = prepare(publication, selected(wiki={"repo_titles": ["Module:A", "Module:B"]}))
    provider.fail = "wiki_repo:Module:B"
    with pytest.raises(PublishError):
        coordinator.apply_publish(path, plan.digest, ctx)
    key = "wiki_repo:Module:A" if changed == "completed" else "wiki_repo:Module:B"
    provider.state[key] = {"revision": 99, "text": "editor's text"}
    provider.fail = None
    with pytest.raises(PublishError, match="changed"):
        coordinator.resume_publish(path, plan.digest, ctx)
    assert provider.writes == ["wiki_repo:Module:A"]


def test_lost_receipt_stays_uncertain_and_is_never_retried(publication) -> None:
    ctx, provider, plan, path = prepare(publication, selected(sheets={"tabs": ["items", "spells"]}))
    provider.uncertain = "sheet:fixture-spreadsheet"
    with pytest.raises(PublishError):
        coordinator.apply_publish(path, plan.digest, ctx)
    assert [op["state"] for op in coordinator.status_publish(path, ctx)["operations"]] == ["uncertain"]
    with pytest.raises(PublishError, match="uncertain"):
        coordinator.resume_publish(path, plan.digest, ctx)
    assert provider.writes == ["sheet:fixture-spreadsheet"]


def test_durable_unacknowledged_intent_prevents_retry(publication) -> None:
    ctx, provider, plan, path = prepare(publication, selected(maps={"targets": ["canonical"]}))
    journal = coordinator.Journal(path.parent / "journal.jsonl", plan.digest)
    journal.append("map:canonical", "running", payload_sha256=plan.operations[0].payload_sha256)
    with pytest.raises(PublishError, match="uncertain"):
        coordinator.resume_publish(path, plan.digest, ctx)
    assert provider.writes == []


def test_cli_harmless_prepare_and_review_use_real_coordinator(publication) -> None:
    from erenshor.cli.commands.publish import app

    ctx, provider, root = publication
    selection = root / "selection.toml"
    selection.write_text('schema_version = 1\nsummary = "Review items"\n[sheets]\ntabs = ["items"]\n')
    runner = CliRunner()
    result = runner.invoke(app, ["prepare", "--selection", str(selection), "--output", str(root / "cli-run")], obj=ctx)
    assert result.exit_code == 0, result.output
    path = root / "cli-run" / "plan.json"
    assert path.exists()
    ctx.dry_run = True
    review = runner.invoke(app, ["apply", str(path)], obj=ctx)
    assert review.exit_code == 0, review.output
    assert '"rows"' in review.output
    assert '"requests"' in review.output
    assert provider.writes == []
    assert not (path.parent / "journal.jsonl").exists()
    selection.write_text('schema_version = 1\nsummary = "Changed review"\n[sheets]\ntabs = ["spells"]\n')
    stale = runner.invoke(app, ["apply", str(path)], obj=ctx)
    assert stale.exit_code == 1
    assert "Selection changed" in stale.output


@pytest.mark.parametrize(
    "failure",
    [
        "wiki_repo:Module:X",
        "wiki_article:Item",
        "map:canonical",
        "map:legacy",
        "sheet:fixture-spreadsheet",
    ],
)
def test_every_stage_boundary_stops_later_writes(publication, failure: str) -> None:
    ctx, provider, plan, path = prepare(
        publication,
        selected(
            wiki={"repo_titles": ["Module:X"], "article_titles": ["Item"]},
            maps={"targets": ["canonical", "legacy"]},
            sheets={"tabs": ["items", "spells"]},
        ),
    )
    provider.fail = failure
    with pytest.raises(PublishError, match="Publication stopped"):
        coordinator.apply_publish(path, plan.digest, ctx)
    ordered = [operation.id for operation in plan.operations]
    assert provider.writes == ordered[: ordered.index(failure)]
    status = coordinator.status_publish(path, ctx)
    assert status["operations"][ordered.index(failure)]["state"] == "failed"
    assert all(operation["state"] == "blocked" for operation in status["operations"][ordered.index(failure) + 1 :])


def test_process_lock_prevents_second_executor(publication) -> None:
    ctx, provider, plan, path = prepare(publication, selected(maps={"targets": ["canonical"]}))
    with coordinator._lock(path.parent), pytest.raises(PublishError, match="local executor"):
        coordinator.apply_publish(path, plan.digest, ctx)
    assert provider.writes == []


def test_incomplete_journal_is_not_treated_as_no_execution(publication) -> None:
    ctx, provider, plan, path = prepare(publication, selected(sheets={"tabs": ["items"]}))
    (path.parent / "journal.jsonl").write_bytes(b'{"operation":"sheet:items"')
    with pytest.raises(PublishError, match="incomplete record"):
        coordinator.resume_publish(path, plan.digest, ctx)
    assert provider.writes == []


def test_interrupted_mutation_is_uncertain_and_blocks_later_work(publication, monkeypatch) -> None:
    ctx, provider, plan, path = prepare(
        publication, selected(wiki={"repo_titles": ["Module:A"]}, sheets={"tabs": ["items", "spells"]})
    )

    def interrupted(*args, **kwargs):
        raise KeyboardInterrupt()

    monkeypatch.setattr(provider, "execute", interrupted)
    with pytest.raises(PublishError):
        coordinator.apply_publish(path, plan.digest, ctx)
    assert [operation["state"] for operation in coordinator.status_publish(path, ctx)["operations"]] == [
        "uncertain",
        "blocked",
    ]
    assert provider.writes == []


def test_input_changes_after_article_success_block_maps_and_sheets(publication, monkeypatch) -> None:
    ctx, provider, plan, path = prepare(
        publication,
        selected(
            wiki={"article_titles": ["Item"]},
            maps={"targets": ["canonical"]},
            sheets={"tabs": ["items"]},
        ),
    )
    execute = provider.execute

    def edit_after_article(context, operation, payload, receipts):
        receipt = execute(context, operation, payload, receipts)
        if operation["kind"] == "wiki_article":
            (ctx.repo_root / "src" / "erenshor" / "publisher.py").write_text("changed after article\n")
        return receipt

    monkeypatch.setattr(provider, "execute", edit_after_article)
    with pytest.raises(PublishError, match="Pinned input changed"):
        coordinator.apply_publish(path, plan.digest, ctx)
    assert provider.writes == ["wiki_article:Item"]
    assert [operation["state"] for operation in coordinator.status_publish(path, ctx)["operations"]] == [
        "succeeded",
        "failed",
        "blocked",
    ]


def test_configuration_source_changes_are_seen_between_operations(publication) -> None:
    ctx, provider, plan, path = prepare(publication, selected(sheets={"tabs": ["items"]}))
    (ctx.repo_root / "config.toml").write_text('[variants.main.google_sheets]\nspreadsheet_id = "changed"\n')
    with pytest.raises(PublishError, match="configuration"):
        coordinator.apply_publish(path, plan.digest, ctx)
    assert provider.writes == []


def test_empty_sections_do_not_add_surface_operations() -> None:
    selection = selected(wiki={}, maps={"targets": ["canonical"]}, sheets={})
    assert selection.wiki is None
    assert selection.sheets is None
    assert selection.maps.targets == ["canonical"]


def test_operation_order_refuses_missing_explicit_dependencies(publication) -> None:
    _, _, plan, _ = prepare(publication, selected(maps={"targets": ["canonical"]}))
    plan.operations[0].dependencies = ["wiki_repo:Module:Erenshor/Data/Links"]
    with pytest.raises(PublishError, match="explicitly selected"):
        coordinator.order_operations(plan.operations)


def test_operation_order_refuses_cycles(publication) -> None:
    _, _, plan, _ = prepare(publication, selected(wiki={"repo_titles": ["Module:A", "Module:B"]}))
    first, second = plan.operations
    first.dependencies = [second.id]
    second.dependencies = [first.id]
    with pytest.raises(PublishError, match="Cyclic"):
        coordinator.order_operations(plan.operations)


def test_secret_changes_do_not_enter_configuration_hashes(publication) -> None:
    ctx, _, root = publication
    local = ctx.repo_root / ".erenshor" / "config.local.toml"
    local.parent.mkdir()
    local.write_text('[global.mediawiki]\nbot_username = "Publisher@Bot"\nbot_password = "first-secret"\n')
    selection = selected(wiki={"repo_titles": ["Module:X"]})
    first = coordinator.prepare_publish(selection, ctx, root / "first-secret")
    local.write_text('[global.mediawiki]\nbot_username = "Publisher@Bot"\nbot_password = "different-secret"\n')
    second = coordinator.prepare_publish(selection, ctx, root / "second-secret")
    assert first.digest == second.digest
    assert b"first-secret" not in canonical(first.model_dump(mode="json"))
    assert b"different-secret" not in canonical(second.model_dump(mode="json"))


def test_atomic_selected_tabs_are_one_failed_operation_without_partial_tab_success(publication) -> None:
    ctx, provider, plan, path = prepare(publication, selected(sheets={"tabs": ["items", "spells"]}))
    assert len(plan.operations) == 1
    provider.fail = "sheet:fixture-spreadsheet"
    with pytest.raises(PublishError):
        coordinator.apply_publish(path, plan.digest, ctx)
    assert provider.writes == []
    assert [operation["state"] for operation in coordinator.status_publish(path, ctx)["operations"]] == ["failed"]
    provider.fail = None
    coordinator.resume_publish(path, plan.digest, ctx)
    assert provider.writes == ["sheet:fixture-spreadsheet"]


@pytest.mark.parametrize("literal", ["$RUN/example", "$REPO/wiki", "/absolute/literal"])
def test_opaque_payload_strings_are_never_path_expanded(publication, monkeypatch, literal: str) -> None:
    ctx, provider, root = publication
    native_prepare = provider.prepare

    def with_literals(context, selection, run_dir):
        drafts = native_prepare(context, selection, run_dir)
        for draft in drafts:
            draft["payload"].update(
                text=literal,
                content=literal,
                original=literal,
                summary=literal,
                rows=[[literal, "$RUN/other", "$REPO/other"]],
            )
        return drafts

    monkeypatch.setattr(provider, "prepare", with_literals)
    plan = coordinator.prepare_publish(selected(sheets={"tabs": ["items"]}), ctx, root / "opaque")
    payload = coordinator.payload_for(plan.operations[0], ctx, root / "opaque")
    assert payload["text"] == literal
    assert payload["content"] == literal
    assert payload["original"] == literal
    assert payload["summary"] == literal
    assert payload["rows"] == [[literal, "$RUN/other", "$REPO/other"]]
    coordinator.apply_publish(root / "opaque" / "plan.json", plan.digest, ctx)
    assert provider.state["sheet:fixture-spreadsheet"]["text"] == literal


def test_copied_plan_cannot_execute_inside_tracked_wiki_sources(publication) -> None:
    import shutil

    ctx, provider, plan, path = prepare(publication, selected(wiki={"repo_titles": ["Module:X"]}))
    forbidden = ctx.repo_root / "wiki" / "publication-run"
    shutil.copytree(path.parent, forbidden)
    with pytest.raises(PublishError, match=r"variant storage|tracked wiki"):
        coordinator.apply_publish(forbidden / "plan.json", plan.digest, ctx)
    assert provider.writes == []
    assert not (forbidden / "execution.lock").exists()


def test_nested_native_output_symlink_is_rejected_before_mutation(publication, monkeypatch) -> None:
    ctx, provider, root = publication
    native_prepare = provider.prepare

    def with_manifest(context, selection, run_dir):
        drafts = native_prepare(context, selection, run_dir)
        for draft in drafts:
            draft["payload"]["native_manifest"] = str(run_dir / "wiki" / "deploys" / "manifest.json")
        return drafts

    monkeypatch.setattr(provider, "prepare", with_manifest)
    plan = coordinator.prepare_publish(selected(wiki={"repo_titles": ["Module:X"]}), ctx, root / "symlink")
    run_dir = root / "symlink"
    (run_dir / "wiki").mkdir()
    foreign = ctx.repo_root / "foreign-checkout"
    (foreign / ".git").mkdir(parents=True)
    (run_dir / "wiki" / "deploys").symlink_to(foreign, target_is_directory=True)
    with pytest.raises(PublishError, match=r"cross-checkout|escapes approved"):
        coordinator.apply_publish(run_dir / "plan.json", plan.digest, ctx)
    assert provider.writes == []
    assert sorted(path.name for path in foreign.iterdir()) == [".git"]


def test_execution_lock_symlink_cannot_write_outside_run(publication) -> None:
    ctx, provider, plan, path = prepare(publication, selected(sheets={"tabs": ["items"]}))
    foreign = ctx.repo_root / "foreign-lock"
    foreign.write_text("untouched")
    (path.parent / "execution.lock").symlink_to(foreign)
    with pytest.raises(PublishError, match="escapes approved"):
        coordinator.apply_publish(path, plan.digest, ctx)
    assert foreign.read_text() == "untouched"
    assert provider.writes == []


def test_normal_apply_reconciles_only_each_written_page_and_hashes_sources_once(publication, monkeypatch) -> None:
    ctx, provider, root = publication
    titles = [f"Module:Page{index:03}" for index in range(80)]
    plan = coordinator.prepare_publish(selected(wiki={"repo_titles": titles}), ctx, root / "linear")
    source = ctx.repo_root / "src" / "erenshor" / "publisher.py"
    byte_reads = []
    native_hash = coordinator.file_sha256

    def record_hash(path):
        byte_reads.append(path)
        return native_hash(path)

    monkeypatch.setattr(coordinator, "file_sha256", record_hash)
    coordinator.apply_publish(root / "linear" / "plan.json", plan.digest, ctx)
    assert len(provider.reconciled) == len(titles)
    assert provider.resume_batches == 0
    assert provider.initial_batches == 1
    assert byte_reads.count(source) == 1


def test_preparation_fingerprints_shared_input_once_per_guard_window(publication, monkeypatch) -> None:
    ctx, provider, root = publication
    source = ctx.repo_root / "src" / "erenshor" / "publisher.py"
    native_prepare = provider.prepare

    def with_shared_input(context, selection, run_dir):
        drafts = native_prepare(context, selection, run_dir)
        for draft in drafts:
            draft["inputs"] = [str(source)]
        return drafts

    monkeypatch.setattr(provider, "prepare", with_shared_input)
    native_fingerprint = coordinator._fingerprint
    fingerprints = []

    def record_fingerprint(path):
        fingerprints.append(path)
        return native_fingerprint(path)

    monkeypatch.setattr(coordinator, "_fingerprint", record_fingerprint)
    coordinator.prepare_publish(
        selected(wiki={"repo_titles": [f"Module:Page{index}" for index in range(40)]}), ctx, root / "deduplicated"
    )
    assert fingerprints.count(source) == 2


def test_changed_seal_refuses_same_size_mutation_with_restored_mtime(publication, monkeypatch) -> None:
    import os

    ctx, provider, plan, path = prepare(publication, selected(wiki={"repo_titles": ["Module:A", "Module:B"]}))
    source = ctx.repo_root / "src" / "erenshor" / "publisher.py"
    before = source.stat()
    native_execute = provider.execute

    def mutate_source(context, operation, payload, receipts):
        receipt = native_execute(context, operation, payload, receipts)
        if operation["target"] == "Module:A":
            data = source.read_bytes()
            source.write_bytes(bytes([data[0] ^ 1]) + data[1:])
            os.utime(source, ns=(before.st_atime_ns, before.st_mtime_ns))
        return receipt

    monkeypatch.setattr(provider, "execute", mutate_source)
    with pytest.raises(PublishError, match="Pinned input changed"):
        coordinator.apply_publish(path, plan.digest, ctx)
    assert provider.writes == ["wiki_repo:Module:A"]


def test_finalizing_preparation_cannot_recapture_changed_separate_review_input(publication, monkeypatch) -> None:
    import hashlib

    ctx, provider, root = publication
    prose_file = root / "wiki" / "reviewed.toml"
    prose_file.parent.mkdir()
    prose_file.write_bytes(b"separately reviewed bytes")
    reviewed_digest = hashlib.sha256(prose_file.read_bytes()).hexdigest()
    native_prepare = provider.prepare

    def replace_after_review(context, selection, run_dir):
        drafts = native_prepare(context, selection, run_dir)
        for draft in drafts:
            draft["inputs"] = [str(prose_file)]
            draft["input_sha256"] = {str(prose_file): reviewed_digest}
        prose_file.write_bytes(b"unreviewed replacement bytes")
        return drafts

    monkeypatch.setattr(provider, "prepare", replace_after_review)
    with pytest.raises(PublishError, match="Separately reviewed input changed"):
        coordinator.prepare_publish(
            selected(
                wiki={
                    "repo_titles": ["Module:X"],
                    "page_edits_file": str(prose_file),
                    "prose_review_sha256": reviewed_digest,
                }
            ),
            ctx,
            root / "review-race",
        )
    assert provider.writes == []
    assert not (root / "review-race" / "plan.json").exists()


@pytest.mark.parametrize("with_maps", [False, True])
def test_completed_article_editor_change_blocks_cross_surface_consumer(
    publication, monkeypatch, with_maps: bool
) -> None:
    surfaces = {"wiki": {"article_titles": ["A", "B"]}, "sheets": {"tabs": ["items"]}}
    if with_maps:
        surfaces["maps"] = {"targets": ["canonical"]}
    ctx, provider, plan, path = prepare(publication, selected(**surfaces))
    native_execute = provider.execute

    def editor_change(context, operation, payload, receipts):
        receipt = native_execute(context, operation, payload, receipts)
        if operation["id"] == "wiki_article:B":
            provider.state["wiki_article:A"] = {"revision": 99, "text": "later editor revision"}
        return receipt

    monkeypatch.setattr(provider, "execute", editor_change)
    with pytest.raises(PublishError, match="Completed destination changed"):
        coordinator.apply_publish(path, plan.digest, ctx)
    assert provider.writes == ["wiki_article:A", "wiki_article:B"]


def test_replaced_map_receipt_blocks_sheet_even_when_dependency_id_is_present(publication, monkeypatch) -> None:
    ctx, provider, plan, path = prepare(
        publication, selected(maps={"targets": ["canonical", "legacy"]}, sheets={"tabs": ["items"]})
    )
    native_execute = provider.execute

    def replace_canonical(context, operation, payload, receipts):
        receipt = native_execute(context, operation, payload, receipts)
        if operation["id"] == "map:legacy":
            provider.state["map:canonical"] = {"revision": 99, "text": "another deployment"}
        return receipt

    monkeypatch.setattr(provider, "execute", replace_canonical)
    with pytest.raises(PublishError, match="Completed destination changed"):
        coordinator.apply_publish(path, plan.digest, ctx)
    assert provider.writes == ["map:canonical", "map:legacy"]


def test_cross_surface_reconciliation_has_fixed_linear_passes(publication) -> None:
    ctx, provider, root = publication
    titles = [f"Article{index:03}" for index in range(80)]
    plan = coordinator.prepare_publish(
        selected(
            wiki={"article_titles": titles},
            maps={"targets": ["canonical", "legacy"]},
            sheets={"tabs": ["items", "spells"]},
        ),
        ctx,
        root / "linear-surfaces",
    )
    coordinator.apply_publish(root / "linear-surfaces/plan.json", plan.digest, ctx)
    assert len(provider.reconciled) == 4 * len(titles) + 6
    assert provider.resume_batches == 3


def test_exact_selection_preserves_distinct_title_body_case() -> None:
    selection = selected(wiki={"article_titles": ["Case Page", "Case page"]})
    assert selection.wiki.article_titles == ["Case Page", "Case page"]
