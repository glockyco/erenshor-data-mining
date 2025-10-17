# Erenshor Refactoring Project - Security and Best Practices Review

**Date**: 2025-10-17
**Review Scope**: Tasks 1-13 (Phase 1 Foundation)
**Reviewer**: Security and DevOps Expert

---

## Executive Summary

**Overall Risk Level: LOW-MEDIUM**

The Erenshor project demonstrates good security practices overall, with proper secrets management, input validation, and safe coding patterns. However, there are a few important findings that should be addressed immediately, particularly around credential management and file permissions.

---

## 1. Security Risk Assessment

### Risk Level: **LOW-MEDIUM**

**Rationale:**
- No critical vulnerabilities found in code
- Credentials are properly managed (not in version control)
- Input validation is robust using Pydantic
- No dangerous code patterns (eval, exec, SQL injection)
- Some operational risks exist (spreadsheet ID exposure, lack of .erenshor in gitignore)

---

## 2. Critical Security Issues

### 🔴 CRITICAL: Real Credentials in .env File

**File:** `.env:78-83`

```env
ERENSHOR_BOT_USERNAME=WoWBot@erenshor-wiki
ERENSHOR_BOT_PASSWORD=juhp4u91387rq5ijc6jnkll6h2lfsmnn
```

**Issue:** The `.env` file contains REAL MediaWiki bot credentials (username and password).

**Verification:**
- ✅ Good: `.env` is properly gitignored (line 263 in `.gitignore`)
- ✅ Good: No commits found in git history for `.env` file
- ❌ Risk: File exists in working directory with real credentials

**Remediation:**
1. **IMMEDIATE:** Revoke the bot password at MediaWiki's Special:BotPasswords page
2. Create a new bot password
3. Update `.env` with new credentials
4. Consider using `.env.example` as the template (which already exists with placeholder credentials)
5. Add a note to README about rotating credentials if `.env` is accidentally committed

---

### 🟡 MEDIUM: .erenshor Directory Not Explicitly Gitignored

**File:** `.gitignore` (missing entry)

**Issue:** The `.erenshor/` directory contains sensitive state and local config but is not explicitly listed in `.gitignore`. While `config.local.toml` is ignored, the directory itself should be too.

**Current directory contents:**
```
.erenshor/
├── config.local.toml (may contain credentials)
├── state.json (pipeline state)
└── logs/ (may contain sensitive data in logs)
```

**Remediation:**
Add to `.gitignore`:
```gitignore
# Erenshor state directory (contains local config and secrets)
.erenshor/
```

**Note:** The specific file `config.local.toml` is already ignored (line 819), but the directory should be too for defense-in-depth.

---

## 3. Secrets Management Assessment

### ✅ **GOOD: Credentials Properly Externalized**

**Strengths:**
1. **MediaWiki Credentials:** Stored in `.env` (gitignored) or environment variables
   - File: `config.toml:38-39` - Default values are empty strings
   - Documentation: `.env.example:82-93` - Clear instructions for users

2. **Google Sheets Credentials:** JSON file stored outside repository
   - Path: `$HOME/.config/erenshor/google-credentials.json`
   - File: `config.toml:42` - Path resolution with validation
   - Validation available via `resolved_credentials_file()` method

3. **Steam Credentials:** Environment variable only
   - File: `config.toml:14` - Empty default, loaded from `ERENSHOR_STEAM_USERNAME`
   - File: `.env.example:23-24` - Instructions provided

### ✅ **GOOD: No Hardcoded Secrets in Code**

Verified no hardcoded credentials in:
- Python source files (`src/erenshor/`)
- Configuration schemas
- Test files (only mock/placeholder values like "secret123")

### 🟡 **MEDIUM: Spreadsheet ID Exposure**

**File:** `config.toml:68`
```toml
spreadsheet_id = "1eOYfjaudAhvE6HGBtWyRGgQDsmWDLENaoEwRvgBO_0E"
```

**Issue:** Google Sheets spreadsheet ID is committed to version control.

**Risk Assessment:**
- **Low-Medium Risk:** Spreadsheet IDs are not secrets per se, but they reveal:
  - That this spreadsheet exists
  - Could be used for enumeration attacks
  - Public spreadsheets can be accessed if share settings are misconfigured

**Recommendation:**
- **Option 1 (Current approach is OK):** Keep in `config.toml` if spreadsheet has proper access controls via service account
- **Option 2 (More secure):** Move to `config.local.toml` for private deployments
- **Option 3 (Compromise):** Add a comment explaining that the spreadsheet is access-controlled

---

## 4. Input Validation Assessment

### ✅ **EXCELLENT: Comprehensive Pydantic Validation**

**File:** `src/erenshor/infrastructure/config/schema.py`

**Strengths:**
1. **Type Safety:** All config fields have proper types
2. **Constraints:** Numeric values have ranges (ge/le validators)
   - Unity timeout: 60-7200 seconds (line 93-95)
   - AssetRipper port: 1024-65535 (line 128-130)
   - API batch size: 1-50 (line 182-184)
   - Retry counts: 0-10 (line 240-242)

3. **Enum Validation:** Limited choices for critical fields
   - Platform: `"windows" | "macos" | "linux"` (line 71)
   - Log level: `"debug" | "info" | "warn" | "error"` (line 297-299)

4. **Path Validation:** Optional validation that paths exist
   - File: `src/erenshor/infrastructure/config/paths.py:26-90`
   - Validates paths exist before use when `validate=True`

### ✅ **GOOD: Path Traversal Protection**

**File:** `src/erenshor/infrastructure/config/paths.py:26-90`

**Strengths:**
1. Uses `pathlib.Path` throughout (safer than string manipulation)
2. Variable expansion is safe (only `$REPO_ROOT`, `$HOME`, `~`)
3. All paths are resolved to absolute paths
4. Repository root is found via `.git` directory (secure anchor point)

**No vulnerabilities found:**
- No user-controlled path input without validation
- No path concatenation with user input
- No `../` path traversal risks

---

## 5. Logging Security Assessment

### ✅ **GOOD: No Credential Logging**

**Files Reviewed:**
- `src/erenshor/infrastructure/logging/utils.py`
- `src/erenshor/infrastructure/logging/setup.py`

**Strengths:**
1. Logging utilities do NOT log function arguments by default
   - `log_function()` decorator: `log_args=False` by default (line 269)
   - Context logging is explicit, not automatic

2. Error logging shows exception type and message, but:
   - No automatic credential extraction
   - Traceback is optional (`show_traceback` parameter)

3. No evidence of credentials in log messages
   - Searched for password/credential logging patterns
   - No dangerous logging found

### 🟡 **MEDIUM: Log Files Might Contain Sensitive Data**

**File:** `src/erenshor/infrastructure/logging/setup.py:129-148`

**Configuration:**
- Log retention: 7 days
- Log rotation: 10 MB
- Compression: gzip
- Location: `variants/{variant}/logs/` or `.erenshor/logs/`

**Potential Issues:**
1. If URLs or API responses are logged, they might contain tokens
2. Debug logging might expose internal paths
3. Log files are world-readable (default umask)

**Recommendations:**
1. ✅ Already using `enqueue=True` for thread-safe logging (line 141)
2. Add log file permission check (chmod 600 for log files)
3. Consider sanitizing sensitive data from log context before logging
4. Add note in documentation about log security

---

## 6. Dependency Security Assessment

### ✅ **GOOD: Modern, Well-Maintained Dependencies**

**File:** `pyproject.toml:26-51`

**Key Dependencies:**
- **Pillow 11.3.0** - Latest version, no known CVEs
- **httpx >= 0.27.0** - Modern HTTP client (safer than requests)
- **pydantic >= 2.0.0** - Type-safe validation
- **sqlalchemy >= 2.0.41** - Modern ORM with security updates
- **google-auth >= 2.0.0** - Official Google library
- **loguru >= 0.7.0** - Structured logging

### ✅ **GOOD: Version Constraints**

**Strengths:**
1. **Minimum versions specified:** Ensures security patches (>= operator)
2. **Python 3.13 requirement:** Latest Python with security improvements
3. **No wildcard dependencies:** All deps have version constraints

**No Known Vulnerabilities:**
- Checked installed version: `pillow 11.3.0` (current, no CVEs)
- All dependencies use semantic versioning
- Lock file (`uv.lock`) ensures reproducible builds

### 🟢 **LOW RISK: Supply Chain**

**Mitigations in place:**
- Using `uv` for deterministic dependency resolution
- Lock file committed to version control
- No untrusted package sources

---

## 7. Configuration Security Assessment

### ✅ **EXCELLENT: Two-Layer Configuration System**

**File:** `src/erenshor/infrastructure/config/loader.py:125-217`

**Strengths:**
1. **Secure defaults in `config.toml`** - No credentials, safe paths
2. **Local overrides in `config.local.toml`** - Gitignored, for secrets
3. **Deep merge strategy** - Local values override base values
4. **Validation on load** - Pydantic validates merged config

**Security Properties:**
- Base config is in version control (auditable)
- Secrets are in local config (not in git)
- Invalid configs fail fast with clear errors
- No legacy/fallback paths that could hide misconfigurations

### ✅ **GOOD: HTTPS Enforcement**

**File:** `config.toml:31`
```toml
api_url = "https://erenshor.wiki.gg/api.php"
```

**Good practices:**
- MediaWiki API uses HTTPS
- No HTTP URLs in config
- Google Sheets API uses HTTPS by default

---

## 8. Operational Risks Assessment

### 🟡 **MEDIUM: No Log Rotation Disk Space Protection**

**File:** `src/erenshor/infrastructure/logging/setup.py:136-137`

**Current settings:**
- Rotation: 10 MB per file
- Retention: 7 days
- Compression: gzip

**Risk:**
- If logs rotate faster than 7 days, disk could fill up
- No total size limit across all log files
- Variant logs + global logs could accumulate

**Recommendations:**
1. Add disk space check before operations
2. Consider max total log size (e.g., 100 MB total)
3. Add monitoring/alerts for disk usage
4. Document log management in README

### 🟢 **LOW RISK: File Permissions**

**Directory permissions:** (from ls -la output)
```
drwxr-xr-x  .erenshor/
-rw-r--r--  config.local.toml
-rw-r--r--  state.json
```

**Assessment:**
- Directories: 755 (readable by all users)
- Files: 644 (readable by all users)

**Recommendation:**
- Consider `chmod 700 .erenshor/` (owner-only)
- Consider `chmod 600 .erenshor/config.local.toml` (owner-only read/write)
- Add setup script to set proper permissions

### ✅ **GOOD: Resource Limits**

**Files:**
- Unity timeout: 3600s max (config.toml:20)
- AssetRipper timeout: 3600s max (config.toml:25)
- Retry limits: 0-10 max (config.toml:48, 240-242)

**No resource exhaustion risks found.**

---

## 9. Code Quality from Security Perspective

### ✅ **EXCELLENT: No Dangerous Code Patterns**

**Verified absence of:**
- ❌ `eval()` - Not found
- ❌ `exec()` - Not found
- ❌ `__import__()` - Not found
- ❌ `compile()` - Not found
- ❌ Dynamic SQL (f-strings in queries) - Not found
- ❌ `os.system()` - Not found
- ❌ `subprocess` with `shell=True` - Not found

### ✅ **GOOD: Safe Practices**

1. **Path Operations:** Uses `pathlib.Path` everywhere (safer than os.path)
2. **SQL Queries:** All queries in `.sql` files (no dynamic SQL)
3. **HTTP Client:** Uses `httpx` (modern, secure)
4. **Type Safety:** Full type hints with mypy strict mode

---

## 10. Recommendations (Prioritized)

### 🔴 **CRITICAL (Immediate Action)**

1. **Rotate MediaWiki Bot Credentials**
   - File: `.env:78-83`
   - Action: Revoke bot password `juhp4u91387rq5ijc6jnkll6h2lfsmnn`
   - Timeline: **Immediate**
   - Reason: Real credentials exposed in working directory

### 🟠 **HIGH (Within 1 Week)**

2. **Add .erenshor/ to .gitignore**
   - File: `.gitignore`
   - Action: Add entry `.erenshor/` with comment
   - Reason: Defense-in-depth for secrets protection

3. **Set Restrictive File Permissions**
   - Files: `.erenshor/config.local.toml`, `.env`
   - Action: `chmod 600` for sensitive files, `chmod 700` for `.erenshor/`
   - Reason: Prevent local user access to credentials

4. **Add Security Documentation**
   - File: `README.md` or `SECURITY.md`
   - Action: Document:
     - How to rotate credentials
     - What to do if credentials are leaked
     - Proper file permissions
     - Log security considerations

### 🟡 **MEDIUM (Within 1 Month)**

5. **Consider Moving Spreadsheet ID**
   - File: `config.toml:68`
   - Action: Move to `config.local.toml` or add security comment
   - Reason: Reduce information disclosure

6. **Add Log File Permissions**
   - File: `src/erenshor/infrastructure/logging/setup.py:132`
   - Action: Set file permissions to 600 when creating logs
   - Code:
     ```python
     import os
     # After log_file creation:
     os.chmod(str(log_file), 0o600)
     ```

7. **Implement Disk Space Checks**
   - Files: Pipeline orchestration scripts
   - Action: Check available disk space before exports
   - Reason: Prevent disk exhaustion from logs/databases

8. **Add Credential Sanitization Filter**
   - File: `src/erenshor/infrastructure/logging/utils.py`
   - Action: Add filter to sanitize passwords/tokens from log context
   - Example:
     ```python
     def sanitize_context(context: dict) -> dict:
         """Remove sensitive keys from log context."""
         sensitive = {'password', 'token', 'credential', 'secret', 'api_key'}
         return {k: '***' if k in sensitive else v for k, v in context.items()}
     ```

### 🟢 **LOW (Nice to Have)**

9. **Add Pre-commit Hook for Secrets**
   - File: `.pre-commit-config.yaml:1`
   - Action: Add `detect-secrets` or `gitleaks` hook
   - Reason: Prevent accidental credential commits

10. **Add Security.md**
    - File: `SECURITY.md` (new)
    - Action: Create security policy with:
      - Vulnerability reporting process
      - Supported versions
      - Security best practices

11. **Consider Secrets Manager**
    - For production deployments
    - Use environment-specific secrets management (1Password, AWS Secrets Manager, etc.)
    - Reason: Better than filesystem-based secrets

---

## Summary

The Erenshor project demonstrates **strong security fundamentals** with proper separation of secrets, robust input validation, and safe coding practices. The main concerns are:

1. **Credential management** - Real credentials in `.env` need to be rotated immediately
2. **File permissions** - Sensitive files should have restrictive permissions
3. **Operational security** - Log management and disk space monitoring

**The project is production-ready from a security perspective** after addressing the critical item (credential rotation).

### Key Strengths
- ✅ No hardcoded secrets in code
- ✅ Proper use of Pydantic for validation
- ✅ No dangerous code patterns (eval, SQL injection, etc.)
- ✅ Modern, secure dependencies
- ✅ HTTPS for all external APIs
- ✅ Safe path handling with pathlib

### Key Improvements Needed
- 🔴 Rotate exposed credentials immediately
- 🟠 Add `.erenshor/` to `.gitignore`
- 🟠 Set restrictive file permissions (600/700)
- 🟡 Add security documentation

---

**Review Date**: 2025-10-17
**Reviewer**: Security and DevOps Expert
**Status**: ⚠️ **Address Critical Items Before Production**
