"""Wiki preflights preserve input causes before local or remote writes."""

from pathlib import Path
from types import SimpleNamespace

from erenshor.cli.preconditions.checks.inputs import option_path
from erenshor.cli.preconditions.checks.wiki import interface_admin_credentials, wiki_endpoint


def test_option_path_requires_supplied_file_and_accepts_stdin(tmp_path: Path) -> None:
    check = option_path("pages_file")
    path = tmp_path / "pages.txt"
    context = {"pages_file": str(path)}
    assert not check(context).passed
    assert str(path) in str(check(context))
    path.write_text("Item:Iron Sword\n")
    assert check(context).passed
    context["pages_file"] = "-"
    assert check(context).passed


def test_wiki_endpoint_and_admin_credentials_preserve_missing_inputs() -> None:
    wiki = SimpleNamespace(api_url="not-a-url", interface_username="", interface_password="")
    context = {"config": SimpleNamespace(global_=SimpleNamespace(mediawiki=wiki))}
    assert not wiki_endpoint(context).passed
    assert "not-a-url" in str(wiki_endpoint(context))
    wiki.api_url = "https://example.test/api.php"
    assert wiki_endpoint(context).passed
    assert not interface_admin_credentials(context).passed
    assert "interface-admin" in str(interface_admin_credentials(context))
    wiki.interface_username, wiki.interface_password = "admin", "secret"
    assert interface_admin_credentials(context).passed
