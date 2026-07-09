from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from .polling import poll_until

if TYPE_CHECKING:
    from .operations import ProbeRunContext


def cargo_string_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def row_fields(row: dict[str, Any]) -> dict[str, Any]:
    title = row.get("title")
    if isinstance(title, dict):
        return title
    return row


def query_replacement_probe_row(context: ProbeRunContext, table: str, key: str) -> dict[str, Any]:
    return context.query_cargo_table(
        tables=table,
        fields="_pageName=Page,ProbeKey,ProbeValue",
        where="ProbeKey=" + cargo_string_literal(key),
        limit=20,
    )


def replacement_row_matches(result: dict[str, Any], key: str) -> bool:
    if not result.get("ok"):
        return False
    rows = result.get("rows", [])
    if len(rows) != 1:
        return False
    fields = row_fields(rows[0])
    return fields.get("ProbeKey") == key and fields.get("ProbeValue") == "Original"


def field_values(rows: list[dict[str, Any]], field: str) -> list[str]:
    return sorted(str(row_fields(row).get(field, "")) for row in rows)


def rows_empty(queries: dict[str, Any]) -> bool:
    return all(result.get("ok") and not result.get("rows", []) for result in queries.values())


def rows_present(queries: dict[str, Any], expected_counts: dict[str, int]) -> bool:
    if set(queries) != set(expected_counts):
        return False
    return all(
        result.get("ok") and len(result.get("rows", [])) == expected_counts[name] for name, result in queries.items()
    )


def query_table(context: ProbeRunContext, table: str, key: str) -> dict[str, Any]:
    return context.query_cargo_table(
        tables=table,
        fields="_pageName=Page,ProbeKey,ProbeValue,ProbeFlag,ProbeNumber",
        where="ProbeKey=" + cargo_string_literal(key),
        limit=20,
    )


def query_all(context: ProbeRunContext, candidate: Any) -> dict[str, Any]:
    return {name: query_table(context, table, candidate.key) for name, table in candidate.tables.items()}


def query_lifecycle_table(
    context: ProbeRunContext,
    table: str,
    fields: str,
    where: str,
) -> dict[str, Any]:
    return context.query_cargo_table(tables=table, fields=fields, where=where, limit=50)


def query_lifecycle_key(context: ProbeRunContext, candidate: Any, key: str) -> dict[str, Any]:
    item_where = "StableKey=" + cargo_string_literal(key)
    relationship_where = "ItemKey=" + cargo_string_literal(key)
    return {
        "items": query_lifecycle_table(
            context,
            candidate.tables["Items"],
            "_pageName=Page,StableKey,DisplayName",
            item_where,
        ),
        "obtained_from": query_lifecycle_table(
            context,
            candidate.tables["ObtainedFrom"],
            "_pageName=Page,ItemKey,SourceKey,SourceIndex",
            relationship_where,
        ),
        "used_in": query_lifecycle_table(
            context,
            candidate.tables["UsedIn"],
            "_pageName=Page,ItemKey,UseKey,UseIndex",
            relationship_where,
        ),
    }


def query_lifecycle_state(context: ProbeRunContext, candidate: Any) -> dict[str, Any]:
    return {
        candidate.item_key: query_lifecycle_key(context, candidate, candidate.item_key),
        candidate.removed_key: query_lifecycle_key(context, candidate, candidate.removed_key),
    }


def query_multi_entity_state(context: ProbeRunContext, candidate: Any) -> dict[str, Any]:
    return {key: query_lifecycle_key(context, candidate, key) for key in candidate.item_keys}


def query_multi_entity_reverse(
    context: ProbeRunContext,
    candidate: Any,
    relationship: Literal["obtained_from", "used_in"],
) -> dict[str, Any]:
    if relationship == "obtained_from":
        table = candidate.tables["ObtainedFrom"]
        fields = "_pageName=Page,ItemKey,SourceKey=RelationshipKey"  # gitleaks:allow
        where = "SourceKey=" + cargo_string_literal("SharedSource")
    else:
        table = candidate.tables["UsedIn"]
        fields = "_pageName=Page,ItemKey,UseKey=RelationshipKey"  # gitleaks:allow
        where = "UseKey=" + cargo_string_literal("SharedUse")
    return query_lifecycle_table(context, table, fields, where)


def query_lifecycle_count(context: ProbeRunContext, table: str) -> dict[str, Any]:
    result = context.query_cargo_table(tables=table, fields="COUNT(*)=Rows", limit=1)
    if not result.get("ok"):
        return result
    try:
        rows = result.get("rows", [])
        count = 0
        if rows:
            count = int(str(row_fields(rows[0]).get("Rows", "0")))
        return {"ok": True, "count": count, "rows": rows}
    except (TypeError, ValueError) as exc:
        return {"ok": False, "error": str(exc)}


def query_batch_counts(context: ProbeRunContext, candidate: Any) -> dict[str, Any]:
    return {name: query_lifecycle_count(context, table) for name, table in candidate.tables.items()}


def batch_counts_match(counts: dict[str, Any], expected_count: int) -> bool:
    return all(result.get("ok") and result.get("count") == expected_count for result in counts.values())


def _batch_source_key(prefix: str, index: int) -> str:
    return prefix + "BatchSource" + str(index).zfill(4)


def _batch_use_key(prefix: str, index: int) -> str:
    return prefix + "BatchUse" + str(index).zfill(4)


def query_batch_samples(context: ProbeRunContext, candidate: Any) -> dict[str, Any]:
    return {key: query_lifecycle_key(context, candidate, key) for key in candidate.sample_item_keys}


def batch_sample_matches(candidate: Any, sample_state: dict[str, Any]) -> bool:
    for key in candidate.sample_item_keys:
        index = candidate.item_keys.index(key) + 1
        if not lifecycle_key_matches(
            sample_state,
            key,
            (_batch_source_key(candidate.prefix, index),),
            (_batch_use_key(candidate.prefix, index),),
        ):
            return False
    return True


def wait_for_batch_counts(
    context: ProbeRunContext,
    candidate: Any,
    seconds: int,
    expected_count: int,
) -> dict[str, Any]:
    return poll_until(
        lambda: query_batch_counts(context, candidate),
        lambda counts: batch_counts_match(counts, expected_count),
        seconds,
        "counts",
    )


def multi_entity_key_state_matches(state: dict[str, Any], key: str) -> bool:
    key_state = state.get(key, {})
    if not lifecycle_key_matches(state, key, ("SharedSource",), ("SharedUse",)):
        return False
    pages = (
        field_values(key_state["items"].get("rows", []), "Page")
        + field_values(key_state["obtained_from"].get("rows", []), "Page")
        + field_values(key_state["used_in"].get("rows", []), "Page")
    )
    return len(set(pages)) == 1


def reverse_rows_match_keys(result: dict[str, Any], keys: tuple[str, str]) -> bool:
    if not result.get("ok"):
        return False
    return field_values(result.get("rows", []), "ItemKey") == sorted(keys)


def reverse_page_title_is_ambiguous(result: dict[str, Any], expected_count: int) -> bool:
    if not result.get("ok"):
        return False
    rows = result.get("rows", [])
    return len(rows) == expected_count and len(set(field_values(rows, "Page"))) == 1


def lifecycle_key_matches(
    state: dict[str, Any],
    key: str,
    source_keys: tuple[str, ...],
    use_keys: tuple[str, ...],
    item_present: bool = True,
) -> bool:
    key_state = state.get(key, {})
    if set(key_state) != {"items", "obtained_from", "used_in"}:
        return False
    if not all(result.get("ok") for result in key_state.values()):
        return False
    item_rows = key_state["items"].get("rows", [])
    obtained_rows = key_state["obtained_from"].get("rows", [])
    used_rows = key_state["used_in"].get("rows", [])
    if item_present:
        if field_values(item_rows, "StableKey") != [key]:
            return False
    elif item_rows:
        return False
    return field_values(obtained_rows, "SourceKey") == sorted(source_keys) and field_values(
        used_rows, "UseKey"
    ) == sorted(use_keys)


def lifecycle_state_matches(
    state: dict[str, Any],
    candidate: Any,
    item_sources: tuple[str, ...],
    item_uses: tuple[str, ...],
    removed_sources: tuple[str, ...],
    removed_uses: tuple[str, ...],
    removed_present: bool,
    item_present: bool = True,
) -> bool:
    return lifecycle_key_matches(
        state,
        candidate.item_key,
        item_sources,
        item_uses,
        item_present=item_present,
    ) and lifecycle_key_matches(
        state,
        candidate.removed_key,
        removed_sources,
        removed_uses,
        item_present=removed_present,
    )


def wait_for_lifecycle_state(
    context: ProbeRunContext,
    candidate: Any,
    seconds: int,
    item_sources: tuple[str, ...],
    item_uses: tuple[str, ...],
    removed_sources: tuple[str, ...],
    removed_uses: tuple[str, ...],
    removed_present: bool = True,
    item_present: bool = True,
) -> dict[str, Any]:
    return poll_until(
        lambda: query_lifecycle_state(context, candidate),
        lambda state: lifecycle_state_matches(
            state,
            candidate,
            item_sources,
            item_uses,
            removed_sources,
            removed_uses,
            removed_present=removed_present,
            item_present=item_present,
        ),
        seconds,
        "state",
    )


def wait_for_rows(context: ProbeRunContext, candidate: Any, seconds: int) -> dict[str, Any]:
    result = poll_until(
        lambda: query_all(context, candidate),
        lambda queries: rows_present(queries, candidate.expected_counts),
        seconds,
        "queries",
    )
    return {
        "present": result["matches"],
        "expected_counts": candidate.expected_counts,
        "final": result["final"],
        "last_attempts": result["last_attempts"],
    }


def standard_candidate_validation(result: dict[str, Any], candidate: Any) -> bool:
    initial_queries = result.get("initial_queries", {})
    rendered_page = result.get("rendered_page", {})
    after_recreate = result.get("queries_after_cargorecreatetables", {})
    after_recreatedata = result.get("queries_after_cargorecreatedata", {})
    return (
        rows_present(initial_queries, candidate.expected_counts)
        and rendered_page.get("ok")
        and not rendered_page.get("contains_probe_text")
        and rows_empty(after_recreate)
        and rows_present(after_recreatedata, candidate.expected_counts)
    )
