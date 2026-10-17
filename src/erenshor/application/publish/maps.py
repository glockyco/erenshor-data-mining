"""Prepared maps publication using maps-owned builds and Wrangler deployment."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any

from erenshor.application.maps import build_info, catalog_images, publication
from erenshor.application.publish.models import SurfaceUncertainError

if TYPE_CHECKING:
    from erenshor.cli.context import CLIContext

RECOVERY = (
    "No automatic rollback. Retain the previous Cloudflare deployment/version IDs and use "
    "Cloudflare's separately reviewed provider recovery. Unknown outcomes cannot be retried. "
    "The guard is preflight-and-postflight, not atomic compare-and-set. A concurrent writer "
    "can race between inspection and deployment. Resume only after reconciling the exact "
    "active version and approved asset evidence."
)


class MapGuardError(ValueError):
    """An observed pre-write conflict cannot have changed the provider."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.evidence = {"safe_to_resume": True, "guard": "preflight-and-postflight"}


def _paths(ctx: CLIContext) -> tuple[Path, Path, Path]:
    variant = ctx.config.variants[ctx.variant]
    return (
        variant.maps.resolved_source_dir(ctx.repo_root),
        variant.maps.resolved_build_dir(ctx.repo_root),
        variant.resolved_database(ctx.repo_root),
    )


def _public_environment_inputs(maps_dir: Path) -> list[Path]:
    """Reject private build overrides rather than digesting credential material."""
    public_files = []
    for path in sorted(maps_dir.glob(".env*")):
        if not path.is_file() or path.name == ".env.example":
            continue
        assignments = [
            line.strip() for line in path.read_text().splitlines() if line.strip() and not line.lstrip().startswith("#")
        ]
        if path.name not in {".env", ".env.production"}:
            if assignments:
                raise ValueError(
                    f"Private map environment override is not supported by prepared publication: {path}. "
                    "Remove the override and keep production public inputs in .env.production."
                )
            continue
        if any(not line.removeprefix("export ").startswith("PUBLIC_") or "=" not in line for line in assignments):
            raise ValueError(
                f"Map environment file contains a non-public build input: {path}. "
                "Prepared publication accepts only PUBLIC_ assignments and never hashes credentials."
            )
        public_files.append(path)
    return public_files


def _input_paths(ctx: CLIContext, maps_dir: Path, database: Path, build_dir: Path) -> list[Path]:
    variant = ctx.config.variants[ctx.variant]
    roots = [maps_dir / name for name in ("src", "scripts", "static", "tests") if (maps_dir / name).exists()]
    # Installation credentials and local dev secrets are not production build inputs.
    roots.extend(
        path
        for path in maps_dir.iterdir()
        if path.is_file() and not path.name.startswith((".env", ".dev.vars")) and path.name != ".npmrc"
    )
    roots.extend(_public_environment_inputs(maps_dir))
    roots.extend(
        ctx.repo_root / name
        for name in ("package.json", "pnpm-lock.yaml", "pnpm-workspace.yaml")
        if (ctx.repo_root / name).is_file()
    )
    roots.extend(catalog_images.selected_source_paths(database, variant.resolved_images_output(ctx.repo_root)))
    roots.extend([database, build_dir])
    return sorted({path.absolute() for path in roots}, key=str)


def _snapshot(path: Path) -> dict[str, Any]:
    if path.is_dir():
        return {"path": str(path), "files": publication.manifest(path)}
    if not path.is_file():
        raise ValueError(f"Map input is missing: {path}")
    return {"path": str(path), "sha256": publication.sha256(path)}


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _build_source_snapshot(ctx: CLIContext, maps_dir: Path, database: Path, build_dir: Path) -> list[dict[str, Any]]:
    """Pin inputs before building without treating generated outputs as sources."""
    snapshots = [
        _snapshot(path)
        for path in _input_paths(ctx, maps_dir, database, build_dir)
        if path not in {build_dir.absolute(), (maps_dir / "static").absolute()}
    ]
    static = publication.manifest(maps_dir / "static")
    generated = {"og-default.png", "tiles/tiles-manifest.json"}
    static = {
        name: value
        for name, value in static.items()
        if name not in generated and not name.startswith(("items/", "characters/"))
    }
    snapshots.append({"path": str(maps_dir / "static"), "source_files": static})
    return snapshots


def prepare(ctx: CLIContext, selection: dict[str, Any], run_dir: Path) -> list[dict[str, Any]]:
    """Build once, freeze exact assets and bundles, and inspect selected live bases."""
    requested = selection.get("targets", [])
    if not requested or len(set(requested)) != len(requested) or set(requested) - set(publication.CONFIGS):
        raise ValueError("Select distinct explicit map targets: canonical and/or legacy")
    targets = [target for target in publication.CONFIGS if target in requested]
    maps_dir, build_dir, database = _paths(ctx)
    # Read-only destination checks precede local preparation side effects.
    destinations = {target: publication.destination(ctx, target) for target in targets}
    bases = {target: publication.current_deployment(maps_dir, target) for target in targets}
    pinned_sources = _build_source_snapshot(ctx, maps_dir, database, build_dir)
    publication.checked_build(ctx)
    if _build_source_snapshot(ctx, maps_dir, database, build_dir) != pinned_sources:
        raise ValueError("Map source bytes changed during the checked build. Prepare a new plan.")
    publication.assert_fresh(maps_dir, build_dir, database)
    database_digest = publication.verify_database(build_dir, database)
    asset_manifest = publication.manifest(build_dir)
    frozen = run_dir / "maps"
    frozen.mkdir(parents=True, exist_ok=False)
    assets = frozen / "build"
    shutil.copytree(build_dir, assets, symlinks=False)
    if publication.manifest(assets) != asset_manifest or publication.manifest(build_dir) != asset_manifest:
        raise ValueError("Map output changed while freezing the reviewed build")
    inputs = _input_paths(ctx, maps_dir, database, build_dir)
    snapshots = [_snapshot(path) for path in inputs]
    operations = []
    for target in targets:
        config = frozen / publication.CONFIGS[target]
        shutil.copyfile(maps_dir / publication.CONFIGS[target], config)
        bundle_dir = frozen / target
        bundle = publication.freeze_worker(maps_dir, target, bundle_dir)
        payload = {
            "target": target,
            "assets": str(assets),
            "bundle": str(bundle),
            "config": str(config),
            "asset_manifest": asset_manifest,
            "worker_manifest": publication.manifest(bundle_dir),
            "config_sha256": publication.sha256(config),
            "input_snapshots": snapshots,
            "database_route": {"path": "/db/erenshor.sqlite", "sha256": database_digest},
            "native_build_info": build_info.read_build_info(assets),
            "guard": "preflight-and-postflight",
            "limitations": RECOVERY,
            "actions": [
                "upload frozen Worker without rebundling",
                "upload frozen assets",
                "activate version",
                "verify version and database body",
            ],
            "asset_evidence": (
                "Full local byte manifest and checked Wrangler upload are bound to an immutable "
                "provider version by its workers/message annotation. The provider CLI does not "
                "expose a downloadable asset manifest. The database body is checked directly on each host."
            ),
        }
        # Include the captured base so a later preparation of identical assets cannot
        # accidentally adopt an earlier publication's provider annotation.
        payload["message"] = "publish-map:" + _digest(
            {
                "target": target,
                "base": bases[target],
                "assets": asset_manifest,
                "worker": payload["worker_manifest"],
                "config": payload["config_sha256"],
            }
        )
        operations.append(
            {
                "id": f"map:{target}",
                "kind": "map",
                "target": target,
                "dependencies": ["map:canonical"] if target == "legacy" and "canonical" in targets else [],
                "payload": payload,
                "expected_base": bases[target],
                "recovery": RECOVERY,
                "inputs": [str(path) for path in inputs],
                "destination": destinations[target],
            }
        )
    # Refuse a source or generated-asset change while Wrangler bundles the Workers.
    if [_snapshot(path) for path in inputs] != snapshots:
        raise ValueError("Map inputs changed during preparation. Prepare a new plan.")
    return operations


def _check_local(ctx: CLIContext, operation: dict[str, Any], payload: dict[str, Any]) -> None:
    # Only the coordinator's concrete, launch-verified proof can extend byte
    # evidence across calls. Standalone callers always read the bytes themselves.
    from erenshor.application.publish.coordinator import ExecutionInputProof

    proof = operation.get("_input_proof")
    if isinstance(proof, ExecutionInputProof):
        proof.verify(operation)
    maps_dir, build_dir, database = _paths(ctx)
    inputs = _input_paths(ctx, maps_dir, database, build_dir)
    if [str(path) for path in inputs] != [snapshot["path"] for snapshot in payload["input_snapshots"]]:
        raise MapGuardError("Map source/configuration input selection changed after preparation")
    target = operation["target"]
    if payload["target"] != target or publication.destination(ctx, target) != operation["destination"]:
        raise MapGuardError("Map destination/account changed after preparation")

    assets, worker, config = Path(payload["assets"]), Path(payload["bundle"]).parent, Path(payload["config"])
    roots = [*inputs, assets, worker, config]
    cache: dict[str, Any] = {}
    if isinstance(proof, ExecutionInputProof):
        proof.assert_unchanged(roots)
        cache = proof.evidence.setdefault("maps.local-bytes", {})

    def snapshot(path: Path) -> dict[str, Any]:
        key = "snapshot:" + str(path)
        if key not in cache:
            if isinstance(proof, ExecutionInputProof):
                cache[key] = (
                    {"path": str(path), "files": proof.manifest(path)}
                    if path.is_dir()
                    else {"path": str(path), "sha256": proof.file_digest(path)}
                )
            else:
                cache[key] = _snapshot(path)
        evidence: dict[str, Any] = cache[key]
        return evidence

    # Canonical and legacy share this native source proof and all common local
    # manifests, but never share destination or active-deployment observations.
    freshness_key = "freshness:" + _digest([str(path) for path in inputs])
    if freshness_key not in cache:
        cache[freshness_key] = build_info.compute_input_hashes(maps_source_dir=maps_dir, database_path=database)
    current = cache[freshness_key]
    publication.assert_fresh(maps_dir, build_dir, database, input_hashes=current)
    publication.assert_fresh(maps_dir, assets, database, input_hashes=current)
    for expected in payload["input_snapshots"]:
        if snapshot(Path(expected["path"])) != expected:
            raise MapGuardError(f"Map input bytes changed: {expected['path']}")
    if snapshot(assets)["files"] != payload["asset_manifest"]:
        raise MapGuardError("Frozen map asset bytes changed after review")
    if snapshot(worker)["files"] != payload["worker_manifest"]:
        raise MapGuardError("Frozen Worker bytes changed after review")
    if snapshot(config)["sha256"] != payload["config_sha256"]:
        raise MapGuardError("Frozen Wrangler configuration changed after review")
    database_digest = snapshot(database)["sha256"]
    body = snapshot(assets)["files"].get("db/erenshor.sqlite")
    if database_digest != payload["database_route"]["sha256"] or body is None or body["sha256"] != database_digest:
        raise MapGuardError("Reviewed map database body changed")
    if isinstance(proof, ExecutionInputProof):
        proof.assert_unchanged(roots)


def _verify_receipt(
    maps_dir: Path, operation: dict[str, Any], payload: dict[str, Any], receipt: dict[str, Any]
) -> None:
    required = {
        "operation_id",
        "destination",
        "deployment",
        "message",
        "asset_manifest_digest",
        "worker_manifest_digest",
        "database_sha256",
    }
    if not required <= receipt.keys():
        raise ValueError("Unknown map receipt. An unacknowledged deployment cannot be retried or adopted.")
    if (
        receipt["operation_id"] != operation["id"]
        or receipt["destination"] != operation["destination"]
        or receipt["message"] != payload["message"]
        or receipt["asset_manifest_digest"] != _digest(payload["asset_manifest"])
        or receipt["worker_manifest_digest"] != _digest(payload["worker_manifest"])
        or receipt["database_sha256"] != payload["database_route"]["sha256"]
    ):
        raise ValueError("Map receipt does not identify the approved operation and asset bytes")
    current = publication.current_deployment(maps_dir, operation["target"])
    if current != receipt["deployment"]:
        raise ValueError("Completed map deployment/version changed before resume")
    versions = current["versions"]
    if len(versions) != 1 or versions[0]["percentage"] != 100 or versions[0]["message"] != payload["message"]:
        raise ValueError("Cloudflare version does not uniquely identify the reviewed map upload")
    if publication.remote_database_digest(operation["destination"]["url"]) != receipt["database_sha256"]:
        raise ValueError("Live map database bytes differ from the reviewed clean database")
    # Detect another deployment racing the postflight HTTP read too.
    if publication.current_deployment(maps_dir, operation["target"]) != current:
        raise ValueError("Map provider changed during postflight asset verification")


def check(
    ctx: CLIContext, operation: dict[str, Any], payload: dict[str, Any], receipts: dict[str, dict[str, Any]]
) -> None:
    """Inspect the approved source/artifact bytes and active target base."""
    try:
        _check_local(ctx, operation, payload)
        maps_dir, _, _ = _paths(ctx)
        if publication.current_deployment(maps_dir, operation["target"]) != operation["expected_base"]:
            raise MapGuardError("Map active deployment/version differs from the approved base")
        for dependency in operation["dependencies"]:
            if dependency == "map:canonical" and dependency in receipts:
                receipt = receipts[dependency]
                current = publication.current_deployment(maps_dir, "canonical")
                versions = current.get("versions", [])
                if (
                    receipt.get("operation_id") != dependency
                    or current != receipt.get("deployment")
                    or receipt.get("asset_manifest_digest") != _digest(payload["asset_manifest"])
                    or receipt.get("database_sha256") != payload["database_route"]["sha256"]
                    or receipt.get("destination") != publication.destination(ctx, "canonical")
                    or len(versions) != 1
                    or versions[0]["percentage"] != 100
                    or versions[0]["message"] != receipt.get("message")
                ):
                    raise MapGuardError("Canonical predecessor receipt no longer matches Cloudflare")
    except MapGuardError:
        raise
    except Exception as error:
        raise MapGuardError(str(error)) from error


def execute(
    ctx: CLIContext, operation: dict[str, Any], payload: dict[str, Any], receipts: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Publish only frozen bytes and refuse ambiguous provider responses."""
    check(ctx, operation, payload, receipts)
    if "map:canonical" in operation["dependencies"] and "map:canonical" not in receipts:
        raise MapGuardError("Legacy deployment requires its recorded canonical predecessor receipt")
    maps_dir, _, _ = _paths(ctx)
    evidence: dict[str, Any] = {
        "operation_id": operation["id"],
        "previous_deployment": operation["expected_base"],
        "message": payload["message"],
        "recovery": RECOVERY,
    }
    try:
        publication.deploy_frozen(
            maps_dir,
            operation["target"],
            Path(payload["config"]),
            Path(payload["bundle"]),
            Path(payload["assets"]),
            payload["message"],
        )
        deployment = publication.current_deployment(maps_dir, operation["target"])
        evidence["observed_deployment"] = deployment
        if deployment == operation["expected_base"]:
            raise ValueError("Wrangler did not return a uniquely identifiable new deployment")
        receipt = {
            "operation_id": operation["id"],
            "destination": operation["destination"],
            "deployment": deployment,
            "previous_deployment": operation["expected_base"],
            "message": payload["message"],
            "asset_manifest_digest": _digest(payload["asset_manifest"]),
            "worker_manifest_digest": _digest(payload["worker_manifest"]),
            "database_sha256": payload["database_route"]["sha256"],
            "guard": "preflight-and-postflight",
        }
        evidence["provider_receipt"] = receipt
        _verify_receipt(maps_dir, operation, payload, receipt)
        return receipt
    except BaseException as error:
        # An interrupt or nonzero Wrangler exit can follow a successful upload or
        # activation. Never infer a safe retry from an absent local response.
        raise SurfaceUncertainError(
            f"Map deployment outcome requires provider reconciliation: {error}",
            evidence,
        ) from error


def reconcile(
    ctx: CLIContext,
    operation: dict[str, Any],
    payload: dict[str, Any],
    receipt: dict[str, Any],
    receipts: dict[str, dict[str, Any]],
) -> None:
    """Accept only a recorded exact provider version and matching asset evidence."""
    _check_local(ctx, operation, payload)
    maps_dir, _, _ = _paths(ctx)
    _verify_receipt(maps_dir, operation, payload, receipt)
