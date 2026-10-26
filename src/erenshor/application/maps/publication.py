"""Checked map build, frozen Wrangler deployment, and read-only provider evidence."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen

from erenshor import __version__

from . import build_info

if TYPE_CHECKING:
    from erenshor.cli.context import CLIContext

CONFIGS = {"canonical": "wrangler.jsonc", "legacy": "wrangler.legacy.jsonc"}


def sha256(path: Path) -> str:
    """Hash actual bytes, including same-size edits."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifest(root: Path) -> dict[str, dict[str, Any]]:
    """Describe every file, following symlinks and rejecting ancestor cycles."""
    if not root.is_dir():
        raise ValueError(f"Map artifact/input directory is missing: {root}")
    result: dict[str, dict[str, Any]] = {}

    def visit(directory: Path, ancestors: frozenset[tuple[int, int]]) -> None:
        stat = directory.stat()
        identity = (stat.st_dev, stat.st_ino)
        if identity in ancestors:
            raise ValueError(f"Map artifact/input has a directory symlink cycle: {directory}")
        descendants = ancestors | {identity}
        for path in sorted(directory.iterdir(), key=lambda entry: entry.name):
            if path.is_dir():
                visit(path, descendants)
            elif path.is_file():
                result[path.relative_to(root).as_posix()] = {
                    "sha256": sha256(path),
                    "size": path.stat().st_size,
                }
            else:
                raise ValueError(f"Map artifact/input is not a readable regular file: {path}")

    visit(root, frozenset())
    return result


def checked_build(ctx: CLIContext) -> None:
    """Use the standalone command's declared preconditions and checked build."""
    from erenshor.cli.commands.maps import build

    build(SimpleNamespace(obj=ctx), skip_checks=False)


def assert_fresh(
    maps_dir: Path, build_dir: Path, database: Path, *, input_hashes: dict[str, str] | None = None
) -> None:
    """Keep native provenance, reusing source evidence only inside a sealed guard."""
    previous = build_info.read_build_info(build_dir)
    current = (
        input_hashes
        if input_hashes is not None
        else build_info.compute_input_hashes(maps_source_dir=maps_dir, database_path=database)
    )
    if previous is None or build_info.changed_groups(previous, current):
        raise ValueError("Map build is stale. Prepare and review a new publication plan.")


def wrangler_json(maps_dir: Path, args: list[str]) -> Any:
    """Inspect Cloudflare using the installed Wrangler, never another API client."""
    result = subprocess.run(
        ["pnpm", "exec", "wrangler", *args, "--json"],
        cwd=maps_dir,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def service_config(maps_dir: Path, target: str) -> dict[str, Any]:
    """Let Wrangler parse its own JSONC and resolve its entry point."""
    script = (
        "const w=require('wrangler');"
        "const c=w.unstable_readConfig({config:process.argv[1]},{hideWarnings:true});"
        "console.log(JSON.stringify({name:c.name,account_id:c.account_id,main:c.main,"
        "routes:c.routes,workers_dev:c.workers_dev}));"
    )
    result = subprocess.run(
        ["node", "-e", script, str(maps_dir / CONFIGS[target])],
        cwd=maps_dir,
        check=True,
        capture_output=True,
        text=True,
    )
    config: dict[str, Any] = json.loads(result.stdout)
    if not config.get("name") or not config.get("main"):
        raise ValueError(f"Wrangler configuration does not identify {target}")
    return config


def _origin(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Map publication URLs must be HTTPS origins without credentials, ports or paths")
    return f"https://{parsed.hostname}"


def _cloudflare_read(maps_dir: Path, resource: str) -> Any:
    """Use Wrangler-selected credentials only in memory for a read-only API request."""
    try:
        credentials = wrangler_json(maps_dir, ["auth", "token"])
        headers = {"Accept": "application/json"}
        if credentials.get("type") in {"oauth", "api_token"} and credentials.get("token"):
            headers["Authorization"] = f"Bearer {credentials['token']}"
        elif credentials.get("type") == "api_key" and credentials.get("key") and credentials.get("email"):
            headers.update({"X-Auth-Key": credentials["key"], "X-Auth-Email": credentials["email"]})
        else:
            raise ValueError("Unreadable native credentials")
        url = "https://api.cloudflare.com/client/v4" + resource
        request = Request(url, headers=headers, method="GET")
        with urlopen(request, timeout=60) as response:
            if response.status != 200 or response.url != url:
                raise ValueError("Unexpected provider response")
            body = json.load(response)
        if not isinstance(body, dict) or body.get("success") is not True or "result" not in body:
            raise ValueError("Unreadable provider metadata")
        return body["result"]
    except Exception:
        # Provider and credential output must not enter reports or error logs.
        raise ValueError("Cloudflare hostname association is unreadable with the selected Wrangler account") from None


def destination(ctx: CLIContext, target: str) -> dict[str, Any]:
    """Bind a configured origin to its actual Wrangler account and live service."""
    maps = ctx.config.variants[ctx.variant].maps
    maps_dir = maps.resolved_source_dir(ctx.repo_root)
    origins = {"canonical": _origin(maps.base_url), "legacy": _origin(maps.legacy_base_url)}
    if origins["canonical"] == origins["legacy"]:
        raise ValueError("Canonical and legacy map destinations must use distinct origins")
    origin = origins[target]
    hostname = urlsplit(origin).hostname
    config = service_config(maps_dir, target)
    identity = wrangler_json(maps_dir, ["whoami"])
    accounts = {account["id"] for account in identity.get("accounts", [])}
    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID") or config.get("account_id")
    if account_id is None and len(accounts) == 1:
        account_id = next(iter(accounts))
    if not identity.get("loggedIn") or not account_id or account_id not in accounts:
        raise ValueError("Wrangler account is unreadable or ambiguous. Select an authenticated account explicitly.")
    account_path = f"/accounts/{quote(account_id, safe='')}/workers"
    service = config["name"]
    if hostname and hostname.endswith(".workers.dev"):
        if config.get("workers_dev") is not True:
            raise ValueError("Configured map origin requires workers_dev in the selected Wrangler configuration")
        subdomain = _cloudflare_read(maps_dir, account_path + "/subdomain")
        if not isinstance(subdomain, dict) or not isinstance(subdomain.get("subdomain"), str):
            raise ValueError("Cloudflare account workers.dev subdomain is unreadable")
        expected = f"{service}.{subdomain['subdomain']}.workers.dev"
        if hostname != expected:
            raise ValueError("Configured map origin does not match the Wrangler service and account subdomain")
        state = _cloudflare_read(maps_dir, account_path + f"/scripts/{quote(service, safe='')}/subdomain")
        if not isinstance(state, dict) or state.get("enabled") is not True:
            raise ValueError("Configured map workers.dev hostname is not enabled for the selected service")
        binding = {"kind": "workers_dev", "account_subdomain": subdomain["subdomain"]}
    else:
        routes = config.get("routes") or []
        if not any(
            isinstance(route, dict) and route.get("custom_domain") is True and route.get("pattern") == hostname
            for route in routes
        ):
            raise ValueError(
                "Configured map origin is not an exact Custom Domain in the selected Wrangler configuration"
            )
        domains = _cloudflare_read(maps_dir, account_path + "/domains?" + urlencode({"hostname": hostname}))
        if not isinstance(domains, list) or len(domains) != 1:
            raise ValueError("Cloudflare map Custom Domain association is unreadable or ambiguous")
        domain = domains[0]
        if (
            not isinstance(domain, dict)
            or not domain.get("id")
            or domain.get("hostname") != hostname
            or domain.get("service") != service
            or domain.get("environment") != "production"
            or domain.get("enabled") is not True
        ):
            raise ValueError("Configured map Custom Domain is not bound to the selected live Worker service")
        binding = {"kind": "custom_domain", "domain_id": domain["id"], "environment": domain["environment"]}
    return {
        "provider": "cloudflare",
        "account_id": account_id,
        "service": config["name"],
        "url": origin,
        "routes": config.get("routes", []),
        "workers_dev": config.get("workers_dev"),
        "host_binding": binding,
    }


def current_deployment(maps_dir: Path, target: str) -> dict[str, Any]:
    """Capture the active deployment and every traffic-bearing version."""
    deployments = wrangler_json(maps_dir, ["deployments", "list", "--config", CONFIGS[target]])
    if not isinstance(deployments, list) or not deployments:
        raise ValueError(f"Cloudflare has no inspectable deployment for {target}")
    latest = max(deployments, key=lambda entry: entry["created_on"])
    if not latest.get("id") or not latest.get("versions"):
        raise ValueError(f"Cloudflare deployment identifiers are missing for {target}")
    versions = []
    for traffic in latest["versions"]:
        version_id = traffic.get("version_id")
        if not version_id or not isinstance(traffic.get("percentage"), (int, float)):
            raise ValueError("Cloudflare deployment has unreadable version traffic")
        version = wrangler_json(
            maps_dir,
            ["versions", "view", version_id, "--config", CONFIGS[target]],
        )
        if version.get("id") != version_id:
            raise ValueError("Cloudflare version identity does not match its deployment")
        # Do not serialize bindings or account credentials from version resources.
        versions.append(
            {
                "id": version_id,
                "percentage": traffic["percentage"],
                "message": version.get("annotations", {}).get("workers/message"),
            }
        )
    return {"deployment_id": latest["id"], "versions": sorted(versions, key=lambda version: version["id"])}


def freeze_worker(maps_dir: Path, target: str, output: Path) -> Path:
    """Bundle locally through the existing checked Wrangler deploy helper."""
    from erenshor.cli.commands.maps import _deploy_command, _run

    _run(
        [*_deploy_command("site" if target == "canonical" else target, dry_run=True), "--outdir", str(output)], maps_dir
    )
    main = Path(service_config(maps_dir, target)["main"])
    bundle = output / f"{main.stem}.js"
    if not bundle.is_file():
        raise ValueError(f"Wrangler did not emit the expected deployable Worker: {bundle}")
    # Wrangler's generated README contains a clock value and is not deployed.
    (output / "README.md").unlink(missing_ok=True)
    return bundle


def deploy_frozen(maps_dir: Path, target: str, config: Path, bundle: Path, assets: Path, *, message: str) -> None:
    """Deploy the approved bundle and assets through the standalone checked runner."""
    from erenshor.cli.commands.maps import _deploy_command, _run

    command = _deploy_command("site" if target == "canonical" else target, dry_run=False)
    command[command.index("--config") + 1] = str(config)
    _run([*command, str(bundle), "--no-bundle", "--assets", str(assets), "--message", message], maps_dir)


def verify_database(build_dir: Path, database: Path) -> str:
    """Require the prerendered compatibility URL to contain unchanged database bytes."""
    body = build_dir / "db" / "erenshor.sqlite"
    expected = sha256(database)
    if not body.is_file() or sha256(body) != expected:
        raise ValueError("Prerendered /db/erenshor.sqlite does not equal the selected clean database")
    return expected


def remote_database_digest(url: str) -> str:
    """Read the public compatibility route without introducing an HTTP writer."""
    # Public hosts can reject urllib's default signature before serving their assets.
    request = Request(
        f"{url}/db/erenshor.sqlite",
        headers={
            "Cache-Control": "no-cache",
            "Accept-Encoding": "identity",
            "User-Agent": (f"ErenshorPublisher/{__version__} (+https://github.com/glockyco/erenshor-data-mining)"),
        },
    )
    digest = hashlib.sha256()
    with urlopen(request, timeout=60) as response:
        if response.status != 200 or response.url != f"{url}/db/erenshor.sqlite":
            raise ValueError("Map database URL did not return its own unchanged body")
        for chunk in iter(lambda: response.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
