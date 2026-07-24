from __future__ import annotations

import ast
from pathlib import Path


def test_domain_does_not_import_outer_erenshor_layers() -> None:
    domain_root = Path("src/erenshor/domain")
    violations: list[str] = []

    for source_path in sorted(domain_root.rglob("*.py")):
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        for node in ast.walk(tree):
            imported_modules: list[str] = []
            if isinstance(node, ast.ImportFrom) and node.module is not None:
                imported_modules.append(node.module)
            elif isinstance(node, ast.Import):
                imported_modules.extend(alias.name for alias in node.names)

            for module in imported_modules:
                if module.startswith("erenshor.") and not module.startswith("erenshor.domain"):
                    line_number = int(getattr(node, "lineno", 0))
                    violations.append(f"{source_path}:{line_number}: {module}")

    assert violations == []
