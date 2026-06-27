---
title: Maps CLI Build/Deploy Consolidation
type: plan
status: implemented
created: 2026-06-26
parent:
archived: 2026-06-27
---

# Maps CLI Build/Deploy Consolidation — Implementation Plan

> **For agentic workers:** Implement task-by-task. New logic (build-info, precondition
> checks) is TDD with the test shown first. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Make `uv run erenshor maps {dev,preview,build,deploy,thumbnails}` the single
command surface for the maps site, with non-bypassable preconditions, so the footgun npm
scripts disappear and a stale or unverified build can't be deployed.

**Architecture:** The `erenshor maps` Typer CLI already exists but shells out to `pnpm run X`
(indirection that collides with pnpm's `deploy` builtin and silently drops `--port`). We make
the CLI call tools directly (`pnpm exec vite|wrangler`, `node scripts/…`, `uv run erenshor mod
publish`), delete the redundant npm command-scripts, and add `@require_preconditions` checks
that mirror the pattern `extract`/`wiki`/`sheets`/`golden` already use. `build` verifies then
builds and stamps a content-hash provenance sidecar; `deploy` is a pure resumable `wrangler
deploy` that refuses unless the build's stamped input hashes still match the working tree.

**Tech stack:** Python 3 / Typer / Rich (CLI), pytest, SvelteKit + Vite + adapter-static,
wrangler (Cloudflare), dotnet (mods).

## Locked decisions (from the design discussion)

- **Build and deploy are separate, single-purpose commands.** `deploy` NEVER rebuilds — it
  stays a pure `wrangler deploy` so a network-interrupted upload resumes via wrangler's
  content-hash incremental upload (verified: our deploy showed "105 new, 18604 already
  uploaded"). Rebuilding would re-hash every asset and force a full re-upload.
- **Staleness = input-equivalence, not age.** `build` writes `build/.build-info.json` with
  per-group content hashes (code / data / mods / tiles). `deploy` recomputes and blocks on
  mismatch, naming the changed group. A resume of an unchanged build matches → deploys
  regardless of age. An absolute-age check is explicitly rejected (it would block resumes).
- **Verify lives in `build`** (lint + svelte-check + `vitest run`), before compiling. `deploy`
  stays pure. No verify on the deploy path.
- **No bypass flags.** No `--force`, no `--skip-checks`, no `--allow-stale`. The remedy for any
  deploy block is the single command `erenshor maps build` (always available, idempotent). A
  guardrail that can be bypassed is not a guardrail.
- **The CLI is the only surface.** The npm command-scripts (`dev/build/preview/deploy/prebuild/
  thumbnails`, root `dev/build/preview`) are deleted. Only precondition-free primitives that
  hooks/CI/the CLI call stay (`check/lint/lint:fix/format/format:check/test/prepare`).
- **`maps build` is idempotent** — always rebuilds, overwriting `build/`. The freshness gate
  now lives at deploy, so build needs no `--force`/refuse guard.

## File structure

| Action | Path | Responsibility |
|---|---|---|
| Create | `src/erenshor/application/maps/__init__.py` | package marker |
| Create | `src/erenshor/application/maps/build_info.py` | compute/write/read/compare input-hash provenance |
| Create | `src/erenshor/cli/preconditions/checks/maps.py` | `build_exists`, `build_matches_inputs`, `cloudflare_auth_configured` |
| Modify | `src/erenshor/cli/preconditions/decorator.py` | add maps paths to the check context |
| Modify | `src/erenshor/cli/commands/maps.py` | rewrite 5 commands: direct tool calls, preconditions, verify-in-build, build-info stamp |
| Modify | `src/maps/package.json` | delete command-scripts; `test` → `vitest run` |
| Modify | `package.json` (root) | delete `dev/build/preview` proxies |
| Modify | `src/erenshor/infrastructure/config/schema.py` | delete unused `MapsConfig.deploy_target` |
| Create | `src/mods/Directory.Build.props` | demote MSB3277 to a message |
| Modify | `AGENTS.md` | stage × side-effect command map; "CLI is the only surface" rule; golden-capture clarification |
| Modify | `.agent/skills/mod-pipeline/SKILL.md` | replace `npm run build`/`wrangler deploy` snippets with `erenshor maps …` |
| Modify | `src/maps/README.md` | slim to point at CLI `--help`; drop false "D1" claim |
| Create | `tests/unit/maps/test_build_info.py` | build_info unit tests |
| Create | `tests/unit/preconditions/test_maps_checks.py` | maps precondition unit tests |

---

## Phase 1 — Provenance + preconditions (new code, TDD)

### Task 1.1: `build_info` module

**Files:** Create `src/erenshor/application/maps/__init__.py` (empty), `src/erenshor/application/maps/build_info.py`; Test `tests/unit/maps/test_build_info.py`.

Input groups and what each hashes:
- **code** — every `*.ts,*.js,*.svelte,*.css,*.html,*.json` under `src/maps/src` plus `src/maps/{svelte.config.js,vite.config.ts,package.json,tailwind config}` → sha256 over sorted `(relpath, sha256(bytes))`.
- **data** — sha256 of the canonical clean DB file (the variant DB, e.g. `variants/main/erenshor-main.sqlite`).
- **mods** — sha256 over sorted `(name, sha256(bytes))` of `src/maps/static/mods/*.dll` + `src/maps/static/mods-metadata.json`.
- **tiles** — sha256 of `src/maps/static/tiles/tiles-manifest.json` bytes + the `(file_count, total_bytes)` of `src/maps/static/tiles`.

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/maps/test_build_info.py
from pathlib import Path
import json
from erenshor.application.maps import build_info


def _mk_inputs(tmp: Path) -> dict:
    maps_src = tmp / "maps" / "src"; maps_src.mkdir(parents=True)
    (maps_src / "a.ts").write_text("export const x = 1;")
    db = tmp / "clean.sqlite"; db.write_bytes(b"DBV1")
    mods = tmp / "maps" / "static" / "mods"; mods.mkdir(parents=True)
    (mods / "Mod.dll").write_bytes(b"DLL1")
    (tmp / "maps" / "static" / "mods-metadata.json").write_text('{"v":1}')
    tiles = tmp / "maps" / "static" / "tiles"; tiles.mkdir(parents=True)
    (tiles / "tiles-manifest.json").write_text('{"zoom_levels":{}}')
    return {"maps_source_dir": tmp / "maps", "database_path": db}


def test_hash_is_deterministic(tmp_path):
    ins = _mk_inputs(tmp_path)
    h1 = build_info.compute_input_hashes(**ins)
    h2 = build_info.compute_input_hashes(**ins)
    assert h1 == h2
    assert set(h1) == {"code", "data", "mods", "tiles"}


def test_data_change_flips_only_data(tmp_path):
    ins = _mk_inputs(tmp_path)
    before = build_info.compute_input_hashes(**ins)
    ins["database_path"].write_bytes(b"DBV2")
    after = build_info.compute_input_hashes(**ins)
    assert build_info.changed_groups(before, after) == {"data"}


def test_code_change_flips_only_code(tmp_path):
    ins = _mk_inputs(tmp_path)
    before = build_info.compute_input_hashes(**ins)
    (ins["maps_source_dir"] / "src" / "a.ts").write_text("export const x = 2;")
    after = build_info.compute_input_hashes(**ins)
    assert build_info.changed_groups(before, after) == {"code"}


def test_write_then_read_roundtrip_atomic(tmp_path):
    build = tmp_path / "build"; build.mkdir()
    hashes = {"code": "a", "data": "b", "mods": "c", "tiles": "d"}
    build_info.write_build_info(build, hashes)
    assert not list(build.glob("*.tmp"))  # atomic: no leftover temp
    assert build_info.read_build_info(build) == hashes


def test_read_missing_returns_none(tmp_path):
    assert build_info.read_build_info(tmp_path) is None
```

- [ ] **Step 2: Run, verify fail** — `uv run pytest tests/unit/maps/test_build_info.py -v` → FAIL (module missing).

- [ ] **Step 3: Implement**

```python
# src/erenshor/application/maps/build_info.py
"""Content-hash provenance for the maps build.

`erenshor maps build` stamps build/.build-info.json with a hash per input group;
`erenshor maps deploy` recomputes and refuses to ship a build whose inputs have
changed. Equivalence is by content, not timestamp, so resuming an unchanged build
always matches regardless of age.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

BUILD_INFO_NAME = ".build-info.json"  # dot-prefixed: wrangler does not serve it
_CODE_EXTS = {".ts", ".js", ".svelte", ".css", ".html", ".json"}
_CODE_CONFIG = ("svelte.config.js", "vite.config.ts", "package.json")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hash_files(paths: list[Path], root: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(paths, key=lambda x: str(x.relative_to(root))):
        h.update(str(p.relative_to(root)).encode())
        h.update(_sha(p.read_bytes()).encode())
    return h.hexdigest()


def _code_hash(maps_source_dir: Path) -> str:
    src = maps_source_dir / "src"
    files = [p for p in src.rglob("*") if p.is_file() and p.suffix in _CODE_EXTS]
    files += [maps_source_dir / n for n in _CODE_CONFIG if (maps_source_dir / n).is_file()]
    return _hash_files(files, maps_source_dir)


def _mods_hash(maps_source_dir: Path) -> str:
    static = maps_source_dir / "static"
    files = sorted((static / "mods").glob("*.dll")) if (static / "mods").is_dir() else []
    meta = static / "mods-metadata.json"
    if meta.is_file():
        files.append(meta)
    return _hash_files(files, static) if files else ""


def _tiles_hash(maps_source_dir: Path) -> str:
    tiles = maps_source_dir / "static" / "tiles"
    manifest = tiles / "tiles-manifest.json"
    h = hashlib.sha256()
    h.update(manifest.read_bytes() if manifest.is_file() else b"")
    count = total = 0
    if tiles.is_dir():
        for p in tiles.rglob("*"):
            if p.is_file():
                count += 1
                total += p.stat().st_size
    h.update(f"{count}:{total}".encode())
    return h.hexdigest()


def compute_input_hashes(*, maps_source_dir: Path, database_path: Path) -> dict[str, str]:
    """Per-group content hashes of everything the build bakes in."""
    return {
        "code": _code_hash(maps_source_dir),
        "data": _sha(database_path.read_bytes()) if database_path.is_file() else "",
        "mods": _mods_hash(maps_source_dir),
        "tiles": _tiles_hash(maps_source_dir),
    }


def changed_groups(before: dict[str, str], after: dict[str, str]) -> set[str]:
    """Group names whose hash differs (or is missing on either side)."""
    return {g for g in set(before) | set(after) if before.get(g) != after.get(g)}


def write_build_info(build_dir: Path, hashes: dict[str, str]) -> None:
    """Atomically stamp the sidecar (tmp + rename) so a half-build never looks fresh."""
    target = build_dir / BUILD_INFO_NAME
    tmp = build_dir / f"{BUILD_INFO_NAME}.{os.getpid()}.tmp"
    tmp.write_text(json.dumps(hashes, indent=2, sort_keys=True))
    tmp.replace(target)


def read_build_info(build_dir: Path) -> dict[str, str] | None:
    target = build_dir / BUILD_INFO_NAME
    if not target.is_file():
        return None
    try:
        data = json.loads(target.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None
```

- [ ] **Step 4: Run, verify pass** — `uv run pytest tests/unit/maps/test_build_info.py -v` → PASS.
- [ ] **Step 5: Commit** — `feat(cli): add maps build-info provenance hashing`.

### Task 1.2: maps precondition checks

**Files:** Create `src/erenshor/cli/preconditions/checks/maps.py`; Test `tests/unit/preconditions/test_maps_checks.py`.

Context keys these consume (added in Task 1.3): `build_dir`, `maps_source_dir`, `database_path` (already present).

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/preconditions/test_maps_checks.py
from pathlib import Path
from erenshor.cli.preconditions.checks import maps as mc
from erenshor.application.maps import build_info


def _ctx(tmp: Path) -> dict:
    maps = tmp / "maps"; (maps / "src").mkdir(parents=True)
    (maps / "src" / "a.ts").write_text("x")
    (maps / "static" / "mods").mkdir(parents=True)
    (maps / "static" / "tiles").mkdir(parents=True)
    (maps / "static" / "tiles" / "tiles-manifest.json").write_text("{}")
    db = tmp / "clean.sqlite"; db.write_bytes(b"DB")
    build = maps / "build"; build.mkdir()
    return {"build_dir": build, "maps_source_dir": maps, "database_path": db}


def test_build_exists_fails_when_missing(tmp_path):
    ctx = _ctx(tmp_path); ctx["build_dir"].rmdir()
    r = mc.build_exists(ctx)
    assert not r.passed and "maps build" in r.detail


def test_matches_passes_for_fresh_build(tmp_path):
    ctx = _ctx(tmp_path)
    build_info.write_build_info(ctx["build_dir"], build_info.compute_input_hashes(
        maps_source_dir=ctx["maps_source_dir"], database_path=ctx["database_path"]))
    assert mc.build_matches_inputs(ctx).passed


def test_matches_fails_and_names_group_on_data_change(tmp_path):
    ctx = _ctx(tmp_path)
    build_info.write_build_info(ctx["build_dir"], build_info.compute_input_hashes(
        maps_source_dir=ctx["maps_source_dir"], database_path=ctx["database_path"]))
    ctx["database_path"].write_bytes(b"DB-CHANGED")
    r = mc.build_matches_inputs(ctx)
    assert not r.passed and "data" in r.message and "maps build" in r.detail


def test_matches_fails_when_no_sidecar(tmp_path):
    ctx = _ctx(tmp_path)  # build/ exists but never stamped
    r = mc.build_matches_inputs(ctx)
    assert not r.passed and "maps build" in r.detail


def test_cloudflare_auth_passes_with_token(tmp_path, monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok")
    ctx = _ctx(tmp_path)
    assert mc.cloudflare_auth_configured(ctx).passed
```

- [ ] **Step 2: Run, verify fail** — `uv run pytest tests/unit/preconditions/test_maps_checks.py -v`.

- [ ] **Step 3: Implement** (mirror `steam.py`/`database.py` style; return `PreconditionResult` with actionable `detail`)

```python
# src/erenshor/cli/preconditions/checks/maps.py
"""Maps build/deploy precondition checks."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from erenshor.application.maps import build_info

from ..base import PreconditionResult


def build_exists(context: dict[str, Any]) -> PreconditionResult:
    build_dir = Path(context["build_dir"])
    if build_dir.is_dir() and any(build_dir.iterdir()):
        return PreconditionResult(True, "build_exists", f"Build present at {build_dir}")
    return PreconditionResult(
        False, "build_exists", "No build to deploy",
        detail="Run `erenshor maps build` to produce build/ before deploying.",
    )


def build_matches_inputs(context: dict[str, Any]) -> PreconditionResult:
    build_dir = Path(context["build_dir"])
    recorded = build_info.read_build_info(build_dir)
    if recorded is None:
        return PreconditionResult(
            False, "build_matches_inputs", "Build has no provenance stamp",
            detail="This build predates provenance tracking. Run `erenshor maps build`.",
        )
    current = build_info.compute_input_hashes(
        maps_source_dir=Path(context["maps_source_dir"]),
        database_path=Path(context["database_path"]),
    )
    changed = build_info.changed_groups(recorded, current)
    if not changed:
        return PreconditionResult(True, "build_matches_inputs", "Build matches current inputs")
    return PreconditionResult(
        False, "build_matches_inputs",
        f"Build is stale: {', '.join(sorted(changed))} changed since it was built",
        detail="Run `erenshor maps build` to rebuild against current inputs.",
    )


def cloudflare_auth_configured(context: dict[str, Any]) -> PreconditionResult:
    if os.environ.get("CLOUDFLARE_API_TOKEN"):
        return PreconditionResult(True, "cloudflare_auth_configured", "Cloudflare API token set")
    maps_dir = Path(context["maps_source_dir"])
    if shutil.which("pnpm"):
        try:
            r = subprocess.run(
                ["pnpm", "exec", "wrangler", "whoami"],
                cwd=maps_dir, capture_output=True, timeout=30, check=False,
            )
            if r.returncode == 0:
                return PreconditionResult(True, "cloudflare_auth_configured", "wrangler session active")
        except (subprocess.SubprocessError, OSError):
            pass
    return PreconditionResult(
        False, "cloudflare_auth_configured", "No Cloudflare credentials",
        detail="Set CLOUDFLARE_API_TOKEN (+ CLOUDFLARE_ACCOUNT_ID) or run `pnpm -C src/maps exec wrangler login`.",
    )
```

- [ ] **Step 4: Run, verify pass.**
- [ ] **Step 5: Commit** — `feat(cli): add maps build/deploy precondition checks`.

### Task 1.3: extend the precondition context with maps paths

**Files:** Modify `src/erenshor/cli/preconditions/decorator.py:141-152` (`_build_check_context` return dict).

- [ ] **Step 1:** Add three keys to the returned dict (after `backups_dir`):

```python
        "maps_source_dir": variant_config.maps.resolved_source_dir(cli_ctx.repo_root),
        "build_dir": variant_config.maps.resolved_build_dir(cli_ctx.repo_root),
        "maps_db_path": variant_config.maps.resolved_database_dir(cli_ctx.repo_root) / "erenshor.sqlite",
```

- [ ] **Step 2:** Run the existing precondition tests to confirm no regression — `uv run pytest tests/unit/preconditions -v`.
- [ ] **Step 3: Commit** — `feat(cli): expose maps paths to precondition checks`.

---

## Phase 2 — Rewrite the maps CLI as the sole orchestrator

All commands in `src/erenshor/cli/commands/maps.py`. Replace every `["pnpm", "run", X]`
subprocess with a direct tool call. Add a small helper:

```python
def _run(cmd: list[str], cwd: Path, *, env: dict | None = None) -> None:
    """Run a step, streaming output; raise typer.Exit on failure."""
    result = subprocess.run(cmd, cwd=cwd, env=env, check=False)
    if result.returncode != 0:
        console.print(f"[red]Step failed ({' '.join(cmd[:2])}…): exit {result.returncode}[/red]")
        raise typer.Exit(result.returncode)
```

### Task 2.1: `build` — verify → prebuild → copy DB → vite build → stamp

**Files:** `src/erenshor/cli/commands/maps.py` (`build`, lines ~280-393).

- [ ] **Step 1:** Decorate and rewrite. Add at top of file:
  `from erenshor.cli.preconditions import require_preconditions`,
  `from erenshor.cli.preconditions.checks.database import database_exists, database_valid, database_has_items`,
  `from erenshor.application.maps import build_info`.
- [ ] **Step 2:** New `build` flow (drop `--force` param and the refuse-if-exists guard; keep pnpm/node_modules guards; keep DB copy):
  1. `@require_preconditions(database_exists, database_valid, database_has_items)`
  2. **verify:** `_run(["pnpm","run","lint"], maps_dir)`; `_run(["pnpm","run","check"], maps_dir)`; `_run(["pnpm","run","test"], maps_dir)`
  3. **prebuild (internalized):** `_run(["uv","run","erenshor","mod","publish"], repo_root)`; `_run(["node","scripts/generate-tiles-manifest.js"], maps_dir)`; `_run(["node","scripts/generate-og-image.mjs"], maps_dir)`
  4. copy canonical DB → `maps_db_path` (existing `shutil.copy2` logic, lines 342-351)
  5. **build:** `_run(["pnpm","exec","vite","build"], maps_dir)`
  6. **stamp:** `build_info.write_build_info(build_dir, build_info.compute_input_hashes(maps_source_dir=maps_dir, database_path=db_path))`
  7. success panel + next-steps (`maps preview` / `maps deploy`)
- [ ] **Step 3:** Manually verify the sequence prints a clear breadcrumb per step.
- [ ] **Step 4: Commit** — `refactor(cli): maps build verifies, orchestrates prebuild, stamps provenance`.

### Task 2.2: `deploy` — pure resumable upload, gated by preconditions

**Files:** `src/erenshor/cli/commands/maps.py` (`deploy`, lines ~396-470).

- [ ] **Step 1:** Decorate `@require_preconditions(build_exists, build_matches_inputs, cloudflare_auth_configured)` (import from `checks.maps`). Keep the `cli_ctx.dry_run` branch.
- [ ] **Step 2:** Replace `["pnpm","run","deploy"]` with `["pnpm","exec","wrangler","deploy"]` (cwd `maps_dir`). No build, no verify. Update dry-run line to print `pnpm exec wrangler deploy (in {maps_dir})`.
- [ ] **Step 3: Commit** — `refactor(cli): maps deploy is a pure resumable wrangler upload behind preconditions`.

### Task 2.3: `dev` / `preview` — direct vite, fix `--port`

**Files:** `src/erenshor/cli/commands/maps.py` (`dev` ~175, `preview` ~261).

- [ ] **Step 1:** `dev`: replace `["pnpm","run","dev","--","--port",str(port)]` with `["pnpm","exec","vite","dev","--port",str(port)]`. Drop the now-redundant `env["PORT"]`. Keep DB symlink + cleanup.
- [ ] **Step 2:** `preview`: replace `["pnpm","run","preview","--","--port",str(port)]` with `["pnpm","exec","vite","preview","--port",str(port)]`.
- [ ] **Step 3:** Commit — `fix(cli): maps dev/preview forward --port via direct vite invocation`.

### Task 2.4: `thumbnails` — direct node script

**Files:** `src/erenshor/cli/commands/maps.py` (`thumbnails` ~507).

- [ ] **Step 1:** Replace `["pnpm","run","thumbnails"] + zones` with `["node","scripts/generate-thumbnails.mjs", *zones]` (cwd `maps_dir`, keep `MAPS_URL` env).
- [ ] **Step 2:** Commit — `refactor(cli): maps thumbnails calls the node script directly`.

---

## Phase 3 — Delete the parallel surface + dead config

### Task 3.1: `src/maps/package.json` scripts

- [ ] Delete `dev`, `prebuild`, `build`, `preview`, `deploy`, `check:watch`, `test:ui`, `thumbnails`. Change `"test": "vitest"` → `"test": "vitest run"`. **Keep:** `prepare`, `check`, `lint`, `lint:fix`, `format`, `format:check`, `test`.
- [ ] Verify nothing else references the deleted scripts: `search "run (dev|build|preview|deploy|thumbnails)" + "pnpm --filter erenshor-maps (dev|build|preview)"`.
- [ ] Commit — `chore(map): drop redundant npm command-scripts (CLI owns build/deploy/dev)`.

### Task 3.2: root `package.json` proxies

- [ ] Delete `dev`, `build`, `preview` (lines 6-8). Keep `prepare`, `check`, `lint`, `lint:fix`, `format`.
- [ ] Commit — `chore: drop root maps proxy scripts`.

### Task 3.3: remove dead `deploy_target` config

- [ ] `search "deploy_target"` across repo → confirm `MapsConfig.deploy_target` is never read (only the unrelated `mod._get_deploy_target_dir`).
- [ ] Delete `MapsConfig.deploy_target` field (`schema.py:447-450`).
- [ ] `uv run pytest tests/ -k config` to confirm config still loads.
- [ ] Commit — `chore(config): remove unused MapsConfig.deploy_target`.

---

## Phase 4 — Quiet the MSB3277 wall

### Task 4.1: `src/mods/Directory.Build.props`

- [ ] Create:

```xml
<!-- Applies to every mod project. MSB3277 (assembly-version conflicts during
     ResolveAssemblyReference) is benign here: game/Unity refs are Private=false
     (runtime-provided) and ILRepack excludes System.* shims. Demote to a message
     so it stays in -v normal / binlogs but doesn't bury real errors. NoWarn does
     not work — MSB3277 is an MSBuild task warning, not a compiler one. -->
<Project>
  <PropertyGroup>
    <MSBuildWarningsAsMessages>$(MSBuildWarningsAsMessages);MSB3277</MSBuildWarningsAsMessages>
  </PropertyGroup>
</Project>
```

- [ ] Verify: `uv run erenshor mod build --mod interactive-map-companion` → no MSB3277 lines, still "Build succeeded".
- [ ] Commit — `chore(mod): demote benign MSB3277 to a build message`.

---

## Phase 5 — Docs as the single agent-facing truth

### Task 5.1: `AGENTS.md`

- [ ] In **Essential Commands**, add a compact maps line and a one-line rule (pair prohibition + alternative):
  `uv run erenshor maps build` / `uv run erenshor maps deploy` — build then deploy the maps site (separate steps; deploy resumes). Rule: *drive every subsystem through `uv run erenshor …`; never `pnpm build`/`wrangler deploy`/`dotnet build` directly.*
- [ ] Add a short **command map** organized by stage (acquire → build → develop → publish → verify) tagging external-publish commands, so an agent knows the canonical command per task across components.
- [ ] Fix the golden-capture line: clarify it gates the **data pipeline** (`tests/golden/`), not a frontend-only maps redeploy.
- [ ] Commit — `docs: add maps commands + CLI-only rule to AGENTS.md`.

### Task 5.2: `.agent/skills/mod-pipeline/SKILL.md`

- [ ] Replace the `npm run build` / `wrangler deploy` snippets in "Website Build" and "Deploy New Mod Version" with `uv run erenshor maps build` / `uv run erenshor maps deploy`. Keep the skill focused on the mod side; link to `src/maps/README.md` / AGENTS.md for maps.
- [ ] Commit — `docs(mod-pipeline): stop teaching the raw build/deploy path`.

### Task 5.3: `src/maps/README.md`

- [ ] Drop the false "Cloudflare Workers + D1" claim (no D1 binding). Slim the command list to: "use `uv run erenshor maps <cmd>` — run `--help`"; keep the "don't use `pnpm dev` directly (the CLI manages the DB)" note and state *why* (the symlink). Add prereqs (dotnet + `mod setup`, `uv`, `pnpm install`, the clean DB).
- [ ] Commit — `docs(map): point README at the CLI; fix stack description`.

---

## Phase 6 — Verification

- [ ] `cd src/maps && pnpm run lint && pnpm run check && pnpm run test` → green.
- [ ] `uv run pytest tests/unit/maps tests/unit/preconditions -v` → green.
- [ ] **Real build:** `uv run erenshor maps build` → verify runs, prebuild runs, `build/.build-info.json` written, build succeeds.
- [ ] **Stale block:** touch the clean DB (or `extract build`), then `uv run erenshor maps deploy` → blocks naming `data`, hint says run `maps build`. Rebuild → deploy proceeds.
- [ ] **Resume case:** with a fresh matching build, `uv run erenshor maps deploy` passes preconditions (proves age-independence).
- [ ] **Missing-creds:** unset `CLOUDFLARE_API_TOKEN` and (if applicable) logged-out → deploy blocks with the actionable hint.
- [ ] **`--port`:** `uv run erenshor maps dev --port 5180` actually binds 5180.
- [ ] **Footgun gone:** `pnpm run deploy` (in src/maps) → "script not found"; `pnpm build` (root) → gone.
- [ ] **Hooks/CI unaffected:** `lefthook run pre-commit` on a maps file still lints; CI yaml unchanged and still references only kept scripts.
- [ ] Deploy for real once green.

## Self-review notes

- Spec coverage: CLI-only surface (P2,P3) ✓; preconditions incl. cloudflare (P1.2) ✓; input-equivalence staleness, no bypass (P1.1,P2.2) ✓; verify-in-build (P2.1) ✓; separate build/deploy, deploy never rebuilds (P2.1/2.2) ✓; MSB3277 (P4) ✓; docs/dead-config (P3.3,P5) ✓.
- No placeholders: new modules/checks/tests have full code; command rewrites specify exact call sequences against the read line ranges.
- Type consistency: `compute_input_hashes(*, maps_source_dir, database_path)`, `changed_groups`, `read/write_build_info` used identically in checks + tests.

## Out of scope (separate follow-ups)

- **Correctness bugs:** `generate-mods-metadata.py` hardcodes 2 mod dirs (4 mods get wrong versions); dirty-tree DLL-vs-metadata version mismatch.
- **`mod publish --skip-unchanged`** incremental rebuild (perf; the build's full mod rebuild is tolerable as-is).
- **Two-worker domain migration** (`wrangler.jsonc` + redirect worker) — tracked in `2026-06-26-maps-domain-url-migration`.
- **Aligning `mod`/`capture`/`images`/`eval`** to `@require_preconditions` (broader CLI consistency pass).
