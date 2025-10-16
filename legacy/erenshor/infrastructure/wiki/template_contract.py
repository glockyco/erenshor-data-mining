from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Set

# Context models
from erenshor.infrastructure.templates.contexts import (
    AbilityBookInfoboxContext,
    AbilityInfoboxContext,
    AuraInfoboxContext,
    EnemyInfoboxContext,
    ItemInfoboxContext,
)

__all__ = ["ContractResult", "check_contracts"]


@dataclass
class ContractResult:
    template: str
    context: str
    missing_in_template: List[str]
    extra_in_template: List[str]
    template_fields: List[str]
    context_fields: List[str]


def _context_fields(model_cls: Any) -> Set[str]:
    # pydantic v2 exposes .model_fields
    names = set(model_cls.model_fields.keys())
    # Exclude internal identity-only fields
    return {n for n in names if n not in {"block_id"}}


def _templatedata_fields(td_file: Path) -> Set[str]:
    data = json.loads(td_file.read_text(encoding="utf-8"))
    params = data.get("params") or {}
    return set(params.keys())


def _template_wikitext_fields(template_file: Path) -> Set[str]:
    """Fallback extraction: scan template wikitext for infobox field bindings.

    Looks for `source="..."` attributes inside <title>, <image>, <caption>, and <data> tags.
    """
    import re

    text = template_file.read_text(encoding="utf-8")
    fields: Set[str] = set()
    # <data source="field">, <title source="field"/>, <image source="field">
    for m in re.finditer(r'source\s*=\s*"([^"]+)"', text):
        fields.add(m.group(1).strip())
    return fields


def check_contracts(templates_cache_dir: Path) -> List[ContractResult]:
    """Compare our render contexts vs. live template params (templatedata only).

    If templatedata is missing for a template, the template is skipped.
    """
    td_dir = Path(templates_cache_dir) / "Templatedata"
    results: List[ContractResult] = []

    # Map contexts to template names
    checks = [
        (AbilityInfoboxContext, "Ability"),
        (EnemyInfoboxContext, "Enemy"),
        (ItemInfoboxContext, "Armor"),
        (ItemInfoboxContext, "Weapon"),
        (AbilityBookInfoboxContext, "Ability Books"),
        (AuraInfoboxContext, "Auras"),
        # Additional item templates in the wild
        (ItemInfoboxContext, "Consumable"),
        (ItemInfoboxContext, "Mold"),
        (ItemInfoboxContext, "Item"),
    ]
    for ctx_cls, tname in checks:
        td_file = td_dir / f"{tname}.json"
        if td_file.exists():
            t_fields = _templatedata_fields(td_file)
        else:
            # Fallback to wikitext scan if templatedata is absent
            tmpl_wiki = Path(templates_cache_dir) / "Template" / f"{tname}.txt"
            if not tmpl_wiki.exists():
                continue
            t_fields = _template_wikitext_fields(tmpl_wiki)
        c_fields = _context_fields(ctx_cls)
        missing = sorted(list(c_fields - t_fields))
        extra = sorted(list(t_fields - c_fields))
        results.append(
            ContractResult(
                template=f"Template:{tname}",
                context=f"{ctx_cls.__module__}.{ctx_cls.__name__}",
                missing_in_template=missing,
                extra_in_template=extra,
                template_fields=sorted(list(t_fields)),
                context_fields=sorted(list(c_fields)),
            )
        )
    return results
