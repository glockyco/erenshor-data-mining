"""Wrangler remains the single map deployment and provider inspection owner."""

from __future__ import annotations

import hashlib
import json
import subprocess
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from erenshor import __version__
from erenshor.application.maps import publication
from erenshor.cli.commands import maps
from erenshor.infrastructure.config.schema import MapsConfig


def test_provider_inspection_uses_wrangler_json_and_exact_version_ids(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    commands = []
    responses = [
        [
            {"id": "old", "created_on": "2026-01-01", "versions": [{"version_id": "v0", "percentage": 100}]},
            {"id": "active", "created_on": "2026-01-02", "versions": [{"version_id": "v1", "percentage": 100}]},
        ],
        {
            "id": "v1",
            "annotations": {"workers/message": "reviewed"},
            "resources": {"bindings": [{"secret_text": "not serialized"}]},
        },
    ]

    def run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        assert kwargs["check"] is True and kwargs["capture_output"] is True
        commands.append(args)
        return subprocess.CompletedProcess(args, 0, stdout=json.dumps(responses.pop(0)))

    monkeypatch.setattr(publication.subprocess, "run", run)
    current = publication.current_deployment(tmp_path, "canonical")
    assert current == {"deployment_id": "active", "versions": [{"id": "v1", "percentage": 100, "message": "reviewed"}]}
    assert commands == [
        ["pnpm", "exec", "wrangler", "deployments", "list", "--config", "wrangler.jsonc", "--json"],
        ["pnpm", "exec", "wrangler", "versions", "view", "v1", "--config", "wrangler.jsonc", "--json"],
    ]
    assert "secret_text" not in json.dumps(current)


def test_unreadable_provider_base_blocks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(publication, "wrangler_json", lambda *_: [])
    with pytest.raises(ValueError, match="no inspectable deployment"):
        publication.current_deployment(tmp_path, "legacy")


def test_ambiguous_account_is_not_selected_silently(
    bound_destination: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("CLOUDFLARE_ACCOUNT_ID", raising=False)
    monkeypatch.setattr(
        publication, "wrangler_json", lambda *_: {"loggedIn": True, "accounts": [{"id": "a"}, {"id": "b"}]}
    )
    with pytest.raises(ValueError, match="ambiguous"):
        publication.destination(bound_destination.ctx, "canonical")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "b")
    assert publication.destination(bound_destination.ctx, "canonical")["account_id"] == "b"


def test_frozen_deploy_keeps_checked_owner_and_never_rebundles(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    monkeypatch.setattr(maps, "_run", lambda command, cwd: calls.append((command, cwd)))
    config, bundle, assets = [
        tmp_path / part for part in ("frozen/wrangler.jsonc", "frozen/site-worker.js", "frozen/build")
    ]
    publication.deploy_frozen(tmp_path, "canonical", config, bundle, assets, "publish-map:digest")
    assert calls == [
        (
            [
                "pnpm",
                "exec",
                "wrangler",
                "deploy",
                "--config",
                str(config),
                str(bundle),
                "--no-bundle",
                "--assets",
                str(assets),
                "--message",
                "publish-map:digest",
            ],
            tmp_path,
        )
    ]


def test_remote_database_checks_body_without_following_a_different_host(monkeypatch: pytest.MonkeyPatch) -> None:
    body = b"unchanged selected database"
    reads = iter([body, b""])
    response = SimpleNamespace(status=200, url="https://example.test/db/erenshor.sqlite", read=lambda _: next(reads))

    class Response:
        def __enter__(self) -> Any:
            return response

        def __exit__(self, *_: Any) -> None:
            pass

    requests = []

    def read(request: Any, *, timeout: int) -> Response:
        requests.append((request, timeout))
        return Response()

    monkeypatch.setattr(publication, "urlopen", read)
    assert publication.remote_database_digest("https://example.test") == hashlib.sha256(body).hexdigest()
    assert len(requests) == 1
    request, timeout = requests[0]
    assert timeout == 60
    assert request.get_header("User-agent") == (
        f"ErenshorPublisher/{__version__} (+https://github.com/glockyco/erenshor-data-mining)"
    )
    assert "Mozilla" not in request.get_header("User-agent")
    assert request.get_header("Accept-encoding") == "identity"
    assert request.get_header("Cache-control") == "no-cache"
    response.url = "https://other.test/db/erenshor.sqlite"
    with pytest.raises(ValueError, match="own unchanged body"):
        publication.remote_database_digest("https://example.test")


def test_manifest_follows_directory_aliases_and_rejects_ancestor_cycles(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "asset").write_bytes(b"asset")
    aliases = tmp_path / "aliases"
    aliases.mkdir()
    (aliases / "first").symlink_to(source, target_is_directory=True)
    (aliases / "second").symlink_to(source, target_is_directory=True)
    assert set(publication.manifest(aliases)) == {"first/asset", "second/asset"}
    (source / "cycle").symlink_to(aliases, target_is_directory=True)
    with pytest.raises(ValueError, match="directory symlink cycle"):
        publication.manifest(aliases)


def test_native_freshness_reuses_one_source_observation_for_both_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from erenshor.application.maps import build_info

    source = tmp_path / "source"
    database = tmp_path / "clean.sqlite"
    builds = [tmp_path / "build", tmp_path / "frozen"]
    hashes = {"code": "code", "data": "data", "tiles": "tiles"}
    calls = []

    def compute(**kwargs: Any) -> dict[str, str]:
        calls.append(kwargs)
        return hashes

    monkeypatch.setattr(build_info, "compute_input_hashes", compute)
    for build in builds:
        build_info.write_build_info(build, hashes)
    current = build_info.compute_input_hashes(maps_source_dir=source, database_path=database)
    for build in builds:
        publication.assert_fresh(source, build, database, input_hashes=current)
    assert calls == [{"maps_source_dir": source, "database_path": database}]
    build_info.write_build_info(builds[1], {**hashes, "tiles": "changed"})
    with pytest.raises(ValueError, match="stale"):
        publication.assert_fresh(source, builds[1], database, input_hashes=current)


@pytest.fixture
def bound_destination(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    configured = MapsConfig(
        source_dir=str(tmp_path),
        base_url="https://maps.example.test",
        legacy_base_url="https://map-legacy.fixture.workers.dev",
    )
    ctx = SimpleNamespace(
        repo_root=tmp_path,
        variant="main",
        config=SimpleNamespace(
            variants={
                "main": SimpleNamespace(maps=configured),
                "playtest": SimpleNamespace(
                    maps=configured.model_copy(update={"base_url": "https://maps.playtest.example.test"})
                ),
            }
        ),
    )
    configs = {
        "canonical": {
            "name": "map-site",
            "main": "worker.ts",
            "routes": [{"pattern": "maps.example.test", "custom_domain": True}],
            "workers_dev": False,
        },
        "legacy": {"name": "map-legacy", "main": "worker.ts", "routes": [], "workers_dev": True},
    }
    domain = {
        "id": "domain-id",
        "hostname": "maps.example.test",
        "service": "map-site",
        "environment": "production",
        "enabled": True,
    }
    account_subdomain = {"subdomain": "fixture"}
    script_subdomain = {"enabled": True}
    reads = []

    def read(_: Path, resource: str) -> Any:
        reads.append(resource)
        if resource.endswith("/workers/subdomain"):
            return account_subdomain
        if "/scripts/" in resource and resource.endswith("/subdomain"):
            return script_subdomain
        if "/domains?" in resource:
            return [domain]
        pytest.fail(f"Unexpected provider read: {resource}")

    monkeypatch.delenv("CLOUDFLARE_ACCOUNT_ID", raising=False)
    monkeypatch.setattr(publication, "service_config", lambda _, target: configs[target])
    monkeypatch.setattr(publication, "wrangler_json", lambda *_: {"loggedIn": True, "accounts": [{"id": "account"}]})
    monkeypatch.setattr(publication, "_cloudflare_read", read)
    return SimpleNamespace(
        ctx=ctx,
        configured=configured,
        configs=configs,
        domain=domain,
        account_subdomain=account_subdomain,
        script_subdomain=script_subdomain,
        reads=reads,
    )


def test_destination_binds_configured_origins_to_actual_account_services(bound_destination: SimpleNamespace) -> None:
    canonical = publication.destination(bound_destination.ctx, "canonical")
    legacy = publication.destination(bound_destination.ctx, "legacy")
    assert canonical["url"] == bound_destination.configured.base_url
    assert legacy["url"] == bound_destination.configured.legacy_base_url
    assert canonical["host_binding"] == {
        "kind": "custom_domain",
        "domain_id": "domain-id",
        "environment": "production",
    }
    assert legacy["host_binding"] == {"kind": "workers_dev", "account_subdomain": "fixture"}
    assert bound_destination.reads == [
        "/accounts/account/workers/domains?hostname=maps.example.test",
        "/accounts/account/workers/subdomain",
        "/accounts/account/workers/scripts/map-legacy/subdomain",
    ]


@pytest.mark.parametrize(
    "field,value",
    [
        ("hostname", "other.example.test"),
        ("service", "other-service"),
        ("environment", "staging"),
        ("enabled", False),
    ],
)
def test_destination_rejects_mismatched_live_custom_domain(
    bound_destination: SimpleNamespace, field: str, value: Any
) -> None:
    bound_destination.domain[field] = value
    with pytest.raises(ValueError, match="not bound"):
        publication.destination(bound_destination.ctx, "canonical")


@pytest.mark.parametrize(
    "routes",
    [[], [{"pattern": "other.example.test", "custom_domain": True}], [{"pattern": "maps.example.test/*"}]],
)
def test_destination_rejects_wrong_wrangler_custom_domain(
    bound_destination: SimpleNamespace, routes: list[Any]
) -> None:
    bound_destination.configs["canonical"]["routes"] = routes
    with pytest.raises(ValueError, match="Wrangler configuration"):
        publication.destination(bound_destination.ctx, "canonical")
    assert bound_destination.reads == []


@pytest.mark.parametrize("which", ["service", "account", "disabled", "config"])
def test_destination_rejects_wrong_workers_dev_host_or_disabled_service(
    bound_destination: SimpleNamespace, which: str
) -> None:
    if which == "service":
        bound_destination.configs["legacy"]["name"] = "another-worker"
    elif which == "account":
        bound_destination.account_subdomain["subdomain"] = "another-account"
    elif which == "disabled":
        bound_destination.script_subdomain["enabled"] = False
    else:
        bound_destination.configs["legacy"]["workers_dev"] = False
    with pytest.raises(ValueError, match=r"subdomain|not enabled|workers_dev"):
        publication.destination(bound_destination.ctx, "legacy")


def test_destination_rejects_two_targets_using_the_same_postflight_host(bound_destination: SimpleNamespace) -> None:
    bound_destination.configured.legacy_base_url = bound_destination.configured.base_url
    with pytest.raises(ValueError, match="distinct origins"):
        publication.destination(bound_destination.ctx, "canonical")
    assert bound_destination.reads == []


def test_playtest_origin_cannot_use_the_main_wrangler_configuration(bound_destination: SimpleNamespace) -> None:
    bound_destination.ctx.variant = "playtest"
    with pytest.raises(ValueError, match="Wrangler configuration"):
        publication.destination(bound_destination.ctx, "canonical")
    assert bound_destination.reads == []


def test_playtest_uses_its_configured_origin_and_bound_service(bound_destination: SimpleNamespace) -> None:
    bound_destination.ctx.variant = "playtest"
    bound_destination.configs["canonical"].update(
        name="map-site-playtest",
        routes=[{"pattern": "maps.playtest.example.test", "custom_domain": True}],
    )
    bound_destination.domain.update(hostname="maps.playtest.example.test", service="map-site-playtest")
    result = publication.destination(bound_destination.ctx, "canonical")
    assert result["url"] == "https://maps.playtest.example.test"
    assert result["service"] == "map-site-playtest"


@pytest.mark.parametrize(
    "value",
    [
        "http://maps.example.test",
        "https://maps.example.test/map",
        "https://user:secret@maps.example.test",
        "https://maps.example.test:443",
    ],
)
def test_destination_requires_an_unambiguous_https_origin(bound_destination: SimpleNamespace, value: str) -> None:
    bound_destination.configured.base_url = value
    with pytest.raises(ValueError, match="HTTPS origins"):
        publication.destination(bound_destination.ctx, "canonical")


@pytest.mark.parametrize(
    "credentials,header,value",
    [
        ({"type": "oauth", "token": "private-oauth"}, "Authorization", "Bearer private-oauth"),
        ({"type": "api_token", "token": "private-token"}, "Authorization", "Bearer private-token"),
        ({"type": "api_key", "key": "private-key", "email": "owner@example.test"}, "X-auth-key", "private-key"),
    ],
)
def test_hostname_reads_use_native_selected_credentials_only_for_get_requests(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    credentials: dict[str, str],
    header: str,
    value: str,
) -> None:
    native_calls = []
    url = "https://api.cloudflare.com/client/v4/accounts/account/workers/subdomain"

    def native(source: Path, args: list[str]) -> dict[str, str]:
        native_calls.append((source, args))
        return credentials

    class Response(BytesIO):
        status = 200

    def read(request: Any, **kwargs: Any) -> Response:
        assert request.get_method() == "GET"
        assert request.full_url == url
        assert request.get_header(header) == value
        assert kwargs == {"timeout": 60}
        response = Response(json.dumps({"success": True, "result": {"subdomain": "fixture"}}).encode())
        response.url = url
        return response

    monkeypatch.setattr(publication, "wrangler_json", native)
    monkeypatch.setattr(publication, "urlopen", read)
    assert publication._cloudflare_read(tmp_path, "/accounts/account/workers/subdomain") == {"subdomain": "fixture"}
    assert native_calls == [(tmp_path, ["auth", "token"])]


def test_hostname_read_errors_never_expose_credential_or_provider_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(publication, "wrangler_json", lambda *_: {"type": "oauth", "token": "private-secret"})

    def failure(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("provider-content private-secret")

    monkeypatch.setattr(publication, "urlopen", failure)
    with pytest.raises(ValueError, match="association is unreadable") as error:
        publication._cloudflare_read(tmp_path, "/accounts/account/workers/subdomain")
    assert "private-secret" not in str(error.value)
    assert "provider-content" not in str(error.value)
