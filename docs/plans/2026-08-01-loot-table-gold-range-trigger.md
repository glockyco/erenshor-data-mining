---
title: LootTable Gold Range Trigger
type: note
status: draft
created: 2026-08-01
parent: 2026-07-09-erenshor-planning-overview
---

# LootTable Gold Range Trigger

Resume static gold-range export work only when a named consumer requires
`LootTable.MinGold` and `LootTable.MaxGold` in the clean database. Record that
consumer and its required query or output surface before creating an executable plan.

Runtime roll state remains outside this boundary. `MyGold`, `ActualDropsQual`, and
`qualUps` stay excluded unless fresh shipped-code analysis proves that a separate
named consumer requires one or more of them.

A resumed executable plan uses the main shipping variant by default. It must freshly
inspect the current raw export model and listener, processor mapping, clean schema,
and `src/tools/ExportSurface/field-coverage.json` before defining tasks. Do not copy
the superseded checklist because those paths and assumptions may have changed before
a consumer exists.
