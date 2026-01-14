# Check-In Command

**SEMI-AUTONOMOUS** - Perform security audit, code audit, and git commit preparation for GitHub.

## Usage

```
/check-in [--no-push]
```

## Examples

```
/check-in
/check-in --no-push
```

## Instructions

When this command is invoked: $ARGUMENTS

This command prepares code for GitHub check-in with comprehensive audits.

---

## WORKFLOW

### Step 1: Security Audit (BLOCKING)

**This step MUST pass before any commit can proceed.**

#### 1.1 Credentials Check

Search for exposed credentials in tracked files:

```bash
cd "D:\music cleanup"
```

**Patterns to detect** (use Grep tool):

| Pattern | Description |
|---------|-------------|
| `api[_-]?key\s*[=:]` | API key assignments |
| `password\s*[=:]` | Password assignments |
| `secret\s*[=:]` | Secret assignments |
| `token\s*[=:]` | Token assignments |
| `sk-[a-zA-Z0-9]{20,}` | OpenAI API keys |
| `ghp_[a-zA-Z0-9]{36}` | GitHub PAT tokens |
| `xoxb-` | Slack tokens |
| `AKIA[A-Z0-9]{16}` | AWS access keys |

**Files to scan**: `*.py`, `*.yaml`, `*.json`, `*.md`, `*.sh`, `*.ps1`

**Exclude from scan**:
- `credentials.yaml` (should be gitignored)
- `.env` files
- Files matching `.gitignore` patterns

#### 1.2 Sensitive Paths Check

Search for hardcoded local/network paths:

| Pattern | Description |
|---------|-------------|
| `//openmediavault/` | NAS paths |
| `C:\\Users\\` or `C:/Users/` | Windows user paths |
| `/home/[username]/` | Linux home paths |
| `/Users/[username]/` | macOS home paths |

**Allowed exceptions**:
- Paths in `music-config.yaml` (configuration file)
- Paths in documentation as examples
- Paths in `.gitignore`

#### 1.3 Security Verdict

```
=== SECURITY AUDIT ===
[PASS/FAIL] Credentials check: N issues found
[PASS/FAIL] Sensitive paths check: N issues found
```

**If ANY security issue found:**
1. Report all issues with file:line references
2. **STOP** - Do not proceed to cleanup or commit
3. Instruct user to fix issues before re-running

---

### Step 2: Cleanup (AUTO-DELETE)

**Automatically delete temp files before commit.**

#### 2.1 Delete Temp Files

Execute the following cleanup commands:

```bash
cd "D:\music cleanup"

# Delete Claude temp files
rm -f tmpclaude-*-cwd

# Delete Python cache
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete 2>/dev/null
find . -type f -name "*.pyo" -delete 2>/dev/null

# Clear temp folder contents (but keep folder)
rm -f temp/* 2>/dev/null

# Delete backup/temp files
find . -type f -name "*.tmp" -delete 2>/dev/null
find . -type f -name "*.bak" -delete 2>/dev/null
```

#### 2.2 Report Cleanup

```
=== CLEANUP ===
[DELETED] N tmpclaude-* files
[DELETED] N __pycache__ directories
[DELETED] N .pyc/.pyo files
[DELETED] N temp files
```

---

### Step 3: Code Audit (WARNING ONLY)

**This step reports issues but does NOT block commits.**

Check for files that shouldn't be committed:

| Location | Check |
|----------|-------|
| `scripts/completed/` | Archive folder - should not grow |
| `outputs/*.json` | Generated reports - gitignored |
| `outputs/*.csv` | Generated reports - gitignored |
| `state/` | Session state - gitignored |
| `logs/` | Log files - gitignored |

#### 3.2 Code Quality Check

Search for common issues:

| Pattern | Description | Severity |
|---------|-------------|----------|
| `print\(` in `.py` files | Debug prints (except cli.py, utilities/) | INFO |
| `# TODO` | Unfinished work | INFO |
| `# FIXME` | Known issues | WARN |
| `# HACK` | Workarounds | WARN |
| `import pdb` | Debugger imports | WARN |
| `breakpoint()` | Debug breakpoints | WARN |

#### 3.3 Documentation Sync Check

1. Run `python cli.py --help` and compare commands to README.md
2. Check `CLAUDE.md` last updated date
3. Verify all slash commands in `.claude/commands/` are documented

#### 3.4 Code Audit Report

```
=== CODE AUDIT ===
[WARN] Orphaned files: N files in archive folders
[INFO] Code quality: N issues (TODOs, prints, etc.)
[INFO] Documentation: In sync / Needs update
```

---

### Step 4: Git Operations

#### 4.1 Check Git Status

```bash
git status
```

Report:
- Modified files
- Added files
- Deleted files
- Untracked files

#### 4.2 Review Changes

```bash
git diff --staged
git diff
```

Analyze the changes to understand:
- What features/fixes were added
- What files were modified
- The nature of the changes

#### 4.3 Auto-Generate Commit Message

Based on the changes, generate a commit message following this format:

```
<type>(<scope>): <summary>

<body - what changed and why>

Co-Authored-By: Claude <noreply@anthropic.com>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `refactor`: Code refactoring
- `style`: Formatting, missing semicolons, etc.
- `test`: Adding tests
- `chore`: Maintenance tasks

**Example:**
```
feat(commands): add /check-in command for GitHub preparation

- Security audit checks for credentials and sensitive paths
- Code audit warns about temp files and orphaned content
- Auto-generates commit messages from staged changes
- Blocks commits only on security issues

Co-Authored-By: Claude <noreply@anthropic.com>
```

#### 4.4 Stage and Commit

1. Show the generated commit message
2. Use AskUserQuestion to confirm:
   - "Proceed with this commit message?"
   - Options: Yes / Edit message / Cancel

3. If confirmed, execute:
```bash
git add -A
git commit -m "<message>"
```

#### 4.5 Push (Optional)

If `--no-push` flag was NOT provided:

1. Use AskUserQuestion:
   - "Push to remote repository?"
   - Options: Yes / No

2. If yes:
```bash
git push
```

---

## Autonomous Behavior Summary

| Action | Autonomous |
|--------|------------|
| Run security scan | YES |
| Delete temp files | YES (auto-cleanup) |
| Run code audit | YES |
| Block on security issues | YES (automatic) |
| Show audit reports | YES |
| Generate commit message | YES |
| Stage files | ASK |
| Execute commit | ASK |
| Push to remote | ASK |

---

## Output Format

```
╔══════════════════════════════════════════════════════════════╗
║                    /check-in AUDIT REPORT                     ║
╚══════════════════════════════════════════════════════════════╝

=== SECURITY AUDIT ===
[PASS] Credentials check: No secrets found
[PASS] Sensitive paths check: No hardcoded paths

=== CLEANUP ===
[DELETED] 3 tmpclaude-* files
[DELETED] 2 __pycache__ directories
[DELETED] 0 .pyc/.pyo files
[DELETED] 1 temp file

=== CODE AUDIT ===
[INFO] Orphaned files: 0 files
[INFO] Code quality: 3 TODOs found
[INFO] Documentation: In sync

=== GIT STATUS ===
Modified:  5 files
Added:     2 files
Deleted:   0 files
Untracked: 1 file

=== PROPOSED COMMIT ===
feat(commands): add /check-in command

- Security audit for credentials and paths
- Auto-cleanup of temp files
- Code audit for quality issues
- Auto-generated commit messages

Co-Authored-By: Claude <noreply@anthropic.com>

════════════════════════════════════════════════════════════════
Proceed with commit? [Confirm/Edit/Cancel]
```

---

## Error Handling

| Scenario | Action |
|----------|--------|
| Security issue found | STOP, report, do not commit |
| Code audit warnings | WARN, continue to commit |
| No changes to commit | Report "Nothing to commit" |
| Git not initialized | Report error, suggest `git init` |
| No remote configured | Skip push step |

---

## Files Excluded from Security Scan

These files are expected to contain sensitive data and are gitignored:

- `credentials.yaml`
- `.env`
- `*.local.yaml`
- `state/`
- `logs/`
