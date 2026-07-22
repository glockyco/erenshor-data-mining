"""Unit tests for wiki CLI commands."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.main import get_command
from typer.testing import CliRunner

# Patch the decorator BEFORE importing the command module
with patch("erenshor.cli.preconditions.require_preconditions") as mock_decorator:
    # Make it a passthrough decorator
    mock_decorator.side_effect = lambda *checks: lambda func: func
    from erenshor.cli.main import app

from erenshor.application.wiki.services.page import OperationResult
from erenshor.application.wiki_deploy.manifest import RepoWikiPageManifest, RepoWikiPageManifestEntry
from erenshor.application.wiki_deploy.override_classifier import ArticleOverrideClassification, OverrideFieldDecision
from erenshor.application.wiki_deploy.override_migration import ArticleMigration, ArticleOverrideReview
from erenshor.application.wiki_deploy.pages import RepoPageDeployResult, RepoPageDeployResultEntry
from erenshor.application.wiki_deploy.refresh import EmbeddedRefreshResult
from erenshor.application.wiki_deploy.rollback import RollbackResult, RollbackResultEntry

runner = CliRunner()


@pytest.fixture
def mock_operation_result():
    """Create mock operation result."""
    return OperationResult(
        total=10,
        succeeded=10,
        skipped=0,
        failed=0,
        warnings=[],
        errors=[],
    )


@pytest.fixture
def mock_operation_result_with_warnings():
    """Create mock operation result with warnings."""
    return OperationResult(
        total=10,
        succeeded=9,
        skipped=0,
        failed=0,
        warnings=["Manual edit preserved: Item:Iron Sword"],
        errors=[],
    )


@pytest.fixture
def mock_operation_result_with_failures():
    """Create mock operation result with failures."""
    return OperationResult(
        total=10,
        succeeded=8,
        skipped=0,
        failed=2,
        warnings=[],
        errors=["Failed to update Item:Broken Sword", "Failed to update Item:Missing Item"],
    )


class TestWikiFetchCommand:
    """Test wiki fetch command."""

    @patch("erenshor.cli.commands.wiki._create_wiki_service")
    def test_fetch_success(self, mock_create_service, mock_operation_result):
        """Test successful fetch."""
        mock_service = MagicMock()
        mock_service.fetch_all.return_value = mock_operation_result
        mock_create_service.return_value = mock_service

        result = runner.invoke(app, ["wiki", "fetch"])

        assert result.exit_code == 0
        mock_service.fetch_all.assert_called_once()

    @patch("erenshor.cli.commands.wiki._create_wiki_service")
    def test_fetch_with_limit(self, mock_create_service, mock_operation_result):
        """Test fetch with limit parameter."""
        mock_service = MagicMock()
        mock_service.fetch_all.return_value = mock_operation_result
        mock_create_service.return_value = mock_service

        result = runner.invoke(app, ["wiki", "fetch", "--limit", "5"])

        assert result.exit_code == 0
        mock_service.fetch_all.assert_called_once()

    @patch("erenshor.cli.commands.wiki._create_wiki_service")
    def test_fetch_with_force(self, mock_create_service, mock_operation_result):
        """Test fetch with force flag."""
        mock_service = MagicMock()
        mock_service.fetch_all.return_value = mock_operation_result
        mock_create_service.return_value = mock_service

        result = runner.invoke(app, ["wiki", "fetch", "--force"])

        assert result.exit_code == 0
        mock_service.fetch_all.assert_called_once()

    @patch("erenshor.cli.commands.wiki._create_wiki_service")
    def test_fetch_dry_run(self, mock_create_service, mock_operation_result):
        """Test fetch in dry-run mode."""
        mock_service = MagicMock()
        mock_service.fetch_all.return_value = mock_operation_result
        mock_create_service.return_value = mock_service

        result = runner.invoke(app, ["--dry-run", "wiki", "fetch"])

        assert result.exit_code == 0
        mock_service.fetch_all.assert_called_once()


class TestWikiGenerateCommand:
    """Test wiki generate command."""

    @patch("erenshor.cli.commands.wiki._create_wiki_service")
    def test_generate_success(self, mock_create_service, mock_operation_result):
        """Test successful generate."""
        mock_service = MagicMock()
        mock_service.generate_all.return_value = mock_operation_result
        mock_create_service.return_value = mock_service

        result = runner.invoke(app, ["wiki", "generate"])

        assert result.exit_code == 0
        mock_service.generate_all.assert_called_once()
        # Generated articles are the legacy path; the next step must reflect the gated cutover.
        assert "deploy-repo-pages" in result.output
        assert "--legacy-article-deploy" in result.output

    @patch("erenshor.cli.commands.wiki._create_wiki_service")
    def test_generate_with_limit(self, mock_create_service, mock_operation_result):
        """Test generate with limit parameter."""
        mock_service = MagicMock()
        mock_service.generate_all.return_value = mock_operation_result
        mock_create_service.return_value = mock_service

        result = runner.invoke(app, ["wiki", "generate", "--limit", "5"])

        assert result.exit_code == 0
        mock_service.generate_all.assert_called_once()

    @patch("erenshor.cli.commands.wiki._create_wiki_service")
    def test_generate_dry_run(self, mock_create_service, mock_operation_result):
        """Test generate in dry-run mode."""
        mock_service = MagicMock()
        mock_service.generate_all.return_value = mock_operation_result
        mock_create_service.return_value = mock_service

        result = runner.invoke(app, ["--dry-run", "wiki", "generate"])

        assert result.exit_code == 0
        mock_service.generate_all.assert_called_once()

    @patch("erenshor.cli.commands.wiki._create_wiki_service")
    def test_generate_with_warnings(self, mock_create_service, mock_operation_result_with_warnings):
        """Test generate that completes with warnings."""
        mock_service = MagicMock()
        mock_service.generate_all.return_value = mock_operation_result_with_warnings
        mock_create_service.return_value = mock_service

        result = runner.invoke(app, ["wiki", "generate"])

        # Should exit 0 even with warnings
        assert result.exit_code == 0
        mock_service.generate_all.assert_called_once()

    def test_generate_lua_passes_faction_and_class_dependencies(self, monkeypatch: pytest.MonkeyPatch):
        """Test generation receives the concrete faction and class services."""
        import erenshor.cli.commands.wiki as wiki_command

        repositories = tuple(MagicMock(name=f"repo_{index}") for index in range(11))
        generation = MagicMock(written_paths=[], validation_tools={})
        monkeypatch.setattr(wiki_command, "_create_lua_repositories", lambda _ctx: repositories)
        generate = MagicMock(return_value=generation)
        monkeypatch.setattr(wiki_command, "generate_lua_data_modules", generate)

        result = runner.invoke(app, ["wiki", "generate-lua"])

        assert result.exit_code == 0
        kwargs = generate.call_args.kwargs
        assert kwargs["faction_repo"] is repositories[9]
        assert kwargs["class_display"] is repositories[10]

    def test_lua_repository_factory_shares_one_read_only_database(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        """Test every Lua repository and class service use one read-only connection."""
        from types import SimpleNamespace

        import erenshor.cli.commands.wiki as wiki_command

        cli_ctx = SimpleNamespace(
            repo_root=tmp_path,
            variant="main",
            config=SimpleNamespace(
                variants={
                    "main": SimpleNamespace(resolved_database=lambda _root: tmp_path / "clean.sqlite"),
                }
            ),
        )
        connection = object()
        database_calls: list[tuple[Path, bool]] = []

        def fake_database(path: Path, *, read_only: bool):
            database_calls.append((path, read_only))
            return connection

        monkeypatch.setattr(wiki_command, "DatabaseConnection", fake_database)
        constructors = (
            "ItemRepository",
            "CharacterRepository",
            "SpawnPointRepository",
            "LootTableRepository",
            "SpellRepository",
            "SkillRepository",
            "StanceRepository",
            "QuestRepository",
            "ZoneRepository",
            "FactionRepository",
            "ClassDisplayNameService",
        )
        constructor_connections: list[object] = []

        for name in constructors:

            def make_constructor(_name: str):
                def constructor(received_connection):
                    constructor_connections.append(received_connection)
                    return MagicMock(name=_name)

                return constructor

            monkeypatch.setattr(wiki_command, name, make_constructor(name))

        repositories = wiki_command._create_lua_repositories(cli_ctx)

        assert len(repositories) == len(constructors)
        assert database_calls == [(tmp_path / "clean.sqlite", True)]
        assert constructor_connections == [connection] * len(constructors)

    def test_generate_lua_dry_run_reports_output_without_writing(self):
        """Test dry-run reports every Lua data module path without writing files."""
        result = runner.invoke(app, ["--dry-run", "wiki", "generate-lua"])

        assert result.exit_code == 0
        assert "Dry run" in result.output
        for module in (
            "Items.lua",
            "Characters.lua",
            "Links.lua",
            "Spells.lua",
            "Skills.lua",
            "Quests.lua",
            "Zones.lua",
            "Stances.lua",
        ):
            assert module in result.output
        assert "variants/main/wiki/lua/Erenshor/Data/Items.lua" in result.output
        assert "variants/main/wiki/lua/Erenshor/Data/Items" in result.output
        assert "variants/main/wiki/lua/Erenshor/Data/Characters.lua" in result.output
        assert "variants/main/wiki/lua/Erenshor/Data/Links.lua" in result.output
        assert "variants/main/wiki/lua/Erenshor/Data/Quests.lua" in result.output
        assert "variants/main/wiki/lua/Erenshor/Data/Zones.lua" in result.output


class TestWikiInventoryTemplatesCommand:
    """Test wiki template inventory command."""

    def test_inventory_templates_writes_manifest_from_recorded_fixtures(self, tmp_path: Path):
        """Test template inventory writes ownership manifest from recorded API fixtures."""
        output_path = tmp_path / "ownership.yml"

        result = runner.invoke(
            app,
            [
                "wiki",
                "inventory-templates",
                "--fixture-dir",
                "tests/fixtures/wiki_inventory",
                "--output",
                str(output_path),
            ],
        )

        assert result.exit_code == 0
        manifest = output_path.read_text(encoding="utf-8")
        assert "title: Template:Item" in manifest
        assert "ownership: repo_owned_template" in manifest
        assert "cutover_blocking: true" in manifest
        assert "Wrote template ownership manifest" in result.output


class TestWikiSyncInterfaceCommand:
    """Test wiki interface sync command."""

    def test_sync_interface_command_metadata_describes_local_preview_mirror(self):
        """Test sync-interface exposes the local preview bootstrap command."""
        wiki_command = get_command(app).commands["wiki"]
        sync_command = wiki_command.commands["sync-interface"]

        assert sync_command.help is not None
        assert "Sync live MediaWiki interface pages for local preview." in sync_command.help
        assert "wiki-dev/interface" in sync_command.help


class TestWikiDeployCommand:
    """Test wiki deploy command."""

    @patch("erenshor.cli.commands.wiki._create_wiki_service")
    def test_deploy_success(self, mock_create_service, mock_operation_result):
        """Test successful deploy."""
        mock_service = MagicMock()
        mock_service.deploy_all.return_value = mock_operation_result
        mock_create_service.return_value = mock_service

        result = runner.invoke(app, ["wiki", "deploy", "--legacy-article-deploy"])

        assert result.exit_code == 0
        mock_service.deploy_all.assert_called_once()

    @patch("erenshor.cli.commands.wiki._create_wiki_service")
    def test_deploy_with_limit(self, mock_create_service, mock_operation_result):
        """Test deploy with limit parameter."""
        mock_service = MagicMock()
        mock_service.deploy_all.return_value = mock_operation_result
        mock_create_service.return_value = mock_service

        result = runner.invoke(app, ["wiki", "deploy", "--legacy-article-deploy", "--limit", "5"])

        assert result.exit_code == 0
        mock_service.deploy_all.assert_called_once()

    @patch("erenshor.cli.commands.wiki._create_wiki_service")
    def test_deploy_dry_run(self, mock_create_service, mock_operation_result):
        """Test deploy in dry-run mode."""
        mock_service = MagicMock()
        mock_service.deploy_all.return_value = mock_operation_result
        mock_create_service.return_value = mock_service

        result = runner.invoke(app, ["--dry-run", "wiki", "deploy", "--legacy-article-deploy"])

        assert result.exit_code == 0
        mock_service.deploy_all.assert_called_once()

    @patch("erenshor.cli.commands.wiki._create_wiki_service")
    def test_deploy_with_failures(self, mock_create_service, mock_operation_result_with_failures):
        """Test deploy that completes with failures."""
        mock_service = MagicMock()
        mock_service.deploy_all.return_value = mock_operation_result_with_failures
        mock_create_service.return_value = mock_service

        result = runner.invoke(app, ["wiki", "deploy", "--legacy-article-deploy"])

        # Should exit 1 with failures
        assert result.exit_code == 1
        mock_service.deploy_all.assert_called_once()


class TestWikiDeployRepoCommand:
    """Test repo-owned wiki deploy command."""

    def test_deploy_repo_pages_writes_deployment_manifest(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        """Test repo-owned page deploy persists revision metadata and rollback sources."""
        import erenshor.cli.commands.wiki as wiki_command

        source_path = tmp_path / "Item.lua"
        source_path.write_text("return {}\n", encoding="utf-8")
        manifest = RepoWikiPageManifest(
            entries=(
                RepoWikiPageManifestEntry(
                    title="Module:Erenshor/Item",
                    source_path=source_path.as_posix(),
                    source_sha256="abc",
                    ownership_class="lua_module",
                    upload_stage="lua_module",
                    content_model="Scribunto",
                    declares_cargo_table=False,
                    cargo_tables=(),
                ),
            )
        )
        client = FakeDeployClient()
        readonly = MagicMock()
        readonly.page_exists.return_value = True
        calls = []

        def fake_build_manifest(repo_root, variant, **kwargs):
            calls.append(("build", repo_root, variant, kwargs))
            return manifest

        def fake_create_client(cli_ctx):
            calls.append(("create_client", cli_ctx.variant))
            return client

        def fake_deploy_repo_pages(**kwargs):
            calls.append(("deploy", kwargs))
            return RepoPageDeployResult(
                entries=(
                    RepoPageDeployResultEntry(
                        title="Module:Erenshor/Item",
                        status="edited",
                        old_revision_id=10,
                        old_revision_timestamp="2026-06-04T12:00:00Z",
                        new_revision_id=11,
                        rollback_text_source="rollback/Module_Erenshor_Item.wiki",
                    ),
                )
            )

        def fake_write_manifest(deployed_manifest, path):
            calls.append(("write_manifest", deployed_manifest, path))

        monkeypatch.setattr(wiki_command, "build_repo_page_manifest", fake_build_manifest)
        monkeypatch.setattr(wiki_command, "_create_readonly_mediawiki_client", lambda _ctx: readonly)
        monkeypatch.setattr(wiki_command, "_create_mediawiki_client", fake_create_client)
        monkeypatch.setattr(wiki_command, "deploy_repo_pages", fake_deploy_repo_pages)
        monkeypatch.setattr(wiki_command, "write_repo_page_manifest", fake_write_manifest)

        manifest_output = tmp_path / "deploy-manifest.json"
        result = runner.invoke(app, ["wiki", "deploy-repo-pages", "--manifest-output", str(manifest_output)])

        assert result.exit_code == 0
        assert "Edited: 1" in result.output
        assert client.closed is True
        _, deploy_kwargs = calls[2]
        assert deploy_kwargs["rollback_root"] == tmp_path / "rollback"
        _, deployed_manifest, written_path = calls[3]
        assert written_path == manifest_output
        [entry] = deployed_manifest.entries
        assert entry.old_revision_id == 10
        assert entry.old_revision_timestamp == "2026-06-04T12:00:00Z"
        assert entry.new_revision_id == 11
        assert entry.rollback_text_source == "rollback/Module_Erenshor_Item.wiki"

    def test_deploy_repo_pages_passes_explicit_scope_flags(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        """Test generated data and maintained content require independent opt-ins."""
        import erenshor.cli.commands.wiki as wiki_command

        manifest = RepoWikiPageManifest(entries=())
        build_calls: list[dict[str, object]] = []
        select_calls: list[dict[str, object]] = []

        def fake_build_manifest(repo_root, variant, **kwargs):
            build_calls.append(kwargs)
            return manifest

        def fake_select_manifest(received_manifest, **kwargs):
            select_calls.append(kwargs)
            return received_manifest

        monkeypatch.setattr(wiki_command, "build_repo_page_manifest", fake_build_manifest)
        monkeypatch.setattr(wiki_command, "select_repo_page_manifest", fake_select_manifest)

        pages_file = tmp_path / "pages.txt"
        pages_file.write_text("Module:Erenshor/Data/Links\n", encoding="utf-8")
        result = runner.invoke(
            app,
            [
                "wiki",
                "deploy-repo-pages",
                "--include-generated-data",
                "--include-content-pages",
                "--pages-file",
                str(pages_file),
                "--manifest-output",
                str(tmp_path / "manifest.json"),
            ],
        )

        assert result.exit_code == 0
        assert build_calls == [
            {
                "include_templates": False,
                "include_generated_data": True,
                "include_content_pages": True,
                "requested_titles": {"Module:Erenshor/Data/Links"},
            }
        ]
        assert select_calls == [
            {
                "requested_titles": {"Module:Erenshor/Data/Links"},
                "include_templates": False,
                "include_generated_data": True,
                "include_content_pages": True,
                "known_live_titles": set(),
            }
        ]
        assert "no remote edits" in result.output

    def test_deploy_repo_pages_requires_pages_file_for_generated_data_before_network(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Unfiltered generated-data opt-in fails before discovery, login, or deployment, including dry-run."""
        import erenshor.cli.commands.wiki as wiki_command

        build_manifest = MagicMock(side_effect=AssertionError("manifest discovery must not run"))
        readonly_client = MagicMock(side_effect=AssertionError("live checks must not run"))
        authenticated_client = MagicMock(side_effect=AssertionError("login must not run"))
        deploy = MagicMock(side_effect=AssertionError("deployment must not run"))
        monkeypatch.setattr(wiki_command, "build_repo_page_manifest", build_manifest)
        monkeypatch.setattr(wiki_command, "_create_readonly_mediawiki_client", readonly_client)
        monkeypatch.setattr(wiki_command, "_create_mediawiki_client", authenticated_client)
        monkeypatch.setattr(wiki_command, "deploy_repo_pages", deploy)

        result = runner.invoke(app, ["--dry-run", "wiki", "deploy-repo-pages", "--include-generated-data"])

        assert result.exit_code == 1
        assert "--include-generated-data requires --pages-file" in result.output
        build_manifest.assert_not_called()
        readonly_client.assert_not_called()
        authenticated_client.assert_not_called()
        deploy.assert_not_called()

    @pytest.mark.parametrize(
        ("title", "stage", "include_option", "error_text"),
        [
            (
                "Template:Item",
                "template",
                "--include-templates",
                "Template pages require --include-templates: Template:Item",
            ),
            (
                "Module:Erenshor/Data/Links",
                "generated_data",
                "--include-generated-data",
                "Generated data pages require explicit deployment opt-in",
            ),
            (
                "Category:Links",
                "content_page",
                "--include-content-pages",
                "Content pages require explicit deployment opt-in: Category:Links",
            ),
        ],
    )
    def test_deploy_repo_pages_discovers_requested_optional_titles(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        title: str,
        stage: str,
        include_option: str,
        error_text: str,
    ):
        """Explicit optional pages fail without their scope flag instead of becoming no-ops."""
        import erenshor.cli.commands.wiki as wiki_command

        manifest = RepoWikiPageManifest(
            entries=(
                RepoWikiPageManifestEntry(
                    title=title,
                    source_path=f"wiki/{title.replace(':', '/')}.wiki",
                    source_sha256="a" * 64,
                    ownership_class=stage,
                    upload_stage=stage,
                    content_model="wikitext",
                    declares_cargo_table=False,
                    cargo_tables=(),
                ),
            )
        )
        build_calls: list[dict[str, object]] = []

        def fake_build_manifest(repo_root, variant, **kwargs):
            build_calls.append(kwargs)
            return manifest

        monkeypatch.setattr(wiki_command, "build_repo_page_manifest", fake_build_manifest)

        pages_file = tmp_path / "pages.txt"
        pages_file.write_text(f"{title}\n", encoding="utf-8")
        rejected = runner.invoke(app, ["wiki", "deploy-repo-pages", "--pages-file", str(pages_file)])

        assert rejected.exit_code == 1
        assert " ".join(error_text.split()) in " ".join(rejected.output.split())
        assert build_calls[0]["requested_titles"] == {title}

        accepted = runner.invoke(
            app,
            [
                "--dry-run",
                "wiki",
                "deploy-repo-pages",
                "--pages-file",
                str(pages_file),
                include_option,
            ],
        )
        assert accepted.exit_code == 0
        assert "Dry run: 1 repo-owned pages" in accepted.output
        assert build_calls[1]["requested_titles"] == {title}

    def test_deploy_repo_pages_rejects_unsafe_resolver_before_mutation(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        """Test a resolver cannot deploy when the Links catalog is neither selected nor live."""
        import erenshor.cli.commands.wiki as wiki_command

        manifest = RepoWikiPageManifest(
            entries=(
                RepoWikiPageManifestEntry(
                    title="Module:Erenshor/Link",
                    source_path="wiki/modules/Erenshor/Link.lua",
                    source_sha256="a" * 64,
                    ownership_class="lua_module",
                    upload_stage="lua_module",
                    content_model="Scribunto",
                    declares_cargo_table=False,
                    cargo_tables=(),
                ),
            )
        )
        readonly = MagicMock()
        readonly.page_exists.return_value = False
        monkeypatch.setattr(wiki_command, "build_repo_page_manifest", lambda *_args, **_kwargs: manifest)
        monkeypatch.setattr(wiki_command, "_create_readonly_mediawiki_client", lambda _ctx: readonly)
        deploy = MagicMock(side_effect=AssertionError("unsafe manifest reached deployment"))
        monkeypatch.setattr(wiki_command, "deploy_repo_pages", deploy)

        pages_file = tmp_path / "pages.txt"
        pages_file.write_text("Module:Erenshor/Link\n", encoding="utf-8")
        result = runner.invoke(app, ["wiki", "deploy-repo-pages", "--pages-file", str(pages_file)])

        assert result.exit_code == 1
        assert "Module:Erenshor/Link requires" in result.output
        assert "Module:Erenshor/Data/Links" in result.output
        readonly.page_exists.assert_called_once_with("Module:Erenshor/Data/Links")
        readonly.close.assert_called_once_with()
        deploy.assert_not_called()

    def test_deploy_repo_pages_accepts_live_catalog_and_dry_run_does_not_login_or_edit(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Test a live read-only catalog permits resolver selection without dry-run mutation."""
        import erenshor.cli.commands.wiki as wiki_command

        manifest = RepoWikiPageManifest(
            entries=(
                RepoWikiPageManifestEntry(
                    title="Module:Erenshor/Link",
                    source_path="wiki/modules/Erenshor/Link.lua",
                    source_sha256="a" * 64,
                    ownership_class="lua_module",
                    upload_stage="lua_module",
                    content_model="Scribunto",
                    declares_cargo_table=False,
                    cargo_tables=(),
                ),
            )
        )
        readonly = MagicMock()
        readonly.page_exists.return_value = True
        authenticated = MagicMock()
        monkeypatch.setattr(wiki_command, "build_repo_page_manifest", lambda *_args, **_kwargs: manifest)
        monkeypatch.setattr(wiki_command, "_create_readonly_mediawiki_client", lambda _ctx: readonly)
        create_client = MagicMock(return_value=authenticated)
        monkeypatch.setattr(wiki_command, "_create_mediawiki_client", create_client)
        deploy = MagicMock(return_value=RepoPageDeployResult(entries=()))
        monkeypatch.setattr(wiki_command, "deploy_repo_pages", deploy)
        monkeypatch.setattr(wiki_command, "write_repo_page_manifest", MagicMock())

        result = runner.invoke(app, ["--dry-run", "wiki", "deploy-repo-pages"])

        assert result.exit_code == 0
        assert "Dry run" in result.output
        readonly.page_exists.assert_called_once_with("Module:Erenshor/Data/Links")
        readonly.close.assert_called_once_with()
        create_client.assert_not_called()
        deploy.assert_not_called()

        result = runner.invoke(app, ["wiki", "deploy-repo-pages"])

        assert result.exit_code == 0
        create_client.assert_called_once()
        deploy.assert_called_once()
        assert deploy.call_args.kwargs["known_live_titles"] == {"Module:Erenshor/Data/Links"}
        assert deploy.call_args.kwargs["include_generated_data"] is False
        assert deploy.call_args.kwargs["include_content_pages"] is False
        authenticated.close.assert_called_once_with()

    def test_deploy_repo_pages_gates_item_on_live_catalog_and_selects_it(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        """Test filtered Item deployment checks the live Links catalog before selection."""
        import erenshor.cli.commands.wiki as wiki_command

        manifest = RepoWikiPageManifest(
            entries=(
                RepoWikiPageManifestEntry(
                    title="Module:Erenshor/Item",
                    source_path="wiki/modules/Erenshor/Item.lua",
                    source_sha256="a" * 64,
                    ownership_class="lua_module",
                    upload_stage="lua_module",
                    content_model="Scribunto",
                    declares_cargo_table=False,
                    cargo_tables=(),
                ),
            )
        )
        readonly = MagicMock()
        readonly.page_exists.return_value = False
        authenticated = MagicMock()
        monkeypatch.setattr(wiki_command, "build_repo_page_manifest", lambda *_args, **_kwargs: manifest)
        monkeypatch.setattr(wiki_command, "_create_readonly_mediawiki_client", lambda _ctx: readonly)
        create_client = MagicMock(return_value=authenticated)
        monkeypatch.setattr(wiki_command, "_create_mediawiki_client", create_client)
        deploy = MagicMock(return_value=RepoPageDeployResult(entries=()))
        monkeypatch.setattr(wiki_command, "deploy_repo_pages", deploy)
        monkeypatch.setattr(wiki_command, "write_repo_page_manifest", MagicMock())

        pages_file = tmp_path / "pages.txt"
        pages_file.write_text("Module:Erenshor/Item\n", encoding="utf-8")
        rejected = runner.invoke(app, ["wiki", "deploy-repo-pages", "--pages-file", str(pages_file)])

        assert rejected.exit_code == 1
        assert "Module:Erenshor/Item requires" in rejected.output
        assert "Module:Erenshor/Data/Links" in rejected.output
        readonly.page_exists.assert_called_once_with("Module:Erenshor/Data/Links")
        readonly.close.assert_called_once_with()
        deploy.assert_not_called()

        readonly.reset_mock()
        readonly.page_exists.return_value = True
        accepted = runner.invoke(app, ["--dry-run", "wiki", "deploy-repo-pages", "--pages-file", str(pages_file)])

        assert accepted.exit_code == 0
        assert "Dry run: 1 repo-owned pages" in accepted.output
        readonly.page_exists.assert_called_once_with("Module:Erenshor/Data/Links")
        readonly.close.assert_called_once_with()
        create_client.assert_not_called()
        deploy.assert_not_called()

        result = runner.invoke(app, ["wiki", "deploy-repo-pages", "--pages-file", str(pages_file)])

        assert result.exit_code == 0
        create_client.assert_called_once()
        deploy.assert_called_once()
        assert [entry.title for entry in deploy.call_args.kwargs["manifest"].entries] == ["Module:Erenshor/Item"]
        assert deploy.call_args.kwargs["known_live_titles"] == {"Module:Erenshor/Data/Links"}
        authenticated.close.assert_called_once_with()

    @patch("erenshor.cli.commands.wiki._create_wiki_service")
    def test_legacy_deploy_requires_explicit_legacy_flag(self, mock_create_service):
        """Test legacy generated article deploy is guarded during Lua cutover."""
        result = runner.invoke(app, ["wiki", "deploy"])

        assert result.exit_code == 1
        assert "--legacy-article-deploy" in result.output
        mock_create_service.assert_not_called()

    def test_deploy_reports_changed_cargo_declarations(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        """Test a changed Cargo declaration is reported with a pointer to Special:CargoTables."""
        import erenshor.cli.commands.wiki as wiki_command

        manifest = RepoWikiPageManifest(
            entries=(
                RepoWikiPageManifestEntry(
                    title="Template:Item",
                    source_path="wiki/templates/Item.wiki",
                    source_sha256="abc",
                    ownership_class="cargo_declaration",
                    upload_stage="cargo_declaration",
                    content_model="wikitext",
                    declares_cargo_table=True,
                    cargo_tables=("Items",),
                ),
            )
        )

        def fake_deploy_repo_pages(**kwargs):
            return RepoPageDeployResult(
                entries=(
                    RepoPageDeployResultEntry(
                        title="Template:Item",
                        status="edited",
                        old_revision_id=1,
                        old_revision_timestamp="2026-06-04T12:00:00Z",
                        new_revision_id=2,
                    ),
                )
            )

        monkeypatch.setattr(wiki_command, "build_repo_page_manifest", lambda repo_root, variant, **kwargs: manifest)
        monkeypatch.setattr(wiki_command, "_create_mediawiki_client", lambda cli_ctx: FakeDeployClient())
        monkeypatch.setattr(wiki_command, "deploy_repo_pages", fake_deploy_repo_pages)
        monkeypatch.setattr(wiki_command, "write_repo_page_manifest", lambda deployed_manifest, path: None)

        result = runner.invoke(
            app,
            [
                "wiki",
                "deploy-repo-pages",
                "--include-templates",
                "--manifest-output",
                str(tmp_path / "m.json"),
            ],
        )

        assert result.exit_code == 0
        assert "Cargo" in result.output
        assert "Items" in result.output
        assert "Special:CargoTables" in result.output


class TestWikiReviewOverridesCommand:
    """Test review-only article override minimization command."""

    def test_review_overrides_fetches_pages_and_prints_review_report(self, monkeypatch: pytest.MonkeyPatch):
        """Test review command delegates live review and reports removals, preserved fields, and diffs."""
        import erenshor.cli.commands.wiki as wiki_command

        client = FakeDeployClient()
        calls = []
        migration = ArticleMigration(
            title="Ember Longsword",
            minimized_wikitext="{{Item|stablekey=item:ember|source=Custom drop}}",
            classification=ArticleOverrideClassification(
                title="Ember Longsword",
                decisions=(
                    OverrideFieldDecision(
                        field="type",
                        article_value="Weapon",
                        generated_value="Weapon",
                        decision="removed_generated_duplicate",
                        reason="value matches generated data",
                    ),
                    OverrideFieldDecision(
                        field="source",
                        article_value="Custom drop",
                        generated_value="Quest",
                        decision="preserved_manual_override",
                        reason="value diverges from generated data",
                    ),
                    OverrideFieldDecision(
                        field="imagecaption",
                        article_value="-",
                        generated_value="A sword",
                        decision="intentional_blank",
                        reason="documented blank sentinel",
                    ),
                ),
            ),
            removed_fields=("type",),
            preserved_fields=("source", "imagecaption"),
        )
        review = ArticleOverrideReview(
            title="Ember Longsword",
            original_wikitext="{{Item|stablekey=item:ember|type=Weapon|source=Custom drop|imagecaption=-}}",
            migration=migration,
        )

        def fake_create_client(cli_ctx):
            calls.append(("create_client", cli_ctx.variant))
            return client

        def fake_review_article_overrides(**kwargs):
            calls.append(("review", kwargs))
            return (review,)

        monkeypatch.setattr(wiki_command, "_create_mediawiki_client", fake_create_client)
        monkeypatch.setattr(wiki_command, "review_article_overrides", fake_review_article_overrides)
        monkeypatch.setattr(
            wiki_command, "_build_item_article_identities", lambda cli_ctx: {"Ember Longsword": ("item:ember",)}
        )

        result = runner.invoke(
            app,
            [
                "wiki",
                "review-overrides",
                "--page",
                "Ember Longsword",
                "--template",
                "Item",
                "--module",
                "Erenshor/Item",
            ],
        )

        assert result.exit_code == 0
        assert "Ember Longsword" in result.output
        assert "Removed generated duplicates: type" in result.output
        assert "Preserved manual overrides: source" in result.output
        assert "Intentional blanks: imagecaption" in result.output
        assert "-{{Item|stablekey=item:ember|type=Weapon|source=Custom drop|imagecaption=-}}" in result.output
        assert "+{{Item|stablekey=item:ember|source=Custom drop}}" in result.output
        assert client.closed is True
        _, kwargs = calls[1]
        assert kwargs["client"] is client
        assert kwargs["titles"] == ("Ember Longsword",)
        assert kwargs["template_names"] == ("Item",)
        assert kwargs["module"] == "Erenshor/Item"
        assert kwargs["article_identities"] == {"Ember Longsword": ("item:ember",)}
        assert calls[0] == ("create_client", "main")
        assert calls[1][0] == "review"

    def test_review_overrides_reports_skipped_pages(self, monkeypatch: pytest.MonkeyPatch):
        """Test ambiguous identity pages are reported instead of minimized."""
        import erenshor.cli.commands.wiki as wiki_command

        client = FakeDeployClient()
        skipped = ArticleOverrideReview(
            title="A Lost Poem",
            original_wikitext="{{Item|title=A Lost Poem (1)}}",
            migration=None,
            skipped_reason="ambiguous identity: 2 stable keys mapped to page",
        )

        monkeypatch.setattr(wiki_command, "_create_mediawiki_client", lambda cli_ctx: client)
        monkeypatch.setattr(
            wiki_command, "_build_item_article_identities", lambda cli_ctx: {"A Lost Poem": ("item:1", "item:2")}
        )
        monkeypatch.setattr(wiki_command, "review_article_overrides", lambda **kwargs: (skipped,))

        result = runner.invoke(app, ["wiki", "review-overrides", "--page", "A Lost Poem"])

        assert result.exit_code == 0
        assert "Skipped: 1" in result.output
        assert "A Lost Poem" in result.output
        assert "Skipped: ambiguous identity: 2 stable keys mapped to page" in result.output
        assert client.closed is True

    def test_review_overrides_defaults_to_identity_map_titles_with_limit(self, monkeypatch: pytest.MonkeyPatch):
        """Test review command can audit repo-mapped item pages without a manual page list."""
        import erenshor.cli.commands.wiki as wiki_command

        client = FakeDeployClient()
        calls = []
        identities = {
            "B Item": ("item:b",),
            "A Item": ("item:a",),
            "C Item": ("item:c",),
        }

        def fake_review_article_overrides(**kwargs):
            calls.append(kwargs)
            return ()

        monkeypatch.setattr(wiki_command, "_create_mediawiki_client", lambda cli_ctx: client)
        monkeypatch.setattr(wiki_command, "_build_item_article_identities", lambda cli_ctx: identities)
        monkeypatch.setattr(wiki_command, "review_article_overrides", fake_review_article_overrides)

        result = runner.invoke(app, ["wiki", "review-overrides", "--limit", "2"])

        assert result.exit_code == 0
        [kwargs] = calls
        assert kwargs["titles"] == ("A Item", "B Item")
        assert kwargs["article_identities"] is identities
        assert client.closed is True


class FakeDeployClient:
    def __init__(self) -> None:
        self.closed = False
        self.purges: list[tuple[tuple[str, ...], bool, str | None, str | None]] = []

    def purge_pages(
        self,
        titles,
        force_link_update=True,
        assertion=None,
        assert_user=None,
    ):
        self.purges.append((tuple(titles), force_link_update, assertion, assert_user))
        return tuple(titles)

    def close(self) -> None:
        self.closed = True


class TestWikiRefreshEmbeddedCommand:
    """Test dependency-derived refresh command."""

    def test_refresh_embedded_uses_dependencies_and_namespace_filters(self, monkeypatch: pytest.MonkeyPatch):
        """Test refresh command delegates dependency discovery with explicit namespaces."""
        import erenshor.cli.commands.wiki as wiki_command

        client = FakeDeployClient()
        calls = []

        def fake_create_client(cli_ctx):
            calls.append(("create_client", cli_ctx.variant))
            return client

        def fake_refresh_embedded_pages(**kwargs):
            calls.append(("refresh", kwargs))
            return EmbeddedRefreshResult(
                requested=("Ember Longsword",),
                refreshed=("Ember Longsword",),
            )

        monkeypatch.setattr(wiki_command, "_create_mediawiki_client", fake_create_client)
        monkeypatch.setattr(wiki_command, "refresh_embedded_pages", fake_refresh_embedded_pages)

        result = runner.invoke(
            app,
            [
                "wiki",
                "refresh-embedded",
                "--dependency-title",
                "Template:Item",
                "--dependency-title",
                "Module:Erenshor/Item",
                "--namespace",
                "0",
                "--namespace",
                "10",
                "--assert-user",
                "ErenshorBot",
            ],
        )

        assert result.exit_code == 0
        assert "Refreshed: 1" in result.output
        assert client.closed is True
        _, kwargs = calls[1]
        assert kwargs["client"] is client
        assert kwargs["dependency_titles"] == ("Template:Item", "Module:Erenshor/Item")
        assert kwargs["namespaces"] == (0, 10)
        assert kwargs["assertion"] == "bot"
        assert kwargs["assert_user"] == "ErenshorBot"

    def test_refresh_embedded_purges_only_explicit_pages(self, monkeypatch: pytest.MonkeyPatch):
        """Explicit page mode bypasses broad transclusion discovery."""
        import erenshor.cli.commands.wiki as wiki_command

        client = FakeDeployClient()
        monkeypatch.setattr(wiki_command, "_create_mediawiki_client", lambda cli_ctx: client)
        discover = MagicMock()
        monkeypatch.setattr(wiki_command, "refresh_embedded_pages", discover)

        result = runner.invoke(
            app,
            [
                "wiki",
                "refresh-embedded",
                "--page",
                "Chazza Priel",
                "--page",
                "Tiallia Priel",
                "--page",
                "Chazza Priel",
                "--assert-user",
                "ErenshorBot",
            ],
        )

        assert result.exit_code == 0
        assert "Refreshed: 2" in result.output
        assert client.purges == [(("Chazza Priel", "Tiallia Priel"), True, "bot", "ErenshorBot")]
        discover.assert_not_called()
        assert client.closed is True

    def test_refresh_embedded_deduplicates_combined_refresh_results(self, monkeypatch: pytest.MonkeyPatch):
        """Dependency and source refreshes share one final refreshed-page count."""
        import erenshor.cli.commands.wiki as wiki_command

        client = FakeDeployClient()
        calls = []

        monkeypatch.setattr(wiki_command, "_create_mediawiki_client", lambda cli_ctx: client)

        def fake_refresh_embedded_pages(**kwargs):
            calls.append(("embedded", kwargs))
            return EmbeddedRefreshResult(requested=("A", "B"), refreshed=("A", "B"))

        def fake_refresh_item_owners_for_source_changes(**kwargs):
            calls.append(("owners", kwargs))
            return EmbeddedRefreshResult(requested=("B", "C"), refreshed=("B", "C"))

        monkeypatch.setattr(wiki_command, "refresh_embedded_pages", fake_refresh_embedded_pages)
        monkeypatch.setattr(
            wiki_command,
            "refresh_item_owners_for_source_changes",
            fake_refresh_item_owners_for_source_changes,
        )

        result = runner.invoke(
            app,
            [
                "wiki",
                "refresh-embedded",
                "--dependency-title",
                "Template:Item",
                "--namespace",
                "0",
                "--source-table",
                "loot_drops",
            ],
        )

        assert result.exit_code == 0
        assert "Refreshed: 3" in result.output
        assert [kind for kind, _ in calls] == ["embedded", "owners"]
        assert client.closed is True

    def test_refresh_embedded_reparses_item_owners_for_source_table(self, monkeypatch: pytest.MonkeyPatch):
        """Source-table mode refreshes item-owned Cargo pages without embeddedin namespaces."""
        import erenshor.cli.commands.wiki as wiki_command

        client = FakeDeployClient()
        calls = []

        monkeypatch.setattr(wiki_command, "_create_mediawiki_client", lambda cli_ctx: client)

        def fake_refresh_item_owners_for_source_changes(**kwargs):
            calls.append(kwargs)
            return EmbeddedRefreshResult(requested=("Ember Longsword",), refreshed=("Ember Longsword",))

        monkeypatch.setattr(
            wiki_command,
            "refresh_item_owners_for_source_changes",
            fake_refresh_item_owners_for_source_changes,
        )

        result = runner.invoke(
            app,
            ["wiki", "refresh-embedded", "--source-table", "loot_drops"],
        )

        assert result.exit_code == 0
        assert "Refreshed: 1" in result.output
        assert calls[0]["changed_source_tables"] == ("loot_drops",)
        assert calls[0]["assertion"] == "bot"
        assert client.closed is True


class TestWikiInterfaceDeployCommands:
    """Test the dedicated interface-admin deploy and rollback commands."""

    def test_deploy_dry_run_checks_rights_without_mutating(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        import erenshor.cli.commands.wiki as wiki_command
        from erenshor.application.wiki_interface.deploy import (
            InterfaceDeployPlan,
            InterfaceDeployPlanEntry,
        )

        client = MagicMock()
        client.get_current_user_rights.return_value = frozenset({"editinterface"})
        plan = InterfaceDeployPlan(
            entries=(
                InterfaceDeployPlanEntry(
                    title="MediaWiki:Gadget-a.js",
                    source_path="wiki/gadgets/a.js",
                    source_sha256="a" * 64,
                    content_model="javascript",
                    planned_action="created",
                    new_text="window.a = true;\n",
                    snapshot=MagicMock(),
                ),
            ),
        )
        monkeypatch.setattr(wiki_command, "_interface_assert_user", lambda _ctx: "InterfaceAdmin")
        monkeypatch.setattr(wiki_command, "_create_interface_mediawiki_client", lambda _ctx: client)
        artifact_root = tmp_path / "artifacts"
        monkeypatch.setattr(wiki_command, "_interface_artifact_root", lambda _ctx: artifact_root)
        monkeypatch.setattr(
            wiki_command,
            "_resolve_interface_manifest_path",
            lambda _ctx, _path: artifact_root / "manifest.json",
        )
        monkeypatch.setattr(wiki_command, "plan_interface_pages", lambda *_args, **_kwargs: plan)
        deploy = MagicMock()
        monkeypatch.setattr(wiki_command, "deploy_interface_pages", deploy)

        result = runner.invoke(app, ["--dry-run", "wiki", "deploy-interface"])

        assert result.exit_code == 0
        assert "created: 1" in result.output
        client.get_current_user_rights.assert_called_once_with(assertion="user", assert_user="InterfaceAdmin")
        deploy.assert_not_called()
        assert not artifact_root.exists()
        client.close.assert_called_once_with()

    def test_deploy_persists_service_checkpoints(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        import erenshor.cli.commands.wiki as wiki_command
        from erenshor.application.wiki_interface.deploy import (
            InterfaceDeployPlan,
            InterfaceDeployResult,
        )
        from erenshor.application.wiki_interface.manifest import (
            InterfaceDeployManifest,
            InterfacePageManifestEntry,
        )

        client = MagicMock()
        plan = InterfaceDeployPlan(entries=())
        manifest = InterfaceDeployManifest(
            entries=(
                InterfacePageManifestEntry(
                    title="MediaWiki:Gadget-a.js",
                    source_path="wiki/gadgets/a.js",
                    source_sha256="a" * 64,
                    content_model="javascript",
                    new_revision_id=2,
                    deploy_action="created",
                    mutation_state="applied",
                    deployed_text_sha256="c" * 64,
                ),
                InterfacePageManifestEntry(
                    title="MediaWiki:Gadgets-definition",
                    source_path="wiki/gadgets/gadgets.toml",
                    source_sha256="b" * 64,
                    content_model="wikitext",
                    deploy_action="unchanged",
                    mutation_state="applied",
                ),
            ),
            rollback_root="output/wiki-interface/rollback/deploy-test",
        )
        writes: list[tuple[InterfaceDeployManifest, Path]] = []

        def fake_deploy(
            received_plan,
            *,
            repo_root,
            client,
            summary,
            rollback_root,
            checkpoint,
        ):
            assert received_plan is plan
            assert rollback_root == tmp_path / "rollback"
            checkpoint(manifest)
            return InterfaceDeployResult(manifest=manifest)

        monkeypatch.setattr(wiki_command, "_create_interface_mediawiki_client", lambda _ctx: client)
        monkeypatch.setattr(wiki_command, "_new_interface_rollback_root", lambda _ctx: tmp_path / "rollback")
        monkeypatch.setattr(wiki_command, "plan_interface_pages", lambda *_args, **_kwargs: plan)
        monkeypatch.setattr(wiki_command, "deploy_interface_pages", fake_deploy)
        monkeypatch.setattr(
            wiki_command,
            "write_interface_deploy_manifest",
            lambda saved, path: writes.append((saved, path)),
        )

        result = runner.invoke(app, ["wiki", "deploy-interface"])

        assert result.exit_code == 0
        assert "created: 1" in result.output
        assert "unchanged: 1" in result.output
        assert len(writes) == 2
        assert writes[0] == writes[1]
        client.close.assert_called_once_with()

    def test_interface_client_never_falls_back_to_bot_credentials(self) -> None:
        from types import SimpleNamespace

        import erenshor.cli.commands.wiki as wiki_command

        mediawiki = SimpleNamespace(
            api_url="https://example.test/api.php",
            bot_username="ContentBot",
            bot_password="bot-secret",
            interface_username="",
            interface_password="",
        )
        cli_ctx = SimpleNamespace(config=SimpleNamespace(global_=SimpleNamespace(mediawiki=mediawiki)))

        with (
            patch.object(wiki_command, "MediaWikiClient") as client_class,
            pytest.raises(ValueError, match="never used as a fallback"),
        ):
            wiki_command._create_interface_mediawiki_client(cli_ctx)

        client_class.assert_not_called()

    @pytest.mark.parametrize(
        ("login_name", "assert_user"),
        [
            ("InterfaceAdmin", "InterfaceAdmin"),
            ("InterfaceAdmin@InterfaceDeploy", "InterfaceAdmin"),
        ],
    )
    def test_interface_assert_user_uses_bot_password_owner(
        self,
        login_name: str,
        assert_user: str,
    ) -> None:
        from types import SimpleNamespace

        import erenshor.cli.commands.wiki as wiki_command

        cli_ctx = SimpleNamespace(
            config=SimpleNamespace(global_=SimpleNamespace(mediawiki=SimpleNamespace(interface_username=login_name)))
        )

        assert wiki_command._interface_assert_user(cli_ctx) == assert_user

    def test_manifest_path_must_stay_inside_repo(self, tmp_path: Path) -> None:
        from types import SimpleNamespace

        import erenshor.cli.commands.wiki as wiki_command

        cli_ctx = SimpleNamespace(repo_root=tmp_path / "repo")
        cli_ctx.repo_root.mkdir()

        with pytest.raises(ValueError, match="inside the repository root"):
            wiki_command._resolve_interface_manifest_path(cli_ctx, tmp_path / "outside.json")

    def test_manifest_path_rejects_source_spec_and_rollback_aliases(self, tmp_path: Path) -> None:
        from types import SimpleNamespace

        import erenshor.cli.commands.wiki as wiki_command

        repo = tmp_path / "repo"
        source = repo / "wiki" / "gadgets" / "a.js"
        spec = repo / "wiki" / "gadgets" / "gadgets.toml"
        source.parent.mkdir(parents=True)
        source.write_text("window.a = true;\n", encoding="utf-8")
        spec.write_text("[gadgets]\n", encoding="utf-8")
        artifact_root = repo / "output" / "wiki-interface"
        artifact_root.mkdir(parents=True)
        rollback = artifact_root / "rollback"
        rollback.mkdir()
        sidecar = rollback / "old.wiki"
        sidecar.write_text("old\n", encoding="utf-8")

        source_alias = artifact_root / "source-alias"
        source_alias.hardlink_to(source)
        spec_alias = artifact_root / "spec-alias"
        spec_alias.hardlink_to(spec)
        sidecar_alias = artifact_root / "sidecar-alias"
        sidecar_alias.hardlink_to(sidecar)
        cli_ctx = SimpleNamespace(repo_root=repo)
        plan = SimpleNamespace(entries=(SimpleNamespace(source_path="wiki/gadgets/a.js"),))

        for alias in (source_alias, spec_alias, sidecar_alias):
            manifest = wiki_command._resolve_interface_manifest_path(cli_ctx, alias)
            with pytest.raises(ValueError, match="alias"):
                wiki_command._validate_interface_manifest_output(cli_ctx, manifest, plan)

        rollback_manifest = wiki_command._resolve_interface_manifest_path(cli_ctx, rollback / "manifest.json")
        with pytest.raises(ValueError, match="rollback"):
            wiki_command._validate_interface_manifest_output(cli_ctx, rollback_manifest, plan)

    def test_real_deploys_reserve_unique_rollback_roots(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        from types import SimpleNamespace

        import erenshor.cli.commands.wiki as wiki_command

        artifact_root = tmp_path / "artifacts"
        monkeypatch.setattr(wiki_command, "_interface_artifact_root", lambda _ctx: artifact_root)
        manifest_path = artifact_root / "deploy-manifest.json"
        monkeypatch.setattr(wiki_command, "_resolve_interface_manifest_path", lambda _ctx, _path: manifest_path)
        client = MagicMock()
        client.get_current_user_rights.return_value = frozenset({"editinterface"})
        plan = SimpleNamespace(entries=())
        roots: list[Path] = []

        def fake_deploy(*_args, rollback_root: Path, **_kwargs):
            roots.append(rollback_root)
            return SimpleNamespace(manifest=SimpleNamespace(entries=()))

        monkeypatch.setattr(wiki_command, "_create_interface_mediawiki_client", lambda _ctx: client)
        monkeypatch.setattr(wiki_command, "plan_interface_pages", lambda *_args, **_kwargs: plan)
        monkeypatch.setattr(wiki_command, "deploy_interface_pages", fake_deploy)
        monkeypatch.setattr(wiki_command, "write_interface_deploy_manifest", lambda *_args: None)

        first = runner.invoke(app, ["wiki", "deploy-interface"])
        second = runner.invoke(app, ["wiki", "deploy-interface"])

        assert first.exit_code == 0
        assert second.exit_code == 0
        assert len(roots) == 2
        assert roots[0] != roots[1]
        assert roots[0].is_dir() and roots[1].is_dir()
        assert roots[0].parent == roots[1].parent == artifact_root / "rollback"

    def test_interrupted_deploy_keeps_prior_rollback_root_isolated(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        from types import SimpleNamespace

        import erenshor.cli.commands.wiki as wiki_command

        artifact_root = tmp_path / "artifacts"
        monkeypatch.setattr(wiki_command, "_interface_artifact_root", lambda _ctx: artifact_root)
        manifest_path = artifact_root / "deploy-manifest.json"
        monkeypatch.setattr(wiki_command, "_resolve_interface_manifest_path", lambda _ctx, _path: manifest_path)
        client = MagicMock()
        client.get_current_user_rights.return_value = frozenset({"editinterface"})
        plan = SimpleNamespace(entries=())
        roots: list[Path] = []
        calls = 0

        def fake_deploy(*_args, rollback_root: Path, **_kwargs):
            nonlocal calls
            calls += 1
            roots.append(rollback_root)
            if calls == 1:
                (rollback_root / "journal.wiki").write_text("first\n", encoding="utf-8")
                raise RuntimeError("interrupted")
            return SimpleNamespace(manifest=SimpleNamespace(entries=()))

        monkeypatch.setattr(wiki_command, "_create_interface_mediawiki_client", lambda _ctx: client)
        monkeypatch.setattr(wiki_command, "plan_interface_pages", lambda *_args, **_kwargs: plan)
        monkeypatch.setattr(wiki_command, "deploy_interface_pages", fake_deploy)
        monkeypatch.setattr(wiki_command, "write_interface_deploy_manifest", lambda *_args: None)

        interrupted = runner.invoke(app, ["wiki", "deploy-interface"])
        completed = runner.invoke(app, ["wiki", "deploy-interface"])

        assert interrupted.exit_code == 1
        assert completed.exit_code == 0
        assert roots[0] != roots[1]
        assert (roots[0] / "journal.wiki").read_text(encoding="utf-8") == "first\n"

    def test_rollback_dry_run_counts_only_deployed_edits(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        from types import SimpleNamespace

        import erenshor.cli.commands.wiki as wiki_command

        manifest_path = tmp_path / "deploy-manifest.json"
        manifest_path.write_text("placeholder", encoding="utf-8")
        monkeypatch.setattr(wiki_command, "_resolve_interface_manifest_path", lambda _ctx, _path: manifest_path)
        manifest = SimpleNamespace(
            entries=(
                SimpleNamespace(deploy_action="edited", new_revision_id=12, rollback_text_source="r/edited.wiki"),
                SimpleNamespace(deploy_action=None, new_revision_id=None, rollback_text_source="r/pending.wiki"),
                SimpleNamespace(deploy_action="created", new_revision_id=14, rollback_text_source=None),
            )
        )
        monkeypatch.setattr(wiki_command, "read_interface_deploy_manifest", lambda _path: manifest)
        client = MagicMock()
        client.get_current_user_rights.return_value = frozenset({"editinterface"})
        monkeypatch.setattr(wiki_command, "_create_interface_mediawiki_client", lambda _ctx: client)

        result = runner.invoke(app, ["--dry-run", "wiki", "rollback-interface", "--manifest", str(manifest_path)])

        assert result.exit_code == 0
        assert "would restore 1 interface pages" in result.output
        assert "created pages left in place: 1" in result.output
        client.close.assert_called_once_with()


class TestWikiRollbackRepoCommand:
    """Test manifest-backed rollback command."""

    def test_rollback_reads_manifest_and_restores_recorded_text(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        """Test rollback loads the persisted manifest and delegates restoration to the service."""
        import erenshor.cli.commands.wiki as wiki_command
        from erenshor.application.wiki_deploy.manifest import write_repo_page_manifest

        manifest = RepoWikiPageManifest(
            entries=(
                RepoWikiPageManifestEntry(
                    title="Module:Erenshor/Item",
                    source_path="variants/main/wiki/lua/Erenshor/Item.lua",
                    source_sha256="0" * 64,
                    ownership_class="generated_data",
                    upload_stage="generated_data",
                    content_model="Scribunto",
                    declares_cargo_table=False,
                    cargo_tables=(),
                    old_revision_id=10,
                    old_revision_timestamp="2026-06-04T12:00:00Z",
                    new_revision_id=11,
                    rollback_text_source="rollback/Module_Erenshor_Item.wiki",
                ),
            )
        )
        manifest_path = tmp_path / "deploy-manifest.json"
        write_repo_page_manifest(manifest, manifest_path)

        client = FakeDeployClient()
        calls = []

        def fake_create_client(cli_ctx):
            calls.append(("create_client", cli_ctx.variant))
            return client

        def fake_rollback_repo_pages(**kwargs):
            calls.append(("rollback", kwargs))
            return RollbackResult(
                entries=(
                    RollbackResultEntry(
                        title="Module:Erenshor/Item",
                        restored_revision_id=10,
                        new_revision_id=12,
                    ),
                )
            )

        monkeypatch.setattr(wiki_command, "_create_mediawiki_client", fake_create_client)
        monkeypatch.setattr(wiki_command, "rollback_repo_pages", fake_rollback_repo_pages)

        result = runner.invoke(
            app,
            ["wiki", "rollback-repo-pages", "--manifest", str(manifest_path), "--assert-user", "ErenshorBot"],
        )

        assert result.exit_code == 0
        assert "Restored: 1" in result.output
        assert client.closed is True
        _, kwargs = calls[1]
        assert kwargs["client"] is client
        assert kwargs["assertion"] == "bot"
        assert kwargs["assert_user"] == "ErenshorBot"
        [entry] = kwargs["manifest"].entries
        assert entry.title == "Module:Erenshor/Item"
        assert entry.rollback_text_source == "rollback/Module_Erenshor_Item.wiki"
        assert entry.old_revision_id == 10
