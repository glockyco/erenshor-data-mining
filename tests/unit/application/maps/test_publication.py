"""Prepared maps bind real bytes and reconcile exact Cloudflare versions."""

from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from erenshor.application.maps import build_info, publication
from erenshor.application.publish import coordinator, maps
from erenshor.application.publish.models import (
    Operation,
    PreparedPublishPlan,
    SurfaceUncertainError,
    canonical,
    sha256,
)


@pytest.fixture
def prepared(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    source = tmp_path / "src" / "maps"
    (source / "src").mkdir(parents=True)
    (source / "src" / "app.ts").write_text("export const value = 1")
    tile = source / "static" / "tiles" / "zone.webp"
    tile.parent.mkdir(parents=True)
    tile.write_bytes(b"tile")
    (tile.parent / "tiles-manifest.json").write_text(json.dumps({"zoom_levels": {"0": {"count": 1}}}))
    for config in publication.CONFIGS.values():
        (source / config).write_text("{}")
    (tmp_path / "pnpm-lock.yaml").write_text("lock")
    images = tmp_path / "images"
    (images / "catalog").mkdir(parents=True)
    (images / "catalog.json").write_text("{}")
    (images / "catalog" / "item.png").write_bytes(b"item pixels")
    (images / "catalog" / "portrait.png").write_bytes(b"portrait pixels")
    (images / "catalog" / "hidden.png").write_bytes(b"hidden pixels")
    captures = images / "model-captures"
    captures.mkdir()
    (captures / "unused.png").write_bytes(b"unused capture")
    database = tmp_path / "clean.sqlite"
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE items (image_hash TEXT, is_map_visible INTEGER);
            INSERT INTO items VALUES ('item', 1), ('hidden', 0), (NULL, 1);
            CREATE TABLE characters (stable_key TEXT, image_hash TEXT);
            INSERT INTO characters VALUES ('visible', 'portrait'), ('hidden', 'hidden'), ('missing', NULL);
            CREATE TABLE character_deduplications (member_stable_key TEXT, is_map_visible INTEGER);
            INSERT INTO character_deduplications VALUES ('visible', 1), ('hidden', 0), ('missing', 1);
            """
        )
    build = source / "build"
    variant = SimpleNamespace(
        maps=SimpleNamespace(
            resolved_source_dir=lambda _: source,
            resolved_build_dir=lambda _: build,
            base_url="https://maps.example.test",
            legacy_base_url="https://legacy.example.test",
            model_dump=lambda **_: {"source_dir": str(source), "build_dir": str(build)},
        ),
        resolved_database=lambda _: database,
        resolved_images_output=lambda _: images,
        model_dump=lambda **_: {"database": str(database), "images": str(images)},
    )
    ctx = SimpleNamespace(config=SimpleNamespace(variants={"main": variant}), variant="main", repo_root=tmp_path)
    current = {
        target: {
            "deployment_id": f"old-{target}",
            "versions": [{"id": f"old-version-{target}", "percentage": 100, "message": None}],
        }
        for target in publication.CONFIGS
    }
    calls: list[str] = []

    def checked_build(_: Any) -> None:
        calls.append("build")
        (build / "db").mkdir(parents=True)
        shutil.copyfile(database, build / "db" / "erenshor.sqlite")
        (build / "map.html").write_text("map document")
        build_info.write_build_info(
            build, build_info.compute_input_hashes(maps_source_dir=source, database_path=database)
        )

    def freeze_worker(_: Path, target: str, output: Path) -> Path:
        output.mkdir()
        bundle = output / f"{target}.js"
        bundle.write_text(f"export default {{target:'{target}'}}")
        return bundle

    def destination(context: Any, target: str) -> dict[str, str]:
        maps_config = context.config.variants[context.variant].maps
        url = maps_config.base_url if target == "canonical" else maps_config.legacy_base_url
        return {"provider": "cloudflare", "account_id": "account", "service": target, "url": url}

    def deploy(_: Path, target: str, config: Path, bundle: Path, assets: Path, *, message: str) -> None:
        assert config.is_file() and bundle.is_file()
        assert assets != build
        assert publication.verify_database(assets, database) == publication.sha256(database)
        calls.append(target)
        current[target] = {
            "deployment_id": f"new-{target}",
            "versions": [{"id": f"new-version-{target}", "percentage": 100, "message": message}],
        }

    monkeypatch.setattr(publication, "checked_build", checked_build)
    monkeypatch.setattr(publication, "freeze_worker", freeze_worker)
    monkeypatch.setattr(publication, "destination", destination)
    monkeypatch.setattr(publication, "current_deployment", lambda _, target: current[target])
    monkeypatch.setattr(publication, "remote_database_digest", lambda _: publication.sha256(database))
    monkeypatch.setattr(publication, "deploy_frozen", deploy)
    run = tmp_path / "run"
    run.mkdir()
    operations = maps.prepare(ctx, {"targets": ["legacy", "canonical"]}, run)
    return SimpleNamespace(
        ctx=ctx,
        source=source,
        build=build,
        tile=tile,
        database=database,
        images=images,
        current=current,
        calls=calls,
        operations=operations,
    )


def test_build_once_and_canonical_before_legacy(prepared: SimpleNamespace) -> None:
    assert prepared.calls == ["build"]
    canonical, legacy = prepared.operations
    assert [canonical["target"], legacy["target"]] == ["canonical", "legacy"]
    assert legacy["dependencies"] == [canonical["id"]]
    assert canonical["payload"]["assets"] == legacy["payload"]["assets"]
    assert canonical["payload"]["guard"] == "preflight-and-postflight"
    assert "concurrent writer" in canonical["recovery"]


def test_same_size_tile_edit_invalidates_native_freshness(prepared: SimpleNamespace) -> None:
    operation = prepared.operations[0]
    prepared.tile.write_bytes(b"EDIT")
    with pytest.raises(ValueError, match="stale"):
        maps.check(prepared.ctx, operation, operation["payload"], {})
    assert prepared.calls == ["build"]


@pytest.mark.parametrize("which", ["source", "output", "frozen", "image", "lockfile", "legacy-config", "worker"])
def test_every_source_and_output_byte_is_bound(prepared: SimpleNamespace, which: str) -> None:
    operation = prepared.operations[0]
    payload = operation["payload"]
    paths = {
        "source": prepared.source / "src" / "app.ts",
        "output": prepared.build / "map.html",
        "frozen": Path(payload["assets"]) / "map.html",
        "image": prepared.images / "catalog" / "item.png",
        "lockfile": prepared.ctx.repo_root / "pnpm-lock.yaml",
        "legacy-config": prepared.source / "wrangler.legacy.jsonc",
        "worker": Path(payload["bundle"]),
    }
    paths[which].write_bytes(b"changed")
    with pytest.raises(ValueError, match=r"changed|stale"):
        maps.check(prepared.ctx, operation, payload, {})
    assert prepared.calls == ["build"]


def test_missing_native_build_sidecar_refuses_deploy(prepared: SimpleNamespace) -> None:
    (prepared.build / build_info.BUILD_INFO_NAME).unlink()
    operation = prepared.operations[0]
    with pytest.raises(ValueError, match="stale"):
        maps.execute(prepared.ctx, operation, operation["payload"], {})
    assert prepared.calls == ["build"]


def test_changed_provider_base_stops_before_upload(prepared: SimpleNamespace) -> None:
    operation = prepared.operations[0]
    prepared.current["canonical"] = {"deployment_id": "editor-deploy", "versions": []}
    with pytest.raises(maps.MapGuardError, match="approved base") as caught:
        maps.execute(prepared.ctx, operation, operation["payload"], {})
    assert caught.value.evidence["safe_to_resume"] is True
    assert prepared.calls == ["build"]


def test_canonical_receipt_reconciles_and_legacy_resumes_without_canonical_upload(
    prepared: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    canonical, legacy = prepared.operations
    receipt = maps.execute(prepared.ctx, canonical, canonical["payload"], {})
    original_deploy = publication.deploy_frozen

    def failed_legacy(*_: Any, **__: Any) -> None:
        raise RuntimeError("lost response after request")

    monkeypatch.setattr(publication, "deploy_frozen", failed_legacy)
    receipts = {canonical["id"]: receipt}
    with pytest.raises(SurfaceUncertainError):
        maps.execute(prepared.ctx, legacy, legacy["payload"], receipts)
    maps.reconcile(prepared.ctx, canonical, canonical["payload"], receipt, receipts)
    # A safe-to-retry outcome must be established explicitly by the operator.
    # This models a reconciled no-write legacy attempt, not an automatic retry.
    monkeypatch.setattr(publication, "deploy_frozen", original_deploy)
    maps.execute(prepared.ctx, legacy, legacy["payload"], receipts)
    assert prepared.calls == ["build", "canonical", "legacy"]


def test_legacy_cannot_execute_without_canonical_receipt(prepared: SimpleNamespace) -> None:
    legacy = prepared.operations[1]
    with pytest.raises(maps.MapGuardError, match=r"requires.*canonical"):
        maps.execute(prepared.ctx, legacy, legacy["payload"], {})
    assert prepared.calls == ["build"]


def test_unknown_receipt_is_not_adopted(prepared: SimpleNamespace) -> None:
    operation = prepared.operations[0]
    with pytest.raises(ValueError, match="Unknown map receipt"):
        maps.reconcile(prepared.ctx, operation, operation["payload"], {}, {})


def test_lost_receipt_cannot_be_inferred_from_matching_bytes(
    prepared: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    operation = prepared.operations[0]
    monkeypatch.setattr(publication, "deploy_frozen", lambda *_, **__: None)
    with pytest.raises(SurfaceUncertainError, match="uniquely identifiable"):
        maps.execute(prepared.ctx, operation, operation["payload"], {})


def test_receipt_current_version_and_database_body_are_mandatory(
    prepared: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    operation = prepared.operations[0]
    receipt = maps.execute(prepared.ctx, operation, operation["payload"], {})
    monkeypatch.setattr(publication, "remote_database_digest", lambda _: "other-bytes")
    with pytest.raises(ValueError, match="Live map database bytes"):
        maps.reconcile(prepared.ctx, operation, operation["payload"], receipt, {})
    monkeypatch.setattr(publication, "remote_database_digest", lambda _: publication.sha256(prepared.database))
    prepared.current["canonical"] = {"deployment_id": "another", "versions": []}
    with pytest.raises(ValueError, match="changed before resume"):
        maps.reconcile(prepared.ctx, operation, operation["payload"], receipt, {})


def test_database_prerender_bytes_are_exact(prepared: SimpleNamespace) -> None:
    for operation in prepared.operations:
        assets = Path(operation["payload"]["assets"])
        assert (assets / "db" / "erenshor.sqlite").read_bytes() == prepared.database.read_bytes()
        assert operation["payload"]["database_route"]["path"] == "/db/erenshor.sqlite"
    (prepared.build / "db" / "erenshor.sqlite").write_bytes(b"not selected DB")
    with pytest.raises(ValueError, match="does not equal"):
        publication.verify_database(prepared.build, prepared.database)


def test_completed_receipt_cannot_hide_a_different_artifact_manifest(prepared: SimpleNamespace) -> None:
    operation = prepared.operations[0]
    receipt = maps.execute(prepared.ctx, operation, operation["payload"], {})
    receipt["asset_manifest_digest"] = "unreviewed"
    with pytest.raises(ValueError, match="approved operation"):
        maps.reconcile(prepared.ctx, operation, operation["payload"], receipt, {})


def test_source_edit_during_build_invalidates_preparation(
    prepared: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    def changing_build(_: Any) -> None:
        (prepared.source / "src" / "app.ts").write_text("changed during build")
        build_info.write_build_info(
            prepared.build,
            build_info.compute_input_hashes(maps_source_dir=prepared.source, database_path=prepared.database),
        )

    monkeypatch.setattr(publication, "checked_build", changing_build)
    with pytest.raises(ValueError, match="source bytes changed during"):
        maps.prepare(prepared.ctx, {"targets": ["canonical"]}, prepared.ctx.repo_root / "second-run")


def test_canonical_only_does_not_select_legacy(prepared: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(publication, "checked_build", lambda _: None)
    operations = maps.prepare(prepared.ctx, {"targets": ["canonical"]}, prepared.ctx.repo_root / "canonical-only")
    assert len(operations) == 1
    assert operations[0]["target"] == "canonical"
    assert operations[0]["dependencies"] == []


@pytest.mark.parametrize("filename", [".env.local", ".env.production.local", ".env.development"])
def test_private_env_is_rejected_before_build_and_never_hashed(
    prepared: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
    filename: str,
) -> None:
    (prepared.source / filename).write_text("CLOUDFLARE_API_TOKEN=private-value")
    monkeypatch.setattr(publication, "checked_build", lambda _: pytest.fail("built with private environment"))
    with pytest.raises(ValueError, match="Private map environment override") as caught:
        maps.prepare(prepared.ctx, {"targets": ["canonical"]}, prepared.ctx.repo_root / "private-run")
    assert "private-value" not in str(caught.value)


def test_nonpublic_assignment_in_public_env_is_rejected(prepared: SimpleNamespace) -> None:
    (prepared.source / ".env.production").write_text("SECRET_TOKEN=private-value")
    with pytest.raises(ValueError, match="non-public build input") as caught:
        maps._public_environment_inputs(prepared.source)
    assert "private-value" not in str(caught.value)


def test_private_env_added_after_prepare_refuses_deploy(prepared: SimpleNamespace) -> None:
    (prepared.source / ".env.local").write_text("SECRET_TOKEN=private-value")
    operation = prepared.operations[0]
    with pytest.raises(maps.MapGuardError, match="Private map environment override"):
        maps.execute(prepared.ctx, operation, operation["payload"], {})
    assert prepared.calls == ["build"]


def test_public_production_environment_is_pinned(prepared: SimpleNamespace) -> None:
    public = prepared.source / ".env.production"
    public.write_text("# Public analytics\nPUBLIC_ANALYTICS_TOKEN=public-token\n")
    assert maps._public_environment_inputs(prepared.source) == [public]


def test_image_pins_are_only_native_selected_catalog_pixels(prepared: SimpleNamespace) -> None:
    expected = {
        str(prepared.images / "catalog" / "item.png"),
        str(prepared.images / "catalog" / "portrait.png"),
    }
    for operation in prepared.operations:
        image_inputs = {path for path in operation["inputs"] if Path(path).is_relative_to(prepared.images)}
        assert image_inputs == expected
        snapshots = {
            snapshot["path"]
            for snapshot in operation["payload"]["input_snapshots"]
            if Path(snapshot["path"]).is_relative_to(prepared.images)
        }
        assert snapshots == expected


@pytest.mark.parametrize("relative", ["model-captures/unused.png", "catalog/hidden.png", "catalog.json"])
def test_unused_image_archive_changes_do_not_invalidate(prepared: SimpleNamespace, relative: str) -> None:
    (prepared.images / relative).write_bytes(b"changed unused image")
    operation = prepared.operations[0]
    maps.check(prepared.ctx, operation, operation["payload"], {})
    assert prepared.calls == ["build"]


def test_selected_character_pixels_invalidate(prepared: SimpleNamespace) -> None:
    (prepared.images / "catalog" / "portrait.png").write_bytes(b"edited portrait")
    operation = prepared.operations[0]
    with pytest.raises(maps.MapGuardError, match="Map input bytes changed"):
        maps.execute(prepared.ctx, operation, operation["payload"], {})
    assert prepared.calls == ["build"]


def test_fabricated_input_proof_cannot_skip_standalone_byte_guards(prepared: SimpleNamespace) -> None:
    operation = prepared.operations[0]
    operation["_input_proof"] = True
    (prepared.images / "catalog" / "item.png").write_bytes(b"changed item")
    with pytest.raises(maps.MapGuardError, match="Map input bytes changed"):
        maps.execute(prepared.ctx, operation, operation["payload"], {})
    assert prepared.calls == ["build"]


def test_preparation_never_traverses_image_archive(prepared: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
    original_iterdir = Path.iterdir

    def iterdir(path: Path) -> Any:
        if path.is_relative_to(prepared.images):
            pytest.fail(f"Traversed unused image archive: {path}")
        return original_iterdir(path)

    monkeypatch.setattr(Path, "iterdir", iterdir)
    monkeypatch.setattr(publication, "checked_build", lambda _: None)
    operations = maps.prepare(prepared.ctx, {"targets": ["canonical", "legacy"]}, prepared.ctx.repo_root / "no-archive")
    assert [operation["target"] for operation in operations] == ["canonical", "legacy"]
    for operation in operations:
        maps.check(prepared.ctx, operation, operation["payload"], {})


@pytest.fixture
def launch_plan(prepared: SimpleNamespace) -> SimpleNamespace:
    """Build real immutable records and payload files for the launch proof."""
    run = prepared.ctx.repo_root / "proof-plan"
    run.mkdir()
    operations = []
    for draft in prepared.operations:
        content = canonical(draft["payload"])
        name = draft["target"] + ".json"
        (run / name).write_bytes(content)
        value = {
            key: draft[key]
            for key in ("id", "kind", "target", "dependencies", "expected_base", "recovery", "destination")
        }
        value.update(
            payload_path=name,
            payload_sha256=sha256(content),
            inputs={path: coordinator._fingerprint(Path(path)) for path in draft["inputs"]},
        )
        operations.append(Operation.model_validate_json(canonical(value)))
    selection = {"schema_version": 1, "summary": "Map proof fixture", "maps": {"targets": ["canonical", "legacy"]}}
    plan = PreparedPublishPlan(
        variant="main",
        game_build_id="fixture",
        selection=selection,
        configuration=coordinator.configuration(prepared.ctx, selection),
        inputs={},
        operations=operations,
    )
    plan.digest = plan.approval_digest()
    return SimpleNamespace(plan=plan, run=run)


def test_both_targets_share_launch_byte_evidence_without_archive_reads(
    prepared: SimpleNamespace, launch_plan: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_open, original_iterdir = Path.open, Path.iterdir
    original_compute = build_info.compute_input_hashes
    original_current = publication.current_deployment
    pixel_reads: dict[Path, int] = {}
    freshness_calls = []
    remote_targets = []

    def opening(path: Path, *args: Any, **kwargs: Any) -> Any:
        mode = args[0] if args else kwargs.get("mode", "r")
        if path.is_relative_to(prepared.images) and "r" in mode and "b" in mode:
            pixel_reads[path] = pixel_reads.get(path, 0) + 1
        return original_open(path, *args, **kwargs)

    def iterdir(path: Path) -> Any:
        if path.is_relative_to(prepared.images):
            pytest.fail(f"Traversed image archive during publication: {path}")
        return original_iterdir(path)

    def compute(**kwargs: Any) -> dict[str, str]:
        freshness_calls.append(kwargs)
        return original_compute(**kwargs)

    def current(source: Path, target: str) -> dict[str, Any]:
        remote_targets.append(target)
        return original_current(source, target)

    monkeypatch.setattr(Path, "open", opening)
    monkeypatch.setattr(Path, "iterdir", iterdir)
    monkeypatch.setattr(build_info, "compute_input_hashes", compute)
    monkeypatch.setattr(publication, "current_deployment", current)
    proof = coordinator.ExecutionInputProof(launch_plan.plan, prepared.ctx, launch_plan.run)
    monkeypatch.setattr(maps, "_snapshot", lambda _: pytest.fail("Rehashed a launch-verified map input"))
    receipts = {}
    for operation in prepared.operations:
        operation["_input_proof"] = proof
        maps.check(prepared.ctx, operation, operation["payload"], receipts)
        receipt = maps.execute(prepared.ctx, operation, operation["payload"], receipts)
        receipts[operation["id"]] = receipt
        maps.reconcile(prepared.ctx, operation, operation["payload"], receipt, receipts)
    assert pixel_reads == {
        prepared.images / "catalog" / "item.png": 1,
        prepared.images / "catalog" / "portrait.png": 1,
    }
    assert len(freshness_calls) == 1
    assert set(remote_targets) == {"canonical", "legacy"}
    assert remote_targets.count("canonical") > remote_targets.count("legacy")
    assert prepared.calls == ["build", "canonical", "legacy"]


@pytest.mark.parametrize("which", ["image", "tile", "output", "frozen", "worker", "config", "database"])
def test_cached_launch_evidence_rejects_changed_local_bytes(
    prepared: SimpleNamespace, launch_plan: SimpleNamespace, which: str
) -> None:
    proof = coordinator.ExecutionInputProof(launch_plan.plan, prepared.ctx, launch_plan.run)
    operation = prepared.operations[0]
    operation["_input_proof"] = proof
    payload = operation["payload"]
    maps.check(prepared.ctx, operation, payload, {})
    paths = {
        "image": prepared.images / "catalog" / "item.png",
        "tile": prepared.tile,
        "output": prepared.build / "map.html",
        "frozen": Path(payload["assets"]) / "map.html",
        "worker": Path(payload["bundle"]),
        "config": Path(payload["config"]),
        "database": prepared.database,
    }
    paths[which].write_bytes(b"changed after cached verification")
    with pytest.raises(maps.MapGuardError, match="changed"):
        maps.execute(prepared.ctx, operation, payload, {})
    assert prepared.calls == ["build"]


def test_cached_map_proof_ignores_unused_archive_edits_and_additions(
    prepared: SimpleNamespace, launch_plan: SimpleNamespace
) -> None:
    proof = coordinator.ExecutionInputProof(launch_plan.plan, prepared.ctx, launch_plan.run)
    operation = prepared.operations[0]
    operation["_input_proof"] = proof
    maps.check(prepared.ctx, operation, operation["payload"], {})
    (prepared.images / "model-captures" / "unused.png").write_bytes(b"edited capture")
    (prepared.images / "model-captures" / "new.png").write_bytes(b"new capture")
    (prepared.images / "catalog" / "unused-new.png").write_bytes(b"unused new catalog pixels")
    maps.execute(prepared.ctx, operation, operation["payload"], {})
    assert prepared.calls == ["build", "canonical"]


def test_cached_local_proof_never_caches_remote_target_bases(
    prepared: SimpleNamespace, launch_plan: SimpleNamespace
) -> None:
    proof = coordinator.ExecutionInputProof(launch_plan.plan, prepared.ctx, launch_plan.run)
    canonical, legacy = prepared.operations
    for operation in prepared.operations:
        operation["_input_proof"] = proof
        maps.check(prepared.ctx, operation, operation["payload"], {})
    receipt = maps.execute(prepared.ctx, canonical, canonical["payload"], {})
    receipts = {canonical["id"]: receipt}
    prepared.current["legacy"] = {"deployment_id": "editor-legacy", "versions": []}
    with pytest.raises(maps.MapGuardError, match="approved base"):
        maps.execute(prepared.ctx, legacy, legacy["payload"], receipts)
    prepared.current["legacy"] = legacy["expected_base"]
    prepared.current["canonical"] = {"deployment_id": "editor-canonical", "versions": []}
    with pytest.raises(maps.MapGuardError, match="predecessor receipt"):
        maps.execute(prepared.ctx, legacy, legacy["payload"], receipts)
    assert prepared.calls == ["build", "canonical"]


def test_launch_evidence_preserves_complete_map_manifest_entries(
    prepared: SimpleNamespace, launch_plan: SimpleNamespace
) -> None:
    root = launch_plan.run / "complete-map-assets"
    (root / "__pycache__").mkdir(parents=True)
    (root / "__pycache__" / "asset.pyc").write_bytes(b"deployable asset")
    (root / "asset.pyc").write_bytes(b"another deployable asset")
    (root / ".DS_Store").write_bytes(b"reviewed bytes")
    launch_plan.plan.inputs[str(root)] = coordinator._fingerprint(root)
    launch_plan.plan.digest = launch_plan.plan.approval_digest()
    expected = publication.manifest(root)
    proof = coordinator.ExecutionInputProof(launch_plan.plan, prepared.ctx, launch_plan.run)
    assert proof.manifest(root) == expected


def test_private_install_and_dev_credentials_never_enter_map_input_pins(prepared: SimpleNamespace) -> None:
    private_files = [
        prepared.ctx.repo_root / ".npmrc",
        prepared.source / ".npmrc",
        prepared.source / ".dev.vars",
        prepared.source / ".dev.vars.production",
    ]
    for path in private_files:
        path.write_text("private-credential=not-a-build-input\n")
    inputs = maps._input_paths(prepared.ctx, prepared.source, prepared.database, prepared.build)
    assert not set(private_files) & set(inputs)
    for operation in prepared.operations:
        maps.check(prepared.ctx, operation, operation["payload"], {})
    for path in private_files:
        path.write_text("rotated-private-credential=still-not-a-build-input\n")
    for operation in prepared.operations:
        maps.check(prepared.ctx, operation, operation["payload"], {})
