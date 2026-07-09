from __future__ import annotations

from erenshor.tools.wiki_cargo_probe.models import MANUAL_DELETE_BASE, manual_cleanup_urls
from erenshor.tools.wiki_cargo_probe.scenarios.lifecycle import build_lifecycle_probe
from erenshor.tools.wiki_cargo_probe.scenarios.multi_entity import build_multi_entity_probe
from erenshor.tools.wiki_cargo_probe.scenarios.recreate_batching import build_recreate_batching_probe
from erenshor.tools.wiki_cargo_probe.scenarios.standard import (
    build_direct_probe,
    build_lua_nested_probe,
    build_nested_probe,
)


def test_direct_probe_builds_direct_attach_templates() -> None:
    candidate = build_direct_probe("UnitProbe")

    assert candidate.kind == "direct"
    assert candidate.key == "UnitProbeDirectKey"
    assert candidate.page_title == "User:WoWMuch/CargoStorageProbe/UnitProbe/Direct"
    assert candidate.table_names == ("UnitProbeDirectA", "UnitProbeDirectB", "UnitProbeDirectC")
    assert candidate.page_titles == (candidate.page_title,)
    assert candidate.expected_counts == {"A": 1, "B": 1, "C": 1}
    assert candidate.recreate_templates == (
        "CargoStorageProbe/UnitProbe/DirectBDeclare",
        "CargoStorageProbe/UnitProbe/DirectCDeclare",
        "CargoStorageProbe/UnitProbe/DirectMain",
    )
    templates = {template.title: template.content for template in candidate.template_pages}
    assert set(templates) == {
        "Template:CargoStorageProbe/UnitProbe/DirectMain",
        "Template:CargoStorageProbe/UnitProbe/DirectBDeclare",
        "Template:CargoStorageProbe/UnitProbe/DirectCDeclare",
    }
    assert "#cargo_attach:_table=UnitProbeDirectB" in templates["Template:CargoStorageProbe/UnitProbe/DirectMain"]
    assert "#cargo_attach:_table=UnitProbeDirectC" in templates["Template:CargoStorageProbe/UnitProbe/DirectMain"]
    assert "__A__" not in templates["Template:CargoStorageProbe/UnitProbe/DirectMain"]


def test_nested_probe_builds_nested_store_templates() -> None:
    candidate = build_nested_probe("UnitProbe")

    assert candidate.kind == "nested"
    assert candidate.key == "UnitProbeNestedKey"
    assert candidate.table_names == ("UnitProbeNestedA", "UnitProbeNestedB", "UnitProbeNestedC")
    assert candidate.recreatedata_pairs == (
        ("CargoStorageProbe/UnitProbe/NestedMain", "UnitProbeNestedA"),
        ("CargoStorageProbe/UnitProbe/NestedBStore", "UnitProbeNestedB"),
        ("CargoStorageProbe/UnitProbe/NestedCStore", "UnitProbeNestedC"),
    )
    templates = {template.title: template.content for template in candidate.template_pages}
    assert "CargoStorageProbe/UnitProbe/NestedBStore" in templates["Template:CargoStorageProbe/UnitProbe/NestedMain"]
    assert "#cargo_store:_table=UnitProbeNestedB" in templates["Template:CargoStorageProbe/UnitProbe/NestedBStore"]
    assert "#cargo_store:_table=UnitProbeNestedC" in templates["Template:CargoStorageProbe/UnitProbe/NestedCStore"]


def test_lua_nested_probe_builds_module_backed_templates() -> None:
    candidate = build_lua_nested_probe("UnitProbe")

    assert candidate.kind == "lua-nested"
    assert candidate.key == "UnitProbeLuaNestedKey"
    assert candidate.expected_counts == {"A": 1, "B": 2, "C": 1}
    assert candidate.table_names == ("UnitProbeLuaNestedA", "UnitProbeLuaNestedB", "UnitProbeLuaNestedC")
    templates = {template.title: template.content for template in candidate.template_pages}
    assert "Module:CargoStorageProbe/UnitProbe" in templates
    assert "UnitProbeLuaNestedA" in templates["Module:CargoStorageProbe/UnitProbe"]
    assert "function p.storeB(frame)" in templates["Module:CargoStorageProbe/UnitProbe"]
    assert (
        "#invoke:CargoStorageProbe/UnitProbe|storeA" in templates["Template:CargoStorageProbe/UnitProbe/LuaNestedMain"]
    )


def test_lifecycle_probe_builds_isolated_pages_tables_and_state_transitions() -> None:
    candidate = build_lifecycle_probe("UnitProbe")

    assert candidate.kind == "lifecycle"
    assert candidate.page_title == "User:WoWMuch/CargoStorageProbe/UnitProbe/Lifecycle"
    assert candidate.template_base == "CargoStorageProbe/UnitProbe/Lifecycle"
    assert candidate.item_key == "UnitProbeLifecycleItemA"
    assert candidate.removed_key == "UnitProbeLifecycleItemB"
    assert candidate.tables == {
        "Items": "UnitProbeLifecycleItems",
        "ObtainedFrom": "UnitProbeLifecycleObtainedFrom",
        "UsedIn": "UnitProbeLifecycleUsedIn",
    }
    assert candidate.table_names == (
        "UnitProbeLifecycleItems",
        "UnitProbeLifecycleObtainedFrom",
        "UnitProbeLifecycleUsedIn",
    )

    templates_by_title = {template.title: template.content for template in candidate.templates}
    assert set(templates_by_title) == {
        "Module:CargoStorageProbe/UnitProbe/Lifecycle",
        "Template:CargoStorageProbe/UnitProbe/LifecycleMain",
        "Template:CargoStorageProbe/UnitProbe/LifecycleObtainedFromStore",
        "Template:CargoStorageProbe/UnitProbe/LifecycleUsedInStore",
    }
    module_content = templates_by_title["Module:CargoStorageProbe/UnitProbe/Lifecycle"]
    assert "local tables = { Items = 'UnitProbeLifecycleItems'" in module_content
    assert "ObtainedFrom = 'UnitProbeLifecycleObtainedFrom'" in module_content
    assert "UsedIn = 'UnitProbeLifecycleUsedIn'" in module_content
    assert "__Items__" not in module_content
    assert "__ObtainedFrom__" not in module_content
    assert "__UsedIn__" not in module_content

    assert candidate.recreatedata_pairs == (
        ("CargoStorageProbe/UnitProbe/LifecycleMain", "UnitProbeLifecycleItems"),
        ("CargoStorageProbe/UnitProbe/LifecycleObtainedFromStore", "UnitProbeLifecycleObtainedFrom"),
        ("CargoStorageProbe/UnitProbe/LifecycleUsedInStore", "UnitProbeLifecycleUsedIn"),
    )
    assert "|stablekey=UnitProbeLifecycleItemA" in candidate.initial_content
    assert "|stablekey=UnitProbeLifecycleItemB" in candidate.initial_content
    assert "|source2=SourceA2" not in candidate.reduced_content
    assert "|use1=UseA1" not in candidate.reduced_content
    assert "UnitProbeLifecycleItemB" not in candidate.removed_content


def test_multi_entity_probe_builds_one_sandbox_page_with_two_item_transclusions() -> None:
    candidate = build_multi_entity_probe("UnitProbe")

    assert candidate.kind == "multi-entity"
    assert candidate.page_title == "User:WoWMuch/CargoStorageProbe/UnitProbe/MultiEntity"
    assert candidate.template_base == "CargoStorageProbe/UnitProbeMultiEntity/Lifecycle"
    assert candidate.item_keys == ("UnitProbeMultiEntityItemA", "UnitProbeMultiEntityItemB")
    assert candidate.recreatedata_pairs == (
        ("CargoStorageProbe/UnitProbeMultiEntity/LifecycleMain", "UnitProbeMultiEntityLifecycleItems"),
        (
            "CargoStorageProbe/UnitProbeMultiEntity/LifecycleObtainedFromStore",
            "UnitProbeMultiEntityLifecycleObtainedFrom",
        ),
        ("CargoStorageProbe/UnitProbeMultiEntity/LifecycleUsedInStore", "UnitProbeMultiEntityLifecycleUsedIn"),
    )
    assert candidate.page_content.startswith("{{CargoStorageProbe/UnitProbeMultiEntity/LifecycleMain")
    assert candidate.page_content.count("|stablekey=UnitProbeMultiEntityItemA") == 1
    assert candidate.page_content.count("|stablekey=UnitProbeMultiEntityItemB") == 1
    assert candidate.page_content.count("|source1=SharedSource") == 2
    assert candidate.page_content.count("|use1=SharedUse") == 2


def test_recreate_batching_probe_builds_one_page_per_item_with_matching_storage_keys() -> None:
    candidate = build_recreate_batching_probe("UnitProbe", 3)

    assert candidate.kind == "recreate-batching"
    assert candidate.page_titles == (
        "User:WoWMuch/CargoStorageProbe/UnitProbe/RecreateBatching/Page0001",
        "User:WoWMuch/CargoStorageProbe/UnitProbe/RecreateBatching/Page0002",
        "User:WoWMuch/CargoStorageProbe/UnitProbe/RecreateBatching/Page0003",
    )
    assert candidate.item_keys == (
        "UnitProbeBatchItem0001",
        "UnitProbeBatchItem0002",
        "UnitProbeBatchItem0003",
    )
    assert candidate.sample_item_keys == candidate.item_keys
    assert candidate.tables == {
        "Items": "UnitProbeBatchLifecycleItems",
        "ObtainedFrom": "UnitProbeBatchLifecycleObtainedFrom",
        "UsedIn": "UnitProbeBatchLifecycleUsedIn",
    }
    assert candidate.recreatedata_pairs == (
        ("CargoStorageProbe/UnitProbeBatch/LifecycleMain", "UnitProbeBatchLifecycleItems"),
        (
            "CargoStorageProbe/UnitProbeBatch/LifecycleObtainedFromStore",
            "UnitProbeBatchLifecycleObtainedFrom",
        ),
        ("CargoStorageProbe/UnitProbeBatch/LifecycleUsedInStore", "UnitProbeBatchLifecycleUsedIn"),
    )
    assert candidate.page_contents == (
        "{{CargoStorageProbe/UnitProbeBatch/LifecycleMain\n"
        "|stablekey=UnitProbeBatchItem0001\n"
        "|name=Batch Item 0001\n"
        "|source1=UnitProbeBatchSource0001\n"
        "|use1=UnitProbeBatchUse0001\n"
        "}}\n",
        "{{CargoStorageProbe/UnitProbeBatch/LifecycleMain\n"
        "|stablekey=UnitProbeBatchItem0002\n"
        "|name=Batch Item 0002\n"
        "|source1=UnitProbeBatchSource0002\n"
        "|use1=UnitProbeBatchUse0002\n"
        "}}\n",
        "{{CargoStorageProbe/UnitProbeBatch/LifecycleMain\n"
        "|stablekey=UnitProbeBatchItem0003\n"
        "|name=Batch Item 0003\n"
        "|source1=UnitProbeBatchSource0003\n"
        "|use1=UnitProbeBatchUse0003\n"
        "}}\n",
    )


def test_manual_cleanup_urls_prefixes_tables() -> None:
    assert manual_cleanup_urls(["A", "B"]) == [MANUAL_DELETE_BASE + "A", MANUAL_DELETE_BASE + "B"]
