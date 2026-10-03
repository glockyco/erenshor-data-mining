---
name: cli-commands
description: Add or change an erenshor Typer command. Use when editing command groups, options, dry-run behavior, or preconditions in src/erenshor/cli/.
---

# CLI commands

1. Inspect a nearby command in `src/erenshor/cli/commands/`.
   Put related actions under its existing Typer app.
   Create another group only when the action does not fit an existing group.
2. For a new group, export `app = typer.Typer(...)` from its command module.
   Import and register it with `app.add_typer(..., name="group")` in `src/erenshor/cli/main.py`.
3. Accept `ctx: typer.Context` in commands that need configuration.
   Read `ctx.obj` as `CLIContext`.
   Select the variant through the root `-V` option, not a second command option.
   Resolve paths through `cli_ctx.config.variants[cli_ctx.variant]` and `cli_ctx.repo_root`.
4. Use the root `--dry-run` option before the group.
   In actions that support preview, read `cli_ctx.dry_run` and prevent writes.
   Do not add another dry-run option.
5. Declare required inputs with `@require_preconditions(...)` immediately below `@app.command(...)`.
   Reuse checks from `src/erenshor/cli/preconditions/checks/`.
   For a new kind of input, add a check.
   Expose missing values through `_build_check_context` in `src/erenshor/cli/preconditions/decorator.py`.
   The decorator also passes command arguments to checks.
6. Run `uv run erenshor <group> --help` and `uv run erenshor <group> <action> --help`.
   Inspect the actual interface and exercise the changed path with harmless inputs or dry run.

Put checks before any side effect when a command writes files, publishes data,
changes an installation, or starts a process.
Do not duplicate a precondition in the command body or declare an empty check list.
Commands that only read state need no declaration.
The decorator runs every declared check, reports each failure, and aborts before the handler.
`eval reset` and `eval watch` change remote state without local input dependencies.
The `test` group uses its own task-graph preflight.
