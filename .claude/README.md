# Claude Code Integration

This folder contains configuration for **Claude Code** (Anthropic's AI-powered CLI tool) to enable intelligent, autonomous music library management.

## Overview

Claude Code uses this configuration to:
- Execute complex, multi-step workflows via slash commands
- Make intelligent decisions about metadata validation and conflict resolution
- Maintain consistent behavior through agent role definitions
- Operate autonomously within defined permission boundaries

## Folder Structure

```
.claude/
├── README.md              # This documentation
├── agents/                # AI agent role definitions
│   ├── metadata_validator.md
│   ├── metadata_enrichment.md
│   ├── conflict_resolver.md
│   ├── fingerprint_validator.md
│   └── report_generator.md
├── commands/              # Slash command workflows
│   ├── clean-music.md
│   ├── validate-folders.md
│   ├── consolidate-all.md
│   ├── consolidate-discs.md
│   ├── move-track.md
│   └── verify-covers.md
└── settings.local.json    # Permissions & tool allowlist
```

## Agents

Agent definitions specify **how Claude should think** about different tasks. Each agent has:
- **Role**: What the agent is responsible for
- **Inputs**: What data it receives
- **Outputs**: What it should produce
- **Decision Matrix**: Rules for making choices
- **Constraints**: Things it must never do

### metadata_validator.md
**Purpose**: Verify metadata completeness and consistency

- Checks critical fields: track count, titles, durations, ISRC codes
- Quality scoring: 0-100 scale (90+ excellent, 80-89 good, 70-79 acceptable)
- **Critical constraint**: Never flags artwork as needing replacement (only if corrupted/missing)

### metadata_enrichment.md
**Purpose**: Fetch missing metadata from trusted sources

- **Source priority**: MusicBrainz → Spotify → Discogs → iTunes
- Cross-validates track counts, titles, and durations
- Caching: 24 hours for matches, 1 hour for no-results

### conflict_resolver.md
**Purpose**: Resolve discrepancies between multiple data sources

- Decision thresholds:
  - **UPDATE** (85%+ confidence): Apply automatically
  - **REVIEW** (70-84%): Flag for human review
  - **PRESERVE** (<70%): Keep current value
- **Critical constraint**: Always preserve existing artwork

### fingerprint_validator.md
**Purpose**: Verify audio content matches expected recordings

- Uses Chromaprint fingerprints + AcoustID database
- Cross-references with MusicBrainz recordings
- Validates ISRC codes when available

### report_generator.md
**Purpose**: Generate comprehensive audit reports

- Output formats: JSON (structured), CSV (tabular)
- Includes quality scores, discrepancies, and recommendations
- Summary statistics for batch operations

## Commands

Commands define **autonomous workflows** that Claude executes via slash commands. Each command:
- Specifies step-by-step instructions
- Declares whether user confirmation is needed
- Includes error handling guidance

### /clean-music (Autonomous)
```
/clean-music <path>
```
Complete cleanup workflow:
1. Run metadata extraction
2. Auto-fix folder names
3. Auto-consolidate multi-disc albums
4. Fetch and embed missing cover art
5. Visually verify cover art
6. Generate summary report

**No user prompts required.**

### /validate-folders (Autonomous)
```
/validate-folders <path>
```
Scan and fix folder name mismatches:
- Truncated names → Full metadata names
- Character substitutions → Windows-safe transforms
- Skips multi-disc albums (use /consolidate-all)

### /consolidate-all (Autonomous)
```
/consolidate-all <path>
```
Find and consolidate all multi-disc sets:
- Detects patterns: `[Disc N]`, `Disc N`, `CD N`
- Adds disc prefix to filenames
- Updates discnumber metadata
- Removes empty source folders

### /consolidate-discs (Interactive)
```
/consolidate-discs <path> <album_name>
```
Consolidate a specific multi-disc album with preview and confirmation.

### /move-track (Interactive)
```
/move-track <source> <destination>
```
Move track between albums:
- Asks for new metadata (album, artist, track number)
- Updates embedded metadata
- Cleans up empty source folders

### /verify-covers (Autonomous)
```
/verify-covers <path>
```
Visually verify cover art:
- Reads each folder.jpg
- Compares against album/artist name
- Reports: ✓ Correct, ⚠ Suspicious, ✗ Wrong

## Settings

`settings.local.json` defines:
- **Allowed bash commands**: python, echo, cat, etc.
- **Allowed domains**: discogs.com, allmusic.com, itunes.apple.com
- **Skill permissions**: Which commands can run autonomously

## Adding New Agents

1. Create a new `.md` file in `agents/`
2. Define the role, inputs, outputs, and constraints
3. Reference the agent from your workflow code

**Template:**
```markdown
# Agent Name

## Role
What this agent is responsible for.

## Inputs
- input1: Description
- input2: Description

## Outputs
- output1: Description

## Decision Matrix
| Condition | Action |
|-----------|--------|
| ... | ... |

## Constraints
- Never do X
- Always do Y
```

## Adding New Commands

1. Create a new `.md` file in `commands/`
2. Define usage, examples, and step-by-step workflow
3. Specify if autonomous or interactive

**Template:**
```markdown
# Command Name

Description of what this command does.

## Usage
```
/command-name <arg1> <arg2>
```

## Examples
```
/command-name //path/to/folder
```

## Instructions

When this command is invoked with arguments: $ARGUMENTS

**Workflow:**
1. Step one
2. Step two
3. Step three

## Autonomous Behavior
This command runs [fully autonomously / with confirmation].
```

## Integration with Python

The file `orchestrator/claude_agents.py` bridges Claude Code with Python:

```python
# Load agent prompt
helper = ClaudeAgentHelper()
prompt = helper.load_agent_prompt('metadata_validator')

# Prepare data for agent
input_data = helper.prepare_validation_input(album_data)

# Format as agent prompt
formatted = helper.format_for_agent('metadata_validator', input_data)

# Parse agent response
result = helper.parse_agent_response(response)
```

## Best Practices

1. **Keep agents focused**: Each agent should have a single responsibility
2. **Be explicit about constraints**: Especially for destructive operations
3. **Document decision thresholds**: Make automation boundaries clear
4. **Test with dry-run**: Use `--dry-run` flags when available
5. **Log everything**: Include logging in workflow steps

---

**Last Updated:** 2026-01-13
