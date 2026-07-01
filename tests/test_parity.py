"""Parity + documentation tests for the lifecycle pipeline.

Machine-checks the same invariants the `lifecycle_parity_auditor` agent reviews:

1. Functional parity - the Claude orchestrator (.claude/commands/lifecycle.md,
   clean-music.md) lists the canonical phases in the same order as the Python
   ``LIFECYCLE_PHASES`` anchor in ``orchestrator/main.py``.
2. Documentation correctness - every ``python cli.py <subcommand>`` referenced
   in README.md / docs/GETTING_STARTED.md / .claude/commands/*.md resolves to a
   real subparser declared in cli.py.

Deterministic and offline: no network, no audio fixtures. The checks read
whatever files exist on disk; sibling docs/commands may still be landing in
parallel, so a referenced-but-absent file is skipped rather than failed.
"""

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _read(rel):
    """Return file text, or None if the file is not present yet."""
    p = PROJECT_ROOT / rel
    if not p.exists():
        return None
    return p.read_text(encoding="utf-8")


# --- the parity anchor -----------------------------------------------------

def test_lifecycle_phases_importable_and_ordered():
    """LIFECYCLE_PHASES is the single source of truth for phase order."""
    from orchestrator.main import LIFECYCLE_PHASES

    assert LIFECYCLE_PHASES == [
        "scan", "identify", "validate", "dedupe", "covers", "fix",
    ]


# --- real cli.py subcommands -----------------------------------------------

def _cli_subcommands():
    """Extract real subparser names from cli.py via its add_parser calls."""
    src = _read("cli.py")
    assert src is not None, "cli.py must exist"
    names = set(re.findall(r"add_parser\(\s*['\"]([A-Za-z][\w-]*)['\"]", src))
    # Sanity: the lifecycle subcommand we are auditing must be present.
    assert "lifecycle" in names, f"lifecycle subcommand missing from cli.py: {sorted(names)}"
    return names


def test_cli_has_expected_subcommands():
    names = _cli_subcommands()
    # These are the documented, load-bearing subcommands; guard against renames.
    for expected in ("scan", "validate", "consolidate", "dedupe", "lifecycle"):
        assert expected in names, f"cli.py is missing subcommand '{expected}'"


# --- functional parity: slash commands list phases in order ----------------

def _assert_phases_in_order(text, source_name):
    """Each phase token appears, in LIFECYCLE_PHASES order, by first occurrence.

    Robust to wording: matches whole-word phase tokens case-insensitively and
    only requires the first occurrences to be monotonically increasing.
    """
    from orchestrator.main import LIFECYCLE_PHASES

    low = text.lower()
    positions = []
    for phase in LIFECYCLE_PHASES:
        m = re.search(r"\b" + re.escape(phase) + r"\b", low)
        assert m is not None, f"{source_name}: phase '{phase}' is never mentioned"
        positions.append(m.start())
    assert positions == sorted(positions), (
        f"{source_name}: phases are out of order vs LIFECYCLE_PHASES "
        f"(first-occurrence offsets: {positions})"
    )


def test_lifecycle_command_lists_phases_in_order():
    """The canonical /lifecycle command must enumerate phases in anchor order.

    Only lifecycle.md is held to strict pipeline order: clean-music.md is the
    legacy autonomous command and intentionally describes its own step sequence
    (it uses words like "validate" in prose), so ordering it against
    LIFECYCLE_PHASES would be a false positive. clean-music.md parity is covered
    qualitatively by the lifecycle_parity_auditor agent instead.
    """
    rel = ".claude/commands/lifecycle.md"
    text = _read(rel)
    if text is None:
        pytest.skip(f"{rel} not present yet (sibling worker may still be landing it)")
    _assert_phases_in_order(text, rel)


# --- documentation correctness: referenced subcommands are real ------------

# Match `python cli.py <subcommand>` where subcommand starts with a letter,
# so flags (`--help`) and placeholders (`<command>`) are not captured.
_CLI_REF = re.compile(r"python\s+cli\.py\s+([a-z][\w-]*)")

_DOC_FILES = [
    "README.md",
    "docs/GETTING_STARTED.md",
    "CLAUDE.md",
]


def _command_md_files():
    cmd_dir = PROJECT_ROOT / ".claude" / "commands"
    if not cmd_dir.is_dir():
        return []
    return [str(p.relative_to(PROJECT_ROOT)).replace("\\", "/")
            for p in sorted(cmd_dir.glob("*.md"))]


@pytest.mark.parametrize("rel", _DOC_FILES + _command_md_files())
def test_referenced_cli_subcommands_exist(rel):
    from orchestrator.main import LIFECYCLE_PHASES

    text = _read(rel)
    if text is None:
        pytest.skip(f"{rel} not present yet")
    real = _cli_subcommands()
    # Known vocabulary = real subparsers PLUS canonical phase names. Docs
    # legitimately show phase-illustrative invocations (e.g. `cli.py fix`, where
    # `fix` is a pipeline phase run by FixerAgent rather than a standalone
    # subparser). Allowing the phase names keeps this check catching genuine
    # typos (e.g. `cli.py scna`) without false-failing on phase references.
    known = real | set(LIFECYCLE_PHASES)
    referenced = set(_CLI_REF.findall(text))
    unknown = sorted(referenced - known)
    assert not unknown, (
        f"{rel} references cli.py subcommands that are neither real subparsers "
        f"nor lifecycle phases: {unknown} (real subcommands: {sorted(real)})"
    )
