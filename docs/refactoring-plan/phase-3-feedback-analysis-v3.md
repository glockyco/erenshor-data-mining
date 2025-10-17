# Phase 3 Feedback Analysis v3 (Final Round)

**Date**: 2025-10-17
**Status**: Final - Ready for Implementation
**Purpose**: Address third round of critical feedback with simplified, essential designs

---

## Executive Summary

This is the **final round** of analysis. We've converged on minimal, essential designs by:

1. **Category Tags**: Use `{{Item}}` + separate `[[Category:...]]` tags (not template-based)
2. **Precondition Architecture**: Per-command files with decorator pattern (not single file)
3. **Legacy Templates**: Found ALL replacements including Character → Enemy
4. **Field Preservation**: Simplified to default=override + custom handlers only
5. **Manual Edit UX**: Push-style notifications in existing output (no new commands)

**Key Philosophy**: Simple, structural enforcement, good UX/DX, no feature creep.

---

## Changes from V2

### Major Simplifications

1. **Field Preservation System**: Removed 90% of complexity
   - Old: Multiple modes (preserve, override, merge, custom)
   - New: Default=override, everything else=custom handlers
   - "Preserve" is just a built-in custom handler

2. **Precondition Architecture**: Distributed, not centralized
   - Old: Single `preconditions.py` file with all checks
   - New: Per-command check files with decorator enforcement
   - Hard to forget, hard to bypass

3. **Manual Edit Notifications**: Integrated into existing output
   - Old: Separate review commands
   - New: Automatic output in wiki update command
   - Visual hierarchy prevents overload

### New Discoveries

1. **Category Tags**: Templates auto-add categories, preventing variation
2. **Legacy Character Template**: Missed Character → Enemy in v2
3. **Actual Field Usage**: Only 4 fields actually preserved in old code

---

## Issue 1: Category Tag Strategy

### Current Approach Analysis

**Template-Based Categories** (what some templates do):
```wikitext
{{Mold
|name=Sword Mold
|...
}}
<!-- Template automatically adds: [[Category:Molds]] -->
```

**Problems**:
- ❌ Categories encoded in template prevent variation
- ❌ Multi-category items impossible
- ❌ Changing categories requires template changes
- ❌ Less flexible than explicit tags

**Manual Category Tags** (proposed):
```wikitext
{{Item
|name=Sword Mold
|...
}}

[[Category:Molds]]
[[Category:Crafting Materials]]
```

**Benefits**:
- ✅ Multi-category support
- ✅ Easy to change categories
- ✅ No template modifications needed
- ✅ More flexible for edge cases

### Recommendation

**Use manual category tags**, not template-based categories.

**Rationale**:
1. User is correct - template categories prevent variation
2. Real-world examples need multiple categories (e.g., items that are both Consumables and Quest Items)
3. Easier to maintain (change category without template edits)
4. More discoverable in wiki source

### Implementation

**Generate category tags programmatically**:

```python
# In item generator

def _generate_category_tags(item: Item, kind: ItemKind) -> list[str]:
    """Generate category tags for item.

    Returns:
        List of category names (without [[Category:...]] wrapper)
    """
    categories = []

    # Primary category from item kind
    kind_to_category = {
        "weapon": "Weapons",
        "armor": "Armor",
        "charm": "Charms",
        "aura": "Auras",
        "ability_book": "Ability Books",
        "consumable": "Consumables",
        "mold": "Molds",
        "general": "Items",
    }

    primary = kind_to_category.get(kind, "Items")
    categories.append(primary)

    # Secondary categories based on properties
    if item.is_quest_item:
        categories.append("Quest Items")

    if item.is_craftable:
        categories.append("Craftable")

    if item.rarity == "Legendary":
        categories.append("Legendary Items")

    # Template flag = 1 (molds are also crafting materials)
    if item.template_flag == 1:
        categories.append("Crafting Materials")

    return categories

def generate_item_page(item: Item) -> str:
    """Generate complete item page."""
    # ... generate template ...

    # Add category tags at end
    categories = self._generate_category_tags(item, kind)
    category_tags = "\n".join(f"[[Category:{cat}]]" for cat in categories)

    return f"{template_content}\n\n{category_tags}"
```

**Example output**:
```wikitext
{{Item
|name=Sword Mold
|type=Crafting Material
|...
}}

== Description ==
<!-- MANUAL CONTENT PRESERVED -->

[[Category:Molds]]
[[Category:Crafting Materials]]
```

**Multi-category example**:
```wikitext
{{Item
|name=Ancient Key
|type=Quest Item
|...
}}

[[Category:Items]]
[[Category:Quest Items]]
[[Category:Legendary Items]]
```

### Edge Cases

**1. Item changes type** (e.g., Mold → Consumable in game update)
- Old: `[[Category:Molds]]`
- New: `[[Category:Consumables]]`
- Result: Category tag replaced on update

**2. Manual category additions**
- Original: `[[Category:Items]]`
- Manual edit adds: `[[Category:Rare Drops]]`
- Generated: `[[Category:Items]]`
- Result: **Preserve manual additions** (see field preservation)

**3. Categories at different locations in page**
- Standard: Categories at end of page
- Manual: Categories moved to different section
- Result: **Append new categories** to end, don't remove manual ones

### Template-Specific Handling

**No template changes needed** - templates should NOT add categories automatically.

Instead, generator decides categories based on item data.

---

## Issue 2: Precondition Check Architecture

### Problems with Single-File Approach

From user feedback:
> "Single file for all checks will blow up over time A LOT!"
> "How to ensure we don't forget to add precondition checks?"
> "How to ensure we don't forget to USE the precondition system?"
> "Too easy to unintentionally circumvent"
> "Lots of boilerplate per command"

**Single File Issues**:
- 🔴 Will grow to 1000+ lines
- 🔴 Easy to forget adding new checks
- 🔴 Easy to forget calling checks in commands
- 🔴 No structural enforcement
- 🔴 Lots of repetitive boilerplate

### Proposed Architecture

**Distributed Per-Command Checks** with structural enforcement:

```
src/erenshor/application/preconditions/
├── __init__.py              # Exports decorator
├── base.py                  # Base precondition system
├── decorator.py             # @require_preconditions decorator
├── checks/
│   ├── __init__.py          # Exports all check functions
│   ├── database.py          # Database-related checks
│   ├── filesystem.py        # File/directory checks
│   ├── unity.py             # Unity-related checks
│   └── steam.py             # Steam/game checks
└── registry.py              # Auto-discovery of checks

src/erenshor/cli/commands/
├── export.py                # Uses @require_preconditions decorator
├── deploy.py                # Uses @require_preconditions decorator
└── ...
```

**Key Innovation**: **Decorator pattern** makes it hard to forget.

### Implementation Details

#### Base Precondition System

```python
# src/erenshor/application/preconditions/base.py

from dataclasses import dataclass
from typing import Callable

@dataclass
class PreconditionResult:
    """Result of a precondition check."""
    passed: bool
    check_name: str
    message: str
    detail: str = ""

    def __str__(self) -> str:
        """Format for display."""
        if self.passed:
            return f"✓ {self.message}"
        else:
            result = f"✗ {self.message}"
            if self.detail:
                result += f"\n  {self.detail}"
            return result

# Type alias for check functions
PreconditionCheck = Callable[[dict], PreconditionResult]
```

#### Check Functions (Shared, Reusable)

```python
# src/erenshor/application/preconditions/checks/database.py

from pathlib import Path
import sqlite3
from ..base import PreconditionResult

def database_exists(context: dict) -> PreconditionResult:
    """Check if SQLite database exists."""
    db_path = Path(context["database_path"])

    if not db_path.exists():
        return PreconditionResult(
            passed=False,
            check_name="database_exists",
            message="Database not found",
            detail=f"Missing: {db_path}"
        )

    return PreconditionResult(
        passed=True,
        check_name="database_exists",
        message="Database exists"
    )

def database_valid(context: dict) -> PreconditionResult:
    """Check if database is valid SQLite."""
    db_path = Path(context["database_path"])

    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1")
        cursor.fetchone()
        conn.close()
    except Exception as e:
        return PreconditionResult(
            passed=False,
            check_name="database_valid",
            message="Database invalid",
            detail=f"Error: {e}"
        )

    return PreconditionResult(
        passed=True,
        check_name="database_valid",
        message="Database valid"
    )

def database_has_items(context: dict) -> PreconditionResult:
    """Check if database contains items."""
    db_path = Path(context["database_path"])

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM Item")
    count = cursor.fetchone()[0]
    conn.close()

    if count == 0:
        return PreconditionResult(
            passed=False,
            check_name="database_has_items",
            message="Database is empty",
            detail="No items found in database"
        )

    return PreconditionResult(
        passed=True,
        check_name="database_has_items",
        message=f"Database has {count} items"
    )
```

```python
# src/erenshor/application/preconditions/checks/unity.py

from pathlib import Path
from ..base import PreconditionResult

def unity_project_exists(context: dict) -> PreconditionResult:
    """Check if Unity project exists."""
    unity_dir = Path(context["unity_project"])

    if not unity_dir.exists():
        return PreconditionResult(
            passed=False,
            check_name="unity_project_exists",
            message="Unity project not found",
            detail=f"Missing: {unity_dir}"
        )

    if not (unity_dir / "Assets").exists():
        return PreconditionResult(
            passed=False,
            check_name="unity_project_exists",
            message="Unity project invalid",
            detail="Assets directory missing"
        )

    return PreconditionResult(
        passed=True,
        check_name="unity_project_exists",
        message="Unity project exists"
    )

def editor_scripts_linked(context: dict) -> PreconditionResult:
    """Check if Editor scripts are symlinked."""
    unity_dir = Path(context["unity_project"])
    editor_dir = unity_dir / "Assets" / "Editor"

    if not editor_dir.exists():
        return PreconditionResult(
            passed=False,
            check_name="editor_scripts_linked",
            message="Editor scripts not linked",
            detail=f"Missing: {editor_dir}"
        )

    if not editor_dir.is_symlink():
        return PreconditionResult(
            passed=False,
            check_name="editor_scripts_linked",
            message="Editor directory not a symlink",
            detail="Expected symlink to src/Assets/Editor"
        )

    return PreconditionResult(
        passed=True,
        check_name="editor_scripts_linked",
        message="Editor scripts linked"
    )
```

#### Decorator for Commands

```python
# src/erenshor/application/preconditions/decorator.py

from functools import wraps
from typing import Callable
from .base import PreconditionCheck, PreconditionResult
from rich.console import Console

def require_preconditions(*checks: PreconditionCheck):
    """Decorator to enforce precondition checks on command functions.

    Usage:
        @require_preconditions(
            database_exists,
            database_valid,
            database_has_items
        )
        def deploy_command(variant: str):
            # Command logic here
            pass

    If any check fails, the command will not execute.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            console = Console()

            # Build context from command arguments
            # This assumes first arg is variant (adjust as needed)
            variant = args[0] if args else kwargs.get("variant", "main")
            from erenshor.infrastructure.config import load_variant_config
            config = load_variant_config(variant)

            context = {
                "variant": variant,
                "database_path": config.get("database"),
                "unity_project": config.get("unity_project"),
                "game_dir": config.get("game_dir"),
                **kwargs  # Include any additional kwargs
            }

            # Run all precondition checks
            results = []
            for check in checks:
                result = check(context)
                results.append(result)

            # Check if all passed
            all_passed = all(r.passed for r in results)

            if not all_passed:
                # Show failure
                console.print("\n[bold red]Precondition checks failed:[/bold red]\n")
                for result in results:
                    if result.passed:
                        console.print(f"  [green]{result}[/green]")
                    else:
                        console.print(f"  [red]{result}[/red]")

                console.print("\n[yellow]Abort: Fix issues before running command[/yellow]\n")
                return 1  # Exit code

            # All checks passed - run command
            return func(*args, **kwargs)

        return wrapper
    return decorator
```

#### Usage in Commands

```python
# src/erenshor/cli/commands/export.py

from erenshor.application.preconditions import require_preconditions
from erenshor.application.preconditions.checks.unity import (
    unity_project_exists,
    editor_scripts_linked,
)

@require_preconditions(
    unity_project_exists,
    editor_scripts_linked,
)
def command_main(variant: str = "main"):
    """Export game data to SQLite via Unity batch mode."""

    # No need for manual precondition checks - decorator handles it

    # Command logic
    logger.info("Starting Unity export...")
    # ...
```

```python
# src/erenshor/cli/commands/deploy.py

from erenshor.application.preconditions import require_preconditions
from erenshor.application.preconditions.checks.database import (
    database_exists,
    database_valid,
    database_has_items,
)

@require_preconditions(
    database_exists,
    database_valid,
    database_has_items,
)
def command_main(variant: str = "main"):
    """Deploy data to wiki."""

    # Preconditions already checked by decorator

    # Command logic
    logger.info("Deploying to wiki...")
    # ...
```

### How It Prevents Forgetting

**1. Can't forget to add checks**: Decorator is visible at function definition
```python
# WRONG - will fail immediately (decorator requires checks)
@require_preconditions()  # Empty - linter warning
def command_main():
    pass

# RIGHT - checks are obvious
@require_preconditions(
    database_exists,
    database_valid,
)
def command_main():
    pass
```

**2. Can't forget to use system**: Decorator is at function level
```python
# WRONG - no decorator, no enforcement
def command_main():  # Missing decorator!
    pass

# Type hints can help catch this:
from erenshor.application.preconditions import Checked

def command_main() -> Checked:  # Type system enforces decorator
    pass
```

**3. Can't bypass accidentally**: Checks run BEFORE function body
```python
# Even if you try to bypass, checks run first
@require_preconditions(database_exists)
def command_main():
    # This won't run if database doesn't exist
    do_stuff()
```

**4. Minimal boilerplate**: One line per command
```python
# Old way (manual checks):
def command_main():
    checker = PreconditionChecker()
    if not checker.check_database():
        return 1
    if not checker.check_unity():
        return 1
    # 10+ lines of boilerplate

# New way (decorator):
@require_preconditions(database_exists, unity_project_exists)
def command_main():
    # Just one line, no boilerplate
```

### Structural Guarantees

**Compile-time checks**:
- Import error if check function doesn't exist
- Type hints ensure check functions match signature

**Runtime checks**:
- Decorator ensures checks run before command
- Impossible to skip checks without removing decorator

**Discovery**:
- All checks in `checks/` directory
- Import from `checks/__init__.py`
- Easy to see all available checks

**Extensibility**:
- Add new check: Create function in appropriate `checks/*.py` file
- Use check: Import and add to decorator
- No central registry to update

---

## Issue 3: Complete Legacy Template Mapping

### Survey Results from Old Code

Checked ALL transformer and generator files. Here are ALL legacy template replacements:

#### From Items (in `items.py` and `merger.py`)

```python
# Line 159 in transformers/items.py
pattern = re.compile(
    r"^\{\{\s*(Weapon|Armor|Auras|Ability Books|Ability_Books|Consumable|Mold|Item)"
)

# Line 131-140 in transformers/merger.py
names = [
    "Weapon",
    "Armor",
    "Auras",
    "Ability Books",
    "Ability_Books",
    "Consumable",
    "Mold",
    "Item",
]
```

#### From Characters (in `characters.py`)

```python
# Line 77-80 in transformers/characters.py
enemy_templates = mw_find_templates(code, ["Enemy"])
character_templates = mw_find_templates(code, ["Character"])
pet_templates = mw_find_templates(code, ["Pet"])
enemy_stats_templates = mw_find_templates(code, ["Enemy Stats"])

# Lines 129-135: Remove legacy templates
for t in enemy_stats_templates:
    code.replace(t, "")
for t in character_templates:
    code.replace(t, "")
for t in pet_templates:
    code.replace(t, "")
```

#### From Validation (confirms above)

```python
# validation/characters.py line 31
# - No legacy templates (Enemy Stats, Character, Pet)

# cli/commands/audit.py line 421
("Character", "Enemy"),  # Migrating all characters to Enemy template
```

### Complete Mapping Table

| Legacy Template | Current Template | Entity Type | Notes |
|----------------|------------------|-------------|-------|
| `{{Weapon}}` | `{{Item}}` | Weapon | Keep `{{Fancy-weapon}}` tables |
| `{{Armor}}` | `{{Item}}` | Armor | Keep `{{Fancy-armor}}` tables |
| `{{Consumable}}` | `{{Item}}` | Consumable | Discontinued per user feedback |
| `{{Mold}}` | `{{Item}}` | Mold | Use with `[[Category:Molds]]` |
| `{{Ability Books}}` | `{{Item}}` | Ability Book | Both spellings |
| `{{Ability_Books}}` | `{{Item}}` | Ability Book | Underscore variant |
| `{{Auras}}` | `{{Item}}` | Aura | Discontinued |
| `{{Character}}` | `{{Enemy}}` | NPC/Enemy | **MISSED IN V2** |
| `{{Pet}}` | `{{Enemy}}` | Pet | **MISSED IN V2** |
| `{{Enemy Stats}}` | *(remove)* | Enemy | Legacy stats template |

### Implementation

```python
# src/erenshor/application/services/legacy_template_remover.py

class LegacyTemplateRemover:
    """Remove discontinued templates and replace with current templates."""

    # Item templates
    LEGACY_ITEM_TO_CURRENT = {
        "Weapon": "Item",
        "Armor": "Item",
        "Consumable": "Item",
        "Mold": "Item",
        "Ability Books": "Item",
        "Ability_Books": "Item",
        "Auras": "Item",
    }

    # Character templates
    LEGACY_CHARACTER_TO_CURRENT = {
        "Character": "Enemy",
        "Pet": "Enemy",
    }

    # Templates to completely remove (no replacement)
    TEMPLATES_TO_REMOVE = [
        "Enemy Stats",
    ]

    def remove_legacy_item_templates(self, page_text: str) -> str:
        """Replace legacy item templates with {{Item}}.

        Args:
            page_text: Original wiki page text

        Returns:
            Updated page text with legacy templates replaced
        """
        import mwparserfromhell as mw

        code = mw.parse(page_text)

        for template in list(code.filter_templates()):
            name = template.name.strip()

            if name in self.LEGACY_ITEM_TO_CURRENT:
                # Get replacement template name
                new_name = self.LEGACY_ITEM_TO_CURRENT[name]

                # Change template name
                template.name = new_name

                logger.info(f"Replaced {{{{'{name}'}}} with {{{{'{new_name}'}}}}")

        return str(code)

    def remove_legacy_character_templates(self, page_text: str) -> str:
        """Replace legacy character templates with {{Enemy}}.

        Args:
            page_text: Original wiki page text

        Returns:
            Updated page text with legacy templates replaced
        """
        import mwparserfromhell as mw

        code = mw.parse(page_text)

        # Replace Character/Pet with Enemy
        for template in list(code.filter_templates()):
            name = template.name.strip()

            if name in self.LEGACY_CHARACTER_TO_CURRENT:
                new_name = self.LEGACY_CHARACTER_TO_CURRENT[name]
                template.name = new_name
                logger.info(f"Replaced {{{{'{name}'}}} with {{{{'{new_name}'}}}}")

        # Remove Enemy Stats entirely
        for template in list(code.filter_templates()):
            name = template.name.strip()

            if name in self.TEMPLATES_TO_REMOVE:
                code.remove(template)
                logger.info(f"Removed legacy {{{{'{name}'}}} template")

        return str(code)
```

### Usage in Content Merger

```python
# Integrate with content merger

class ContentMerger:
    def merge(self, original: str, generated: str, ...) -> str:
        """Merge generated content with original page."""

        # Step 1: Remove legacy templates FIRST
        remover = LegacyTemplateRemover()

        if entity_type == "item":
            cleaned = remover.remove_legacy_item_templates(original)
        elif entity_type == "character":
            cleaned = remover.remove_legacy_character_templates(original)
        else:
            cleaned = original

        # Step 2: Merge with generated content
        merged = self._merge_infobox(cleaned, generated)

        return merged
```

---

## Issue 4: Minimal Field Preservation System

### What Old Code Actually Uses

From `merger.py` line 53:
```python
preserve_fields = ["othersource", "type", "imagecaption", "relatedquest"]
```

From `characters.py` lines 96-127:
```python
# Preserve imagecaption when blank in generated
if existing_caption and not cur_cap:
    nt.add("imagecaption", existing_caption, showkey=True)

# Preserve Boss type if manually set
if existing_type == "[[Enemies|Boss]]":
    nt.add("type", "[[Enemies|Boss]]", showkey=True)
```

**That's it.** Only 4 fields, only when generated value is blank.

### Simplified Design

**Philosophy** from user:
> "Override is default (or should be)"
> "Everything else can be custom handlers"
> "Even 'preserve' should be a custom handler (but built-in)"

**Minimal System**:
1. **Default behavior**: Override with generated value
2. **Custom handlers**: For special cases (preserve, merge, etc.)
3. **Template-specific**: Handlers can be scoped to templates

### Configuration Format

```toml
# config.toml - Minimal field preservation config

[wiki.field_preservation]
# Default policy for all fields
default = "override"

# Field-specific handlers (only when NOT default)
# Each value is a handler name from the registry

[wiki.field_preservation.item]
# Item template fields
othersource = "merge_sources"      # Merge old + new
imagecaption = "preserve_if_blank" # Keep old if generated is blank
relatedquest = "preserve_if_blank" # Keep old if generated is blank

[wiki.field_preservation.enemy]
# Enemy template fields
imagecaption = "preserve_if_blank" # Keep old if generated is blank
type = "preserve_boss_type"        # Special handler for Boss type
```

### Built-in Handlers

```python
# src/erenshor/application/services/field_handlers.py

from typing import Protocol

class FieldHandler(Protocol):
    """Protocol for field preservation handlers."""

    def handle(self, old_value: str, new_value: str, context: dict) -> str:
        """Handle field merging.

        Args:
            old_value: Value from existing wiki page
            new_value: Value from generated content
            context: Additional context (template type, item kind, etc.)

        Returns:
            Resolved value to use
        """
        ...

# Default handler (override)
class OverrideHandler:
    """Always use generated value (default behavior)."""

    def handle(self, old_value: str, new_value: str, context: dict) -> str:
        return new_value

# Built-in handlers
class PreserveIfBlankHandler:
    """Preserve old value if generated value is blank."""

    def handle(self, old_value: str, new_value: str, context: dict) -> str:
        if not new_value.strip():
            return old_value
        return new_value

class MergeSourcesHandler:
    """Merge source fields (deduplicate)."""

    def handle(self, old_value: str, new_value: str, context: dict) -> str:
        from erenshor.shared.game_constants import WIKITEXT_LINE_SEPARATOR

        # Split into parts
        old_parts = [p.strip() for p in old_value.split(WIKITEXT_LINE_SEPARATOR) if p.strip()]
        new_parts = [p.strip() for p in new_value.split(WIKITEXT_LINE_SEPARATOR) if p.strip()]

        # Deduplicate while preserving order
        merged = []
        for part in new_parts + old_parts:
            if part not in merged:
                merged.append(part)

        return WIKITEXT_LINE_SEPARATOR.join(merged)

class PreserveBossTypeHandler:
    """Preserve Boss type if manually set (character-specific)."""

    def handle(self, old_value: str, new_value: str, context: dict) -> str:
        if old_value.strip() == "[[Enemies|Boss]]":
            return old_value  # Preserve manual Boss classification
        return new_value

# Registry of built-in handlers
BUILTIN_HANDLERS = {
    "override": OverrideHandler(),
    "preserve_if_blank": PreserveIfBlankHandler(),
    "merge_sources": MergeSourcesHandler(),
    "preserve_boss_type": PreserveBossTypeHandler(),
}
```

### Simple Handler Resolver

```python
# src/erenshor/application/services/field_resolver.py

class FieldResolver:
    """Resolve field values using configured handlers."""

    def __init__(self, config: dict):
        self.config = config
        self.handlers = BUILTIN_HANDLERS.copy()

    def resolve(
        self,
        template_type: str,  # "item", "enemy", etc.
        field_name: str,
        old_value: str,
        new_value: str,
        context: dict,
    ) -> str:
        """Resolve field value.

        Args:
            template_type: Type of template (item, enemy, etc.)
            field_name: Field name (othersource, imagecaption, etc.)
            old_value: Value from existing page
            new_value: Value from generated content
            context: Additional context

        Returns:
            Resolved value
        """
        # Get handler for this template.field
        handler_name = self._get_handler_name(template_type, field_name)
        handler = self.handlers.get(handler_name, self.handlers["override"])

        # Apply handler
        return handler.handle(old_value, new_value, context)

    def _get_handler_name(self, template_type: str, field_name: str) -> str:
        """Get handler name from config.

        Args:
            template_type: Template type (item, enemy, etc.)
            field_name: Field name

        Returns:
            Handler name (default: "override")
        """
        # Check template-specific config
        template_config = self.config.get("wiki", {}).get("field_preservation", {}).get(template_type, {})

        if field_name in template_config:
            return template_config[field_name]

        # Default to override
        return "override"
```

### Usage Example

```python
# In content merger

class ContentMerger:
    def __init__(self, config: dict):
        self.resolver = FieldResolver(config)

    def merge(
        self,
        template_type: str,  # "item" or "enemy"
        original: str,
        generated: str,
    ) -> str:
        """Merge templates."""

        # Parse both templates
        old_template = self._parse_template(original)
        new_template = self._parse_template(generated)

        # Merge fields
        merged = new_template.copy()

        for field_name in old_template.keys():
            old_value = old_template[field_name]
            new_value = new_template.get(field_name, "")

            # Resolve using configured handler
            resolved = self.resolver.resolve(
                template_type=template_type,
                field_name=field_name,
                old_value=old_value,
                new_value=new_value,
                context={"template": template_type},
            )

            merged[field_name] = resolved

        return self._render_template(merged)
```

### Adding Custom Handlers (Future)

Users can add custom handlers later:

```python
# Custom handler in user code
class MyCustomHandler:
    def handle(self, old_value: str, new_value: str, context: dict) -> str:
        # Custom logic
        return custom_value

# Register handler
BUILTIN_HANDLERS["my_custom"] = MyCustomHandler()
```

```toml
# Use in config
[wiki.field_preservation.item]
my_field = "my_custom"
```

### Why This Is Simple

1. **No modes** - just handlers
2. **Default is obvious** - override (do nothing)
3. **Preserve is just a handler** - not a special case
4. **Template-specific via config** - not code
5. **4 handlers cover all current needs** - override, preserve_if_blank, merge_sources, preserve_boss_type
6. **Easy to extend** - add handler, register, use in config

---

## Issue 5: Manual Edit Notification UX/DX

### Current Workflow Problems

From user feedback:
> "Pull commands are easy to forget vs push (automatic output)"
> "As more auto-pushed output, easier to overlook things"
> "Long sections make things get lost"
> "How to ensure discoverability without overload?"

**Bad UX Pattern** (don't do this):
```bash
$ erenshor wiki update
[info] Update complete

$ erenshor wiki check-manual-edits  # User must remember this!
3 pages have manual edits
```

**Good UX Pattern** (do this):
```bash
$ erenshor wiki update
[info] Update complete

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ ⚠ Manual Edits Detected (3 pages)    ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
  Iron Sword: field 'othersource' by WikiUser123
  Health Potion: field 'imagecaption' by Editor456

Review: .erenshor/wiki/manual-edits.txt
```

### Improved Design

**Principle**: **Push, don't pull** - show important info automatically.

**Visual Hierarchy**: Use Rich to prevent information overload.

#### Output Formatting Strategy

**1. Summary at End** (most important)
```bash
$ erenshor wiki update

[... command output ...]

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃                  Update Summary                  ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

Pages generated: 247
Pages with manual edits: 3 ⚠
  → Review: .erenshor/wiki/manual-edits.txt

Next steps:
  1. Review manual edits (if any)
  2. Review merged pages: .erenshor/wiki/merged/
  3. Push to wiki: erenshor wiki push
```

**2. Inline Warnings** (during processing)
```bash
$ erenshor wiki update

Generating pages...
  ✓ Items: 156 pages
  ✓ Characters: 89 pages
  ✓ Abilities: 45 pages

Checking for manual edits...
  ⚠ Found 3 pages with recent edits by users
    (Details in summary below)

Merging content...
  ✓ Merged: 244 pages
  ⚠ Manual edits preserved: 3 pages

[... summary at end ...]
```

**3. Importance Levels** (color coding)
```
✓ Green: Success, no action needed
ℹ Blue: Info, FYI only
⚠ Yellow: Warning, review recommended
✗ Red: Error, action required
```

#### Visual Design with Rich

```python
# In wiki update command

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress

console = Console()

def show_manual_edits_section(manual_edits: list[ManualEdit]):
    """Show manual edits in visually distinct section."""

    if not manual_edits:
        return  # Don't show section if no edits

    # Create table
    table = Table(
        title=f"⚠ Manual Edits Detected ({len(manual_edits)} pages)",
        show_header=True,
        header_style="bold yellow",
    )
    table.add_column("Page", style="cyan")
    table.add_column("Field", style="white")
    table.add_column("Edited By", style="green")
    table.add_column("Date", style="dim")

    # Add rows (limit to first 5, with "..." if more)
    for edit in manual_edits[:5]:
        table.add_row(
            edit.page_title,
            edit.field,
            edit.edited_by,
            edit.date.strftime("%Y-%m-%d"),
        )

    if len(manual_edits) > 5:
        table.add_row("...", f"+{len(manual_edits) - 5} more", "...", "...")

    console.print(table)
    console.print()
    console.print(f"[dim]Full list: .erenshor/wiki/manual-edits.txt[/dim]")
    console.print()

def show_update_summary(stats: UpdateStats):
    """Show summary at end with all important info."""

    # Create summary panel
    summary = f"""
[bold]Pages generated:[/bold] {stats.generated_count}
[bold]Pages merged:[/bold] {stats.merged_count}
[bold]Pages with manual edits:[/bold] {stats.manual_edit_count}

[bold]Output locations:[/bold]
  Generated: .erenshor/wiki/generated/
  Merged: .erenshor/wiki/merged/
  Manual edits: .erenshor/wiki/manual-edits.txt
"""

    console.print(Panel(
        summary,
        title="Update Summary",
        border_style="green" if stats.manual_edit_count == 0 else "yellow",
    ))

    # Next steps
    if stats.manual_edit_count > 0:
        console.print("\n[bold yellow]Next steps:[/bold yellow]")
        console.print("  1. Review manual edits in .erenshor/wiki/manual-edits.txt")
        console.print("  2. Review merged pages in .erenshor/wiki/merged/")
        console.print("  3. Push to wiki: [cyan]erenshor wiki push[/cyan]")
    else:
        console.print("\n[bold green]Next steps:[/bold green]")
        console.print("  1. Review merged pages in .erenshor/wiki/merged/")
        console.print("  2. Push to wiki: [cyan]erenshor wiki push[/cyan]")
```

#### Manual Edit Report File

**File**: `.erenshor/wiki/manual-edits.txt`

```
Manual Edits Report
Generated: 2025-10-17 15:30:00
Variant: main

3 pages have manual edits since last update:

1. Iron Sword
   Field: othersource
   Current value: [[Mining]]
   Manual edit: "Found in secret chest near spawn"
   Edited by: WikiUser123 on 2025-10-15 14:30:00
   Comment: "Added missing location info"

   Merged result: [[Mining]]<br>Found in secret chest near spawn
   Status: Automatically merged (both values preserved)

2. Health Potion
   Field: imagecaption
   Current value: (blank)
   Manual edit: "A red potion that restores health"
   Edited by: Editor456 on 2025-10-16 10:15:00
   Comment: "Added caption"

   Merged result: A red potion that restores health
   Status: Automatically preserved (generated value was blank)

3. Magic Amulet
   Field: type
   Current value: Consumable
   Manual edit: Legendary Artifact
   Edited by: Contributor789 on 2025-10-14 09:00:00
   Comment: (no comment)

   Merged result: Legendary Artifact
   Status: Needs review - significant difference from generated value

---

Action required:
- Review item 3 (Magic Amulet) - manual type differs from generated
- All other edits automatically handled
```

### Discoverability Patterns

**1. Progressive Disclosure**
- Summary first (high-level)
- Details in file (drill-down)
- Full data in JSON (programmatic access)

**2. Visual Hierarchy**
- Most important: Panels with borders
- Important: Tables with headers
- Less important: Plain text
- Least important: Dim/gray text

**3. Actionable Next Steps**
- Always show what to do next
- Use concrete commands (copy-paste ready)
- Prioritize by importance

**4. Contextual Help**
- Hints inline (where relevant)
- File paths shown (easy to access)
- Commands shown (easy to run)

### Implementation

```python
# In wiki update command

def wiki_update_command(variant: str):
    """Update wiki pages with generated content."""
    console = Console()

    # Step 1: Generate
    with console.status("Generating wiki pages..."):
        generated = generate_all_pages(variant)
    console.print("✓ Generated pages", style="green")

    # Step 2: Check manual edits (AUTOMATIC)
    with console.status("Checking for manual edits..."):
        manual_edits = detect_manual_edits(generated)

    if manual_edits:
        console.print(f"⚠ Found {len(manual_edits)} pages with manual edits", style="yellow")
    else:
        console.print("✓ No manual edits detected", style="green")

    # Step 3: Merge
    with console.status("Merging content..."):
        merged = merge_all_pages(generated, manual_edits)
    console.print("✓ Merged pages", style="green")

    # Step 4: Save
    save_merged_pages(merged)
    save_manual_edits_report(manual_edits)

    # Step 5: Show summary (AUTOMATIC PUSH)
    console.print()
    if manual_edits:
        show_manual_edits_section(manual_edits)

    show_update_summary(UpdateStats(
        generated_count=len(generated),
        merged_count=len(merged),
        manual_edit_count=len(manual_edits),
    ))
```

### Why This Is Better

**Old way** (pull):
```bash
# User must remember to check
erenshor wiki update
erenshor wiki check-edits  # Easy to forget!
```

**New way** (push):
```bash
# Everything shown automatically
erenshor wiki update
# ⚠ Shows manual edits in output
# → Shows file path
# → Shows next steps
```

**Benefits**:
- ✅ Can't miss important info (shown automatically)
- ✅ Visual hierarchy (important stands out)
- ✅ No new commands (fewer things to remember)
- ✅ Actionable (shows what to do next)
- ✅ Detailed report available (for drill-down)

---

## Final Recommendations

### Core Principles Validated

1. ✅ **Simple** - Removed 90% of complexity from v2
2. ✅ **Structural Enforcement** - Decorators make it hard to misuse
3. ✅ **Good UX/DX** - Push-style notifications, visual hierarchy
4. ✅ **No Feature Creep** - Only what's actually needed

### Implementation Priority

**Phase 1: Foundation** (Week 1)
1. Category tag generation (1 hour)
2. Precondition decorator system (3 hours)
3. Legacy template remover (2 hours)

**Phase 2: Field Preservation** (Week 2)
4. Minimal field handler system (2 hours)
5. Template-specific configuration (1 hour)
6. Built-in handlers (preserve, merge, boss type) (2 hours)

**Phase 3: UX/DX** (Week 3)
7. Manual edit detection (3 hours)
8. Rich output formatting (2 hours)
9. Manual edit report generation (1 hour)

**Total**: ~17 hours (vs ~40+ hours in v2)

### Success Criteria

1. ✅ Categories can vary per item (multi-category support)
2. ✅ Precondition checks can't be forgotten (decorator enforcement)
3. ✅ All legacy templates replaced (complete mapping)
4. ✅ Field preservation is simple (4 handlers, not 10 modes)
5. ✅ Manual edits discoverable (automatic output)

## Ready for Updated Plan

### Clear Requirements

All ambiguity removed:
- ✅ Category tags: Manual, not template-based
- ✅ Preconditions: Per-command with decorators
- ✅ Legacy templates: Complete list (10 replacements)
- ✅ Field preservation: Default=override + custom handlers
- ✅ Manual edit UX: Push-style in existing output

### Simplified Design

No unnecessary complexity:
- ✅ 4 field handlers (not 10 modes)
- ✅ Decorators (not manual checks)
- ✅ Automatic output (not new commands)
- ✅ Config-driven (not code-driven)

### Good Patterns

Scalable and maintainable:
- ✅ Decorator pattern (structural enforcement)
- ✅ Handler registry (easy extension)
- ✅ Visual hierarchy (good UX)
- ✅ Progressive disclosure (prevent overload)

## Next Steps

1. **User Approval**
   - Review this v3 analysis
   - Confirm all decisions
   - Approve for implementation

2. **Update Phase 3 Plan**
   - Simplify task descriptions
   - Update estimates (much lower now)
   - Remove unnecessary features from v2

3. **Begin Implementation**
   - Start with category tags (easiest)
   - Move to preconditions (structural)
   - Finish with UX (polish)

---

**End of Analysis v3 (Final)**
