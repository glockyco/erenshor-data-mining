---
name: code-review
description: Review code for quality and adherence to project standards. Use when reviewing PRs, checking code quality, or validating changes before commit.
---

# Code Review Checklist

Review code against the project's quality principles.

## 1. Validate Every Claim

- [ ] No assumptions made without checking actual code
- [ ] Claims about "not used" verified by searching entire codebase
- [ ] Implementation details verified by reading the files

## 2. Fail Fast

- [ ] No silent fallbacks that hide errors
- [ ] Errors fail immediately with clear messages
- [ ] No try/except that swallows exceptions silently

## 3. No Backward Compatibility

- [ ] Clean breaks, no legacy code paths
- [ ] No "just in case" fallback behavior
- [ ] Migration code removed after migration

## 4. Keep It Simple

- [ ] No unnecessary config options or flags
- [ ] No features beyond what was requested
- [ ] Minimal abstraction (prefer duplication over wrong abstraction)

## 5. Clean Cuts Only

- [ ] Old code fully removed when refactoring
- [ ] No commented-out code
- [ ] No unused imports or variables

## 6. Minimal Comments

- [ ] No comments explaining obvious code
- [ ] Comments explain "why", not "what"
- [ ] No development history in comments

## 7. Atomic Commits

- [ ] One concept per commit
- [ ] Conventional commit format
- [ ] Prose description, not bullet lists

## 8. Fix All Errors

- [ ] No ignored errors or warnings
- [ ] Bugs found during review are fixed
- [ ] Type errors resolved

## Additional Checks

**Security**:
- [ ] No hardcoded secrets or tokens
- [ ] Input validation at system boundaries
- [ ] No SQL injection vulnerabilities

**Python-specific**:
- [ ] Type hints on all functions
- [ ] Passes `uv run ruff check src/ tests/`
- [ ] Passes `uv run ruff format --check src/ tests/`
- [ ] Passes `uv run mypy` (strict mode with CLI exemptions)
- [ ] Python 3.13+ compatible syntax

**Project-specific**:
- [ ] Only modifies `src/Assets/Editor/` or `src/erenshor/`
- [ ] Works with Unity 2021.3.45f2
- [ ] Tested across variants if applicable
