"""Fail-fast publication with immutable payloads and durable per-operation receipts."""

from __future__ import annotations

import fcntl
import json
import os
import tomllib
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

from erenshor.application.publish.models import (
    Operation,
    OperationKind,
    PreparedPublishPlan,
    PublishError,
    PublishSelection,
    SurfaceUncertainError,
    canonical,
    file_sha256,
    load_selection,
    order_operations,
    sha256,
)
from erenshor.infrastructure.config.paths import require_owned_write_path

if TYPE_CHECKING:
    from erenshor.cli.context import CLIContext


# This is a closed dispatch, not a user-extensible workflow registry.
def _surface(kind: str) -> Any:
    if kind in {"wiki_repo", "wiki_prose", "wiki_article"}:
        from . import wiki

        return wiki
    if kind == "map":
        from . import maps

        return maps
    if kind == "sheet":
        from . import sheets

        return sheets
    raise PublishError(f"Unknown publication operation: {kind}")


def _path(value: str, ctx: CLIContext, run_dir: Path, *, expand: bool = False) -> str:
    """Relocate one declared filesystem path, never opaque provider content."""
    for token, absolute in (("$RUN", str(run_dir.resolve())), ("$REPO", str(ctx.repo_root.resolve()))):
        source, target = (token, absolute) if expand else (absolute, token)
        if value == source or value.startswith(source + "/"):
            return target + value[len(source) :]
    return value


def _selection_paths(value: dict[str, Any], ctx: CLIContext, run_dir: Path, *, expand: bool = False) -> dict[str, Any]:
    from copy import deepcopy

    result = deepcopy(value)
    if result.get("wiki", {}).get("page_edits_file"):
        result["wiki"]["page_edits_file"] = _path(result["wiki"]["page_edits_file"], ctx, run_dir, expand=expand)
    return result


def _payload_paths(
    kind: str, value: dict[str, Any], ctx: CLIContext, run_dir: Path, *, expand: bool = False
) -> dict[str, Any]:
    from copy import deepcopy

    result = deepcopy(value)
    if kind in {"wiki_repo", "wiki_prose", "wiki_article"}:
        for key in ("native_manifest", "page_edits_file"):
            if result.get(key):
                result[key] = _path(result[key], ctx, run_dir, expand=expand)
        for key in ("local_outputs", "preparation_outputs"):
            if key in result:
                result[key] = [_path(path, ctx, run_dir, expand=expand) for path in result[key]]
        if "manifest_entry" in result:
            entry = result["manifest_entry"]
            entry["source_path"] = _path(entry["source_path"], ctx, run_dir, expand=expand)
    elif kind == "map":
        for key in ("assets", "bundle", "config"):
            if key in result:
                result[key] = _path(result[key], ctx, run_dir, expand=expand)
        for snapshot in result.get("input_snapshots", []):
            snapshot["path"] = _path(snapshot["path"], ctx, run_dir, expand=expand)
    elif kind == "sheet":
        if result.get("batch_body_path"):
            result["batch_body_path"] = _path(result["batch_body_path"], ctx, run_dir, expand=expand)
        for query in result.get("queries", []):
            query["path"] = _path(query["path"], ctx, run_dir, expand=expand)
    return result


def _require_run_output(path: Path, ctx: CLIContext, run_dir: Path) -> None:
    require_owned_write_path(path, ctx.repo_root)
    if not path.resolve().is_relative_to(run_dir.resolve()):
        raise PublishError(f"Publication output escapes approved run storage: {path}")


def _check_run_outputs(
    ctx: CLIContext, run_dir: Path, operation: Operation | None = None, payload: dict[str, Any] | None = None
) -> None:
    run_directory(ctx, run_dir)
    outputs = [run_dir / "execution.lock", run_dir / "journal.jsonl"]
    if payload is not None:
        if payload.get("native_manifest"):
            outputs.append(Path(payload["native_manifest"]))
        outputs.extend(Path(path) for path in payload.get("local_outputs", []))
        if operation is not None and operation.kind == OperationKind.MAP:
            outputs.extend(Path(payload[key]) for key in ("assets", "bundle", "config") if key in payload)
    if operation is not None and operation.kind == OperationKind.SHEET:
        stem = "sheets-" + sha256(operation.id.encode())
        outputs.append(run_dir / f"{stem}.jsonl")
        outputs.extend(run_dir.glob(f"{stem}*.jsonl"))
    for path in outputs:
        _require_run_output(path, ctx, run_dir)


def _fingerprint(path: Path) -> str:
    if path.is_file():
        return file_sha256(path)
    if not path.is_dir():
        raise PublishError(f"Pinned input is missing: {path}")
    entries: dict[str, str] = {}
    ancestors: set[Path] = set()

    def visit(directory: Path, relative: Path) -> None:
        resolved = directory.resolve()
        if resolved in ancestors:
            raise PublishError(f"Cyclic input directory: {directory}")
        ancestors.add(resolved)
        for child in sorted(directory.iterdir()):
            if child.name in {"__pycache__", ".DS_Store"} or child.suffix == ".pyc":
                continue
            name = relative / child.name
            if child.is_dir():
                entries[name.as_posix() + "/"] = "directory"
                visit(child, name)
            elif child.is_file():
                entries[name.as_posix()] = file_sha256(child)
            else:
                raise PublishError(f"Unreadable pinned input: {child}")
        ancestors.remove(resolved)

    visit(path, Path())
    return sha256(canonical(entries))


def configuration(ctx: CLIContext, selection: dict[str, Any]) -> dict[str, Any]:
    reviewed_urls = []
    if selection.get("wiki"):
        reviewed_urls.append(ctx.config.global_.mediawiki.api_url)
    if selection.get("maps") or selection.get("wiki") or selection.get("sheets"):
        reviewed_urls.append(ctx.config.variants[ctx.variant].maps.base_url)
    if selection.get("maps"):
        reviewed_urls.append(ctx.config.variants[ctx.variant].maps.legacy_base_url)
    if any(urlsplit(url).username is not None for url in reviewed_urls):
        raise PublishError("Publication URLs must not contain credentials. Configure publisher accounts separately")
    variant = ctx.config.variants[ctx.variant]
    result: dict[str, Any] = {"variant": variant.model_dump(mode="json", exclude={"google_sheets", "maps"})}
    if selection.get("wiki"):
        wiki = ctx.config.global_.mediawiki
        result["wiki"] = wiki.model_dump(
            mode="json",
            exclude={
                "bot_password",
                "interface_username",
                "interface_password",
                "administrator_username",
                "administrator_password",
            },
        )
        result["templates"] = ctx.config.global_.paths.templates
    if selection.get("maps"):
        result["maps"] = variant.maps.model_dump(mode="json")
    if selection.get("sheets"):
        result["sheets"] = variant.google_sheets.model_dump(mode="json")
        result["sheets_publisher"] = ctx.config.global_.google_sheets.model_dump(mode="json")
    if selection.get("wiki") or selection.get("sheets"):
        result["link_map_base_url"] = variant.maps.base_url
    sources: dict[str, str] = {}
    for name in ("config.toml", ".erenshor/config.local.toml"):
        path = ctx.repo_root / name
        if not path.exists():
            sources[name] = "absent"
            continue
        source = tomllib.loads(path.read_text(encoding="utf-8"))
        public: dict[str, Any] = {"variant": dict(source.get("variants", {}).get(ctx.variant, {}))}
        if not selection.get("maps"):
            map_source = public["variant"].pop("maps", {})
            if selection.get("wiki") or selection.get("sheets"):
                public["link_map_base_url"] = map_source.get("base_url")
        if not selection.get("sheets"):
            public["variant"].pop("google_sheets", None)
        global_source = source.get("global", {})
        if selection.get("wiki"):
            public["wiki"] = {
                key: value
                for key, value in global_source.get("mediawiki", {}).items()
                if key
                not in {
                    "bot_password",
                    "interface_username",
                    "interface_password",
                    "administrator_username",
                    "administrator_password",
                }
            }
            public["templates"] = global_source.get("paths", {}).get("templates")
        if selection.get("sheets"):
            public["sheets"] = global_source.get("google_sheets", {})
        sources[name] = sha256(canonical(public))
    result["configuration_sources"] = sources
    return result


def run_directory(ctx: CLIContext, output: Path) -> Path:
    variant = ctx.config.variants[ctx.variant]
    root = variant.resolved_wiki(ctx.repo_root).parent.resolve()
    resolved = output.resolve()
    if not resolved.is_relative_to(root) or resolved == root:
        raise PublishError(f"Publication output must be a new directory under selected variant storage: {root}")
    require_owned_write_path(output, ctx.repo_root)
    if resolved.is_relative_to((ctx.repo_root / "wiki").resolve()):
        raise PublishError("Editor payloads must never be stored under tracked wiki sources")
    protected = (
        variant.resolved_images_output(ctx.repo_root),
        variant.resolved_backups(ctx.repo_root),
        variant.resolved_unity_project(ctx.repo_root),
        variant.maps.resolved_source_dir(ctx.repo_root),
        variant.maps.resolved_build_dir(ctx.repo_root),
    )
    if any(resolved.is_relative_to(path.resolve()) for path in protected):
        raise PublishError("Run storage must not be nested inside pinned inputs or build outputs")
    return resolved


def preparation_outputs(ctx: CLIContext, selection: dict[str, Any], run_dir: Path) -> list[str]:
    outputs = [
        str(run_dir / name) for name in ("plan.json", "payloads", "review.json", "review-summary.json", "metadata.json")
    ]
    if selection.get("wiki"):
        outputs.append(str(run_dir / "wiki"))
    if selection.get("maps"):
        variant = ctx.config.variants[ctx.variant]
        maps_dir = variant.maps.resolved_source_dir(ctx.repo_root)
        outputs.extend(
            str(path)
            for path in (
                run_dir / "maps",
                variant.maps.resolved_build_dir(ctx.repo_root),
                maps_dir / ".svelte-kit",
                maps_dir / "static" / "items",
                maps_dir / "static" / "characters",
                maps_dir / "static" / "og-default.png",
                maps_dir / "static" / "tiles" / "tiles-manifest.json",
            )
        )
    return outputs


def _durable_bytes(path: Path, data: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _durable_json(path: Path, value: Any) -> None:
    _durable_bytes(path, canonical(value) + b"\n")


def prepare_publish(
    selection: PublishSelection, ctx: CLIContext, output: Path, *, selection_path: Path | None = None
) -> PreparedPublishPlan:
    if ctx.dry_run:
        raise PublishError("Dry-run preparation describes actions without creating a plan")
    run_dir = run_directory(ctx, output)
    if run_dir.exists():
        raise PublishError(f"Run directory already exists. Choose a new directory: {run_dir}")
    selected = selection.model_dump(mode="json", exclude_none=True)
    config = configuration(ctx, selected)
    database = ctx.config.variants[ctx.variant].resolved_database(ctx.repo_root)
    from erenshor.application.extract.database_comparison import recorded_build_id

    game_build_id = recorded_build_id(database)
    fixed = {str(database): _fingerprint(database)}
    # Pin all publisher/generator implementation bytes before any preparation side effect.
    code = ctx.repo_root / "src" / "erenshor"
    fixed[str(code)] = _fingerprint(code)
    for name in ("mapping.json", "content-lifecycle.json"):
        source = ctx.repo_root / name
        if source.exists():
            fixed[str(source)] = _fingerprint(source)
    run_dir.mkdir(parents=True)
    (run_dir / "payloads").mkdir()
    drafts: list[dict[str, Any]] = []
    for name, kind in (("wiki", "wiki_repo"), ("maps", "map"), ("sheets", "sheet")):
        if name in selected:
            section = {**selected[name], "summary": selection.summary}
            drafts.extend(_surface(kind).prepare(ctx, section, run_dir))
    if not drafts:
        raise PublishError("Selection produced no operations")
    operations: list[Operation] = []
    fingerprints = dict(fixed)
    for draft in drafts:
        body_input: tuple[str, str] | None = None
        if draft["kind"] == "sheet" and "batch_body" in draft["payload"]:
            body = draft["payload"]["batch_body"].encode("utf-8")
            body_digest = sha256(body)
            if body_digest != draft["payload"]["batch_body_sha256"]:
                raise PublishError("Prepared Sheets wire body does not match its declared digest")
            body_path = run_dir / "payloads" / f"{body_digest}.batch.json"
            _require_run_output(body_path, ctx, run_dir)
            if body_path.exists():
                if file_sha256(body_path) != body_digest:
                    raise PublishError("Prepared Sheets wire-body sidecar changed")
            else:
                _durable_bytes(body_path, body)
            draft["payload"]["batch_body_path"] = str(body_path)
            body_input = (str(body_path), body_digest)
        payload = _payload_paths(draft["kind"], draft["payload"], ctx, run_dir)
        content = canonical(payload) + b"\n"
        digest = sha256(content)
        relative = f"payloads/{digest}.json"
        if not (run_dir / relative).exists():
            _durable_json(run_dir / relative, payload)
        inputs: dict[str, str] = {}
        approved_inputs = dict(draft.get("input_sha256", {}))
        draft_inputs = list(draft.get("inputs", []))
        if body_input is not None:
            body_path_text, body_digest = body_input
            draft_inputs.append(body_path_text)
            approved_inputs[body_path_text] = body_digest
        for path in sorted(set(draft_inputs)):
            absolute = str(Path(path).absolute())
            if absolute not in fingerprints:
                fingerprints[absolute] = _fingerprint(Path(absolute))
            expected = approved_inputs.get(path, fingerprints[absolute])
            if fingerprints[absolute] != expected:
                raise PublishError(f"Separately reviewed input changed: {absolute}")
            inputs[_path(absolute, ctx, run_dir)] = expected
        operation_data = {
            key: draft[key]
            for key in ("id", "kind", "target", "dependencies", "expected_base", "recovery", "destination")
        }
        operation_data.update(payload_path=relative, payload_sha256=digest, inputs=inputs)
        # JSON validation accepts the closed string enum while retaining strict scalar types.
        operations.append(Operation.model_validate_json(canonical(operation_data)))
    wiki_ids = [op.id for op in operations if op.kind not in (OperationKind.MAP, OperationKind.SHEET)]
    article_ids = [op.id for op in operations if op.kind == OperationKind.WIKI_ARTICLE]
    map_ids = [op.id for op in operations if op.kind == OperationKind.MAP]
    canonical_id = next((op.id for op in operations if op.kind == OperationKind.MAP and op.target == "canonical"), None)
    for operation in operations:
        if operation.kind == OperationKind.MAP:
            for dependency in wiki_ids:
                if dependency not in operation.dependencies:
                    operation.dependencies.append(dependency)
                    operation.dependency_reasons[dependency] = "Selected wiki publication precedes map publication"
            if operation.target == "legacy" and canonical_id and canonical_id not in operation.dependencies:
                operation.dependencies.append(canonical_id)
                operation.dependency_reasons[canonical_id] = "Canonical service precedes legacy service"
        if operation.kind == OperationKind.SHEET:
            for dependency in article_ids + map_ids:
                if dependency not in operation.dependencies:
                    operation.dependencies.append(dependency)
                    operation.dependency_reasons[dependency] = "Selected destinations precede exported links"
        operation.dependencies.sort()
        for dependency in operation.dependencies:
            operation.dependency_reasons.setdefault(dependency, "Required selected predecessor")
    for path, digest in fingerprints.items():
        if _fingerprint(Path(path)) != digest:
            raise PublishError(f"Input changed during preparation: {path}. Prepare again")
    if configuration(ctx, selected) != config:
        raise PublishError("Configuration changed during preparation")
    plan = PreparedPublishPlan(
        variant=ctx.variant,
        game_build_id=game_build_id,
        selection=_selection_paths(selected, ctx, run_dir),
        selection_path=_path(str(selection_path.resolve()), ctx, run_dir) if selection_path else None,
        configuration=config,
        inputs={_path(path, ctx, run_dir): digest for path, digest in fixed.items()},
        operations=order_operations(operations),
    )
    plan.digest = plan.approval_digest()
    _durable_json(run_dir / "plan.json", plan.model_dump(mode="json"))
    _durable_json(run_dir / "metadata.json", {"prepared_at": datetime.now(UTC).isoformat(), "run_dir": str(run_dir)})
    review = review_document(plan, ctx, run_dir)
    _durable_json(run_dir / "review.json", review)
    from .reporting import review_summary

    _durable_bytes(
        run_dir / "review-summary.json",
        (json.dumps(review_summary(review), ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
    )
    return plan


def load_plan(path: Path, ctx: CLIContext) -> PreparedPublishPlan:
    plan = PreparedPublishPlan.model_validate_json(path.read_bytes())
    plan.validate_digest()
    if plan.variant != ctx.variant:
        raise PublishError(f"Plan selects variant {plan.variant}, not {ctx.variant}")
    # The graph and its serialized order must both remain canonical.
    if [op.id for op in order_operations(plan.operations)] != [op.id for op in plan.operations]:
        raise PublishError("Plan operation order is not canonical")
    return plan


def payload_for(operation: Operation, ctx: CLIContext, run_dir: Path) -> dict[str, Any]:
    relative = Path(operation.payload_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise PublishError(f"Unsafe payload path: {relative}")
    path = run_dir / relative
    if not path.resolve().is_relative_to(run_dir.resolve()):
        raise PublishError(f"Payload escapes run storage: {relative}")
    content = path.read_bytes()
    value = json.loads(content)
    if sha256(content) != operation.payload_sha256:
        raise PublishError(f"Payload changed after review: {operation.id}")
    expanded = _payload_paths(operation.kind, value, ctx, run_dir, expand=True)
    return expanded


def _runtime(
    operation: Operation, ctx: CLIContext, run_dir: Path, proof: ExecutionInputProof | None = None
) -> dict[str, Any]:
    value = operation.model_dump(mode="json")
    value["_run_dir"] = str(run_dir)
    if proof is not None:
        value["_input_proof"] = proof
    return value


def _validate_configuration(
    plan: PreparedPublishPlan, ctx: CLIContext, run_dir: Path, *, verify_plan: bool = True
) -> None:
    if verify_plan:
        plan.validate_digest()
    selected = _selection_paths(plan.selection, ctx, run_dir, expand=True)
    if plan.selection_path:
        selection_file = Path(_path(plan.selection_path, ctx, run_dir, expand=True))
        current = load_selection(selection_file).model_dump(mode="json", exclude_none=True)
        if _selection_paths(current, ctx, run_dir) != plan.selection:
            raise PublishError("Selection changed after review. Prepare and review a new plan")
    if configuration(ctx, selected) != plan.configuration:
        raise PublishError("Selected configuration or destination changed. Prepare and review a new plan")


class ExecutionInputProof:
    """Verify bytes once, then reject every change to relevant kernel metadata seals."""

    def __init__(self, plan: PreparedPublishPlan, ctx: CLIContext, run_dir: Path):
        self.plan = plan
        self.ctx = ctx
        self.run_dir = run_dir
        self.evidence: dict[str, Any] = {}
        self._nodes: dict[Path, tuple[int, ...]] = {}
        self._roots: dict[Path, tuple[Path, ...]] = {}
        self._files: dict[Path, str] = {}
        self._payloads: dict[str, dict[str, Any]] = {}
        self._common = [Path(_path(path, ctx, run_dir, expand=True)) for path in plan.inputs]
        self._operations: dict[str, list[Path]] = {}
        expected: dict[Path, str] = {}
        for path, digest in plan.inputs.items():
            expected[Path(_path(path, ctx, run_dir, expand=True)).absolute()] = digest
        for operation in plan.operations:
            roots = [Path(_path(path, ctx, run_dir, expand=True)).absolute() for path in operation.inputs]
            payload_path = (run_dir / operation.payload_path).absolute()
            self._operations[operation.id] = [*roots, payload_path]
            for path, digest in operation.inputs.items():
                absolute = Path(_path(path, ctx, run_dir, expand=True)).absolute()
                if absolute in expected and expected[absolute] != digest:
                    raise PublishError(f"Inconsistent approved input digests: {absolute}")
                expected[absolute] = digest
            expected[payload_path] = operation.payload_sha256
        for root in expected:
            self._collect(root)
        for node in tuple(self._nodes):
            if node.is_file():
                self._files[node] = file_sha256(node)
        for root, digest in expected.items():
            if self._fingerprint(root) != digest:
                raise PublishError(f"Pinned input changed: {root}. Prepare and review a new plan")
        _validate_configuration(plan, ctx, run_dir)
        for operation in plan.operations:
            payload = payload_for(operation, ctx, run_dir)
            self._payloads[operation.id] = payload
            if operation.kind == OperationKind.MAP:
                for name in ("assets", "config"):
                    if name in payload:
                        self._collect(Path(payload[name]))
                if "bundle" in payload:
                    self._collect(Path(payload["bundle"]).parent)
        for node in tuple(self._nodes):
            if node.is_file() and node not in self._files:
                self._files[node] = file_sha256(node)
        self.assert_unchanged(list(self._roots))

    @staticmethod
    def _seal(path: Path) -> tuple[int, ...]:
        try:
            link, target = path.lstat(), path.stat()
        except OSError as error:
            raise PublishError(f"Pinned input changed: {path}") from error
        return tuple(
            value
            for info in (link, target)
            for value in (info.st_dev, info.st_ino, info.st_mode, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
        )

    def _collect(self, root: Path) -> None:
        root = root.absolute()
        if root in self._roots:
            return
        nodes: list[Path] = []
        ancestors: set[tuple[int, int]] = set()

        def visit(path: Path) -> None:
            seal = self._seal(path)
            if path in self._nodes and self._nodes[path] != seal:
                raise PublishError(f"Pinned input changed while establishing proof: {path}")
            self._nodes[path] = seal
            nodes.append(path)
            if path.is_dir():
                identity = (path.stat().st_dev, path.stat().st_ino)
                if identity in ancestors:
                    raise PublishError(f"Cyclic pinned directory: {path}")
                ancestors.add(identity)
                for child in sorted(path.iterdir()):
                    python_cache = child.name == "__pycache__" or child.suffix == ".pyc"
                    if python_cache and child.is_relative_to(self.ctx.repo_root / "src" / "erenshor"):
                        continue
                    visit(child)
                ancestors.remove(identity)

        visit(root)
        self._roots[root] = tuple(nodes)

    def _fingerprint(self, root: Path) -> str:
        if root.is_file():
            return self._files[root]
        entries: dict[str, str] = {}
        for path in self._roots[root]:
            if path == root:
                continue
            relative = path.relative_to(root)
            if any(part in {"__pycache__", ".DS_Store"} for part in relative.parts) or path.suffix == ".pyc":
                continue
            if path.is_dir():
                entries[relative.as_posix() + "/"] = "directory"
            else:
                entries[relative.as_posix()] = self._files[path]
        return sha256(canonical(entries))

    def assert_unchanged(self, paths: Sequence[str | Path]) -> None:
        checked: set[Path] = set()
        for value in paths:
            root = Path(value).absolute()
            if root not in self._nodes:
                raise PublishError(f"Input is outside the established byte proof: {root}")
            nodes = self._roots.get(root)
            if nodes is None:
                nodes = tuple(path for path in self._nodes if path == root or path.is_relative_to(root))
                self._roots[root] = nodes
            for path in nodes:
                if path not in checked:
                    if self._seal(path) != self._nodes[path]:
                        raise PublishError(f"Pinned input changed: {path}. Prepare and review a new plan")
                    checked.add(path)

    def verify(self, operation: dict[str, Any]) -> None:
        _validate_configuration(self.plan, self.ctx, self.run_dir, verify_plan=False)
        self.assert_unchanged([*self._common, *self._operations[operation["id"]]])

    def file_digest(self, path: Path) -> str:
        self.assert_unchanged([path])
        return self._files[path.absolute()]

    def manifest(self, root: Path) -> dict[str, dict[str, Any]]:
        self.assert_unchanged([root])
        absolute = root.absolute()
        return {
            path.relative_to(absolute).as_posix(): {"sha256": self._files[path], "size": self._nodes[path][9]}
            for path in self._roots[absolute]
            if path in self._files
        }

    def payload(self, operation: Operation) -> dict[str, Any]:
        from copy import deepcopy

        return deepcopy(self._payloads[operation.id])


def validate_inputs(plan: PreparedPublishPlan, ctx: CLIContext, run_dir: Path) -> None:
    ExecutionInputProof(plan, ctx, run_dir)


def review_document(plan: PreparedPublishPlan, ctx: CLIContext, run_dir: Path) -> dict[str, Any]:
    return {
        "run_dir": str(run_dir),
        "plan_path": "$RUN/plan.json",
        "review_path": "$RUN/review.json",
        "summary_path": "$RUN/review-summary.json",
        "approval_digest": plan.digest,
        "variant": plan.variant,
        "game_build_id": plan.game_build_id,
        "selection": plan.selection,
        "configuration": plan.configuration,
        "inputs": plan.inputs,
        "local_outputs": [
            _path(path, ctx, run_dir)
            for path in [
                *preparation_outputs(ctx, plan.selection, run_dir),
                str(run_dir / "journal.jsonl"),
                str(run_dir / "execution.lock"),
            ]
        ],
        "operations": [
            {
                **op.model_dump(mode="json"),
                "payload": _payload_paths(op.kind, payload_for(op, ctx, run_dir), ctx, run_dir),
            }
            for op in plan.operations
        ],
        "recovery": (
            "No automatic retry or rollback. Explicit resume reconciles every completed receipt. "
            "Uncertain writes require provider reconciliation. New wiki pages require manual deletion. "
            "Maps and Sheets do not provide a cross-service transaction."
        ),
    }


class Journal:
    def __init__(self, path: Path, digest: str):
        self.path = path
        self.digest = digest
        self.events: list[dict[str, Any]] = []
        if path.exists():
            data = path.read_bytes()
            if data and not data.endswith(b"\n"):
                raise PublishError(
                    "Journal has an incomplete record. Reconcile the interrupted write before continuation"
                )
            previous = ""
            for line in data.splitlines():
                event = json.loads(line)
                checksum = event.pop("checksum")
                if (
                    event.get("plan") != digest
                    or event.get("previous") != previous
                    or sha256(canonical(event)) != checksum
                ):
                    raise PublishError("Journal integrity mismatch")
                event["checksum"] = checksum
                self.events.append(event)
                previous = checksum

    def append(self, operation: str, state: str, **evidence: Any) -> None:
        event = {
            "plan": self.digest,
            "operation": operation,
            "state": state,
            "time": datetime.now(UTC).isoformat(),
            "previous": self.events[-1]["checksum"] if self.events else "",
            **evidence,
        }
        event["checksum"] = sha256(canonical(event))
        with self.path.open("ab") as stream:
            stream.write(canonical(event) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        descriptor = os.open(self.path.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        self.events.append(event)

    def latest(self) -> dict[str, dict[str, Any]]:
        return {event["operation"]: event for event in self.events if event["operation"] != "$approval"}


@contextmanager
def _lock(run_dir: Path) -> Iterator[None]:
    with (run_dir / "execution.lock").open("a+b") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise PublishError("This publication run already has a local executor") from error
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def status_publish(path: Path, ctx: CLIContext) -> dict[str, Any]:
    plan = load_plan(path, ctx)
    journal = Journal(path.parent / "journal.jsonl", plan.digest)
    latest = journal.latest()
    states = []
    halted = False
    history_by_id: dict[str, list[dict[str, Any]]] = {}
    for entry in journal.events:
        history_by_id.setdefault(entry["operation"], []).append(entry)
    for operation in plan.operations:
        event = latest.get(operation.id, {})
        state = event.get("state", "blocked" if halted else "pending")
        if state == "running":
            state = "uncertain"
        if state in {"failed", "uncertain", "blocked"}:
            halted = True
        history = history_by_id.get(operation.id, [])
        states.append(
            {
                **operation.model_dump(mode="json"),
                "state": state,
                "evidence": event,
                "history": history,
                "journal": str(journal.path),
            }
        )
    return {
        "digest": plan.digest,
        "variant": plan.variant,
        "game_build_id": plan.game_build_id,
        "configuration": plan.configuration,
        "inputs": plan.inputs,
        "selection": plan.selection,
        "run_dir": str(path.parent),
        "plan_path": str(path),
        "review_path": str(path.parent / "review.json"),
        "operations": states,
        "journal": str(journal.path),
        "next": (
            f"Review with publish apply {path} under root --dry-run. "
            f"Continue only with publish resume {path} --approval {plan.digest}. "
            "Uncertain outcomes must be reconciled, not retried."
        ),
    }


def _reconcile(
    plan: PreparedPublishPlan,
    ctx: CLIContext,
    run_dir: Path,
    latest: dict[str, dict[str, Any]],
    proof: ExecutionInputProof,
) -> dict[str, dict[str, Any]]:
    receipts = {key: value["receipt"] for key, value in latest.items() if value["state"] == "succeeded"}
    wiki_completed: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]] = []
    for operation in plan.operations:
        event = latest.get(operation.id)
        if event and event["state"] in {"running", "uncertain"}:
            raise PublishError(
                f"{operation.id} has an uncertain remote outcome. "
                "Reconcile provider evidence and prepare a new continuation"
            )
        if event and event["state"] == "succeeded":
            payload = proof.payload(operation)
            _check_run_outputs(ctx, run_dir, operation, payload)
            runtime = _runtime(operation, ctx, run_dir, proof)
            if operation.kind in {OperationKind.WIKI_REPO, OperationKind.WIKI_PROSE, OperationKind.WIKI_ARTICLE}:
                wiki_completed.append((runtime, payload, event["receipt"]))
            else:
                _surface(operation.kind).reconcile(ctx, runtime, payload, event["receipt"], receipts)
        if (
            event
            and event["state"] == "failed"
            and event.get("evidence")
            and (
                event["evidence"].get("partial_writes")
                or any(outcome.get("status") == "succeeded" for outcome in event["evidence"].get("outcomes", []))
            )
        ):
            raise PublishError(
                f"{operation.id} has partial provider writes. Reconcile them and prepare a new continuation"
            )
    if wiki_completed:
        _surface("wiki_repo").reconcile_many(ctx, wiki_completed, receipts)
    return receipts


def _reconcile_prerequisites(
    operation: Operation,
    plan: PreparedPublishPlan,
    ctx: CLIContext,
    run_dir: Path,
    receipts: dict[str, dict[str, Any]],
    proof: ExecutionInputProof,
) -> None:
    if operation.kind not in {OperationKind.MAP, OperationKind.SHEET}:
        return
    dependencies = set(operation.dependencies)
    wiki_predecessors: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]] = []
    other_predecessors: list[tuple[Operation, dict[str, Any], dict[str, Any]]] = []
    for previous in plan.operations:
        if previous.id not in dependencies:
            continue
        payload = proof.payload(previous)
        _check_run_outputs(ctx, run_dir, previous, payload)
        runtime = _runtime(previous, ctx, run_dir, proof)
        if previous.kind in {OperationKind.WIKI_REPO, OperationKind.WIKI_PROSE, OperationKind.WIKI_ARTICLE}:
            wiki_predecessors.append((runtime, payload, receipts[previous.id]))
        else:
            other_predecessors.append((previous, runtime, payload))
    if wiki_predecessors:
        _surface("wiki_repo").reconcile_many(ctx, wiki_predecessors, receipts)
    for previous, runtime, payload in other_predecessors:
        _surface(previous.kind).reconcile(ctx, runtime, payload, receipts[previous.id], receipts)


class InitialBaseError(PublishError):
    def __init__(self, error: Exception, operation_id: str):
        super().__init__(f"{type(error).__name__}: {error}")
        self.operation_id = operation_id


def _check_initial(
    plan: PreparedPublishPlan,
    ctx: CLIContext,
    run_dir: Path,
    receipts: dict[str, dict[str, Any]],
    proof: ExecutionInputProof,
) -> None:
    wiki_pending: list[tuple[dict[str, Any], dict[str, Any]]] = []
    other_pending: list[tuple[Operation, dict[str, Any], dict[str, Any]]] = []
    for operation in plan.operations:
        if operation.id in receipts:
            continue
        payload = proof.payload(operation)
        _check_run_outputs(ctx, run_dir, operation, payload)
        runtime = _runtime(operation, ctx, run_dir, proof)
        if operation.kind in {OperationKind.WIKI_REPO, OperationKind.WIKI_PROSE, OperationKind.WIKI_ARTICLE}:
            wiki_pending.append((runtime, payload))
        else:
            other_pending.append((operation, runtime, payload))
    if wiki_pending:
        try:
            _surface("wiki_repo").check_many(ctx, wiki_pending, receipts)
        except Exception as error:
            raise InitialBaseError(error, getattr(error, "operation_id", wiki_pending[0][0]["id"])) from error
    for operation, runtime, payload in other_pending:
        try:
            _surface(operation.kind).check(ctx, runtime, payload, receipts)
        except Exception as error:
            raise InitialBaseError(error, operation.id) from error


class PublishInspectionError(PublishError):
    def __init__(self, message: str, review: dict[str, Any]):
        super().__init__(message)
        self.review = review


def inspect_publish(path: Path, ctx: CLIContext) -> dict[str, Any]:
    path = path.absolute()
    _check_run_outputs(ctx, path.parent)
    plan = load_plan(path, ctx)
    review = review_document(plan, ctx, path.parent)
    try:
        for kind in {operation.kind for operation in plan.operations}:
            _surface(kind)
        proof = ExecutionInputProof(plan, ctx, path.parent)
        latest = Journal(path.parent / "journal.jsonl", plan.digest).latest()
        receipts = _reconcile(plan, ctx, path.parent, latest, proof)
        _check_initial(plan, ctx, path.parent, receipts, proof)
    except Exception as error:
        review.update(valid=False, conflicts=[f"{type(error).__name__}: {error}"])
        raise PublishInspectionError(str(error), review) from error
    return {**review, "valid": True, "conflicts": [], "execution": status_publish(path, ctx)}


def apply_publish(path: Path, approval_digest: str | None, ctx: CLIContext, *, resume: bool = False) -> dict[str, Any]:
    if ctx.dry_run:
        return inspect_publish(path, ctx)
    path = path.absolute()
    _check_run_outputs(ctx, path.parent)
    plan = load_plan(path, ctx)
    if approval_digest != plan.digest:
        raise PublishError("Live publication requires explicit human approval matching the reviewed plan digest")
    with _lock(path.parent):
        journal = Journal(path.parent / "journal.jsonl", plan.digest)
        if journal.events and not resume:
            raise PublishError("This run has execution history. Inspect status and use explicit resume")
        if resume and not journal.events:
            raise PublishError("This plan has no execution history. Use apply, not resume")
        for kind in {operation.kind for operation in plan.operations}:
            _surface(kind)
        proof = ExecutionInputProof(plan, ctx, path.parent)
        receipts = _reconcile(plan, ctx, path.parent, journal.latest(), proof)
        journal.append("$approval", "approved", declaration=approval_digest, resume=resume)
        # All fixed initial bases are checked before any live mutation.
        try:
            _check_initial(plan, ctx, path.parent, receipts, proof)
        except BaseException as error:
            failed_id = getattr(error, "operation_id", next(op.id for op in plan.operations if op.id not in receipts))
            journal.append(failed_id, "failed", error=f"{type(error).__name__}: {error}", phase="initial-base-check")
            for blocked in plan.operations:
                if blocked.id != failed_id and blocked.id not in receipts:
                    journal.append(blocked.id, "blocked", reason=failed_id)
            raise PublishError(f"Initial base check failed at {failed_id}: {error}") from error
        for index, operation in enumerate(plan.operations):
            if operation.id in receipts:
                continue
            try:
                proof.verify(_runtime(operation, ctx, path.parent))
                if set(operation.dependencies) - set(receipts):
                    raise PublishError(f"Unfinished predecessors for {operation.id}")
                owner = _surface(operation.kind)
                runtime = _runtime(operation, ctx, path.parent, proof)
                payload = proof.payload(operation)
                _check_run_outputs(ctx, path.parent, operation, payload)
                owner.check(ctx, runtime, payload, receipts)
                _reconcile_prerequisites(operation, plan, ctx, path.parent, receipts, proof)
                journal.append(
                    operation.id,
                    "running",
                    payload_sha256=operation.payload_sha256,
                    expected_base=operation.expected_base,
                    destination=operation.destination,
                    native_manifest=payload.get("native_manifest"),
                )
                receipt = owner.execute(ctx, runtime, payload, receipts)
                # A receipt is durable before postflight so a later mismatch cannot erase known writes.
                journal.append(operation.id, "succeeded", receipt=receipt)
                receipts[operation.id] = receipt
                owner.reconcile(ctx, runtime, payload, receipt, receipts)
            except BaseException as error:
                current = journal.latest().get(operation.id, {})
                evidence = getattr(error, "evidence", {})
                uncertain = (
                    isinstance(error, (SurfaceUncertainError, KeyboardInterrupt, SystemExit))
                    or current.get("state") == "succeeded"
                    or (
                        current.get("state") == "running"
                        and not evidence.get("safe_to_resume")
                        and getattr(error, "uncertain", True)
                    )
                )
                journal.append(
                    operation.id,
                    "uncertain" if uncertain else "failed",
                    error=f"{type(error).__name__}: {error}",
                    evidence=evidence,
                    known_receipt=current.get("receipt"),
                )
                for blocked in plan.operations[index + 1 :]:
                    if blocked.id not in receipts:
                        journal.append(blocked.id, "blocked", reason=operation.id)
                raise PublishError(
                    f"Publication stopped at {operation.id}: {error}. Inspect publish status {path}"
                ) from error
        return status_publish(path, ctx)


def resume_publish(path: Path, approval_digest: str | None, ctx: CLIContext) -> dict[str, Any]:
    return apply_publish(path, approval_digest, ctx, resume=True)
