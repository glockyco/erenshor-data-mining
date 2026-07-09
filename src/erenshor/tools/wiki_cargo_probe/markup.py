from __future__ import annotations


def store_probe_row(table: str, value: str, number: int = 1, flag: str = "yes") -> str:
    return (
        "{{#cargo_store:_table="
        + table
        + "|ProbeKey={{{key|}}}|ProbeValue="
        + value
        + "|ProbeFlag="
        + flag
        + "|ProbeNumber="
        + str(number)
        + "}}"
    )


def declare_probe_table(table: str) -> str:
    return (
        "{{#cargo_declare:_table="
        + table
        + "|ProbeKey=String|ProbeValue=String|ProbeFlag=Boolean|ProbeNumber=Integer}}"
    )


def declare_lifecycle_table(table: str, fields: str) -> str:
    return "{{#cargo_declare:_table=" + table + "|" + fields + "}}"


def lifecycle_item_call(
    template_base: str,
    stable_key: str,
    name: str,
    sources: tuple[str, ...],
    uses: tuple[str, ...],
) -> str:
    fields = [
        "{{" + template_base + "Main",
        "|stablekey=" + stable_key,
        "|name=" + name,
    ]
    fields.extend("|source" + str(index) + "=" + source for index, source in enumerate(sources, start=1))
    fields.extend("|use" + str(index) + "=" + use for index, use in enumerate(uses, start=1))
    fields.append("}}")
    return "\n".join(fields)
