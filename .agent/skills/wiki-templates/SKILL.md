---
name: wiki-templates
description: Work with MediaWiki page generation and templates. Use when creating wiki pages, modifying templates, or understanding the wiki deployment system.
---

# Wiki Template System

Generates MediaWiki pages from database entities using Jinja2 templates.

## Architecture

```
Database → Repository → Page Generator → Jinja2 Template → Wikitext
```

## Workflow

```bash
uv run erenshor wiki fetch      # Download existing pages from wiki
uv run erenshor wiki generate   # Generate pages locally
uv run erenshor wiki deploy     # Upload changes to wiki
```

Generated pages: `variants/{variant}/wiki/generated/`
Fetched pages: `variants/{variant}/wiki/fetched/`

## Directory Structure

```
src/erenshor/application/wiki/generators/
├── base.py              # Base generator class
├── context.py           # Template context building
├── field_preservation.py # Preserve manually-edited wiki fields
├── formatting.py        # Wikitext formatting utilities
├── pages/               # Page generators
│   ├── entities.py      # Entity page generators
│   ├── armor_overview.py
│   └── weapons_overview.py
├── sections/            # Page section generators
└── templates/           # Jinja2 templates
```

## Jinja2 Templates

Located in `generators/templates/`:

**Items** (by type):
- weapon.jinja2, armor.jinja2, charm.jinja2
- consumable.jinja2, general.jinja2
- skillbook.jinja2, spellscroll.jinja2
- mold.jinja2, aura.jinja2, item.jinja2

**Characters**:
- character.jinja2

**Abilities**:
- ability.jinja2

## Field Preservation

The system preserves manually-edited fields from existing wiki pages.
See `field_preservation.py` for the full preservation rules.

Key preserved fields by template:
- **Items**: `image`, `imagecaption` (prefer manual), `othersource`, `type`/`questsource`/`relatedquest` (merge)
- **Characters**: `imagecaption`, `type` (prefer manual), `zones`/`coordinates`/`respawn` (prefer database)
- **Abilities**: `image` (prefer manual)

## Services

Located in `src/erenshor/application/wiki/services/`:
- Wiki fetch, generate, deploy orchestration
- Page comparison and diff generation
- Deployment batching

## Common Tasks

**Generate all pages**:
```bash
uv run erenshor wiki generate
```

**Generate specific pages from file**:
```bash
# Create pages.txt with one page title per line
uv run erenshor wiki generate --pages-file pages.txt

# Or pipe from stdin
echo "Sword of Flames" | uv run erenshor wiki generate --pages-file -
```

**Limit for testing**:
```bash
uv run erenshor wiki generate --limit 10
```

**Preview without deploying**:
```bash
uv run erenshor wiki generate
ls variants/main/wiki/generated/
```

**Deploy with confirmation**:
```bash
uv run erenshor wiki deploy --dry-run  # Preview changes
uv run erenshor wiki deploy            # Actually deploy
```
