#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Claude Agent Integration Module

Provides a clean, dependency-free interface for invoking the Claude agent
specifications stored in ``.claude/agents/`` and for reading/writing the
learning knowledge base in ``.claude/knowledge/``.

The actual large-language-model call happens through Claude Code's Task tool
(or any other backend). This module never imports the Anthropic SDK; instead it
accepts an ``invoker`` callable -- ``Callable[[str], str]`` -- that takes a fully
formatted prompt and returns the model's raw text response. That keeps the whole
toolkit runnable as standalone Python while still letting a host (Claude Code,
the orchestrator, a unit test, or a local model) wire a real agent in.

Agent Prompts are stored in: .claude/agents/
    - metadata_validator.md      (quality-scores an album before auto-apply)
    - metadata_enrichment.md     (fetches metadata from trusted sources)
    - fingerprint_validator.md   (AcoustID/Chromaprint track verification)
    - conflict_resolver.md       (reconciles conflicting sources before apply)
    - report_generator.md        (emits JSON/CSV audit reports)
    - cover_art_verifier.md      (AI-vision: embedded art matches the album)
    - duplicate_detector.md      (duplicate tracks/albums)
    - code_quality_auditor.md    (flags duplication/bloat in diffs)
    - test_author.md             (writes/extends the pytest harness)

Knowledge base (read/write contract documented in .claude/knowledge/README.md):
    - corrections.json       (append-only log of applied corrections)
    - cover_art_mapping.json (album_key -> known-correct cover URL)
    - patterns.json          (human-curated issue patterns, read-mostly)

Typical wire-in (consumed by the orchestrator before auto-applying fixes)::

    from orchestrator.claude_agents import ClaudeAgentHelper, AgentWorkflow

    helper = ClaudeAgentHelper()
    workflow = AgentWorkflow()

    # `invoker` is supplied by the host; omit it for a dry, pending envelope.
    decision = workflow.decide_auto_apply(
        album_path=path, folder_name=name,
        current_metadata=meta, enrichment_data=enrich,
        fingerprint_data=fp, invoker=my_claude_invoker,
    )
    if decision["auto_apply"]:
        ...  # safe to apply

The standalone helpers (``prepare_*_input``, ``format_for_agent``,
``parse_agent_response``) remain available for callers that drive the agents
manually.
"""

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


# An invoker takes a fully formatted prompt string and returns the model's raw
# text response. The host (Claude Code Task tool, orchestrator, test, or a local
# model) supplies the implementation; this module never calls an LLM directly.
AgentInvoker = Callable[[str], str]


@dataclass
class ValidationInput:
    """Input data structure for metadata_validator agent"""
    album_path: str
    folder_name: str
    current_metadata: Dict[str, Any]
    trusted_source_metadata: Optional[Dict[str, Any]]
    fingerprint_data: Optional[Dict[str, Any]]
    sources_queried: List[str]
    sources_matched: List[str]
    track_count: int
    has_artwork: bool


@dataclass
class ConflictInput:
    """Input data structure for conflict_resolver agent"""
    album_path: str
    folder_name: str
    current_metadata: Dict[str, Any]
    trusted_sources: Dict[str, Any]  # Key: source name, Value: metadata
    fingerprint_data: Optional[Dict[str, Any]]
    validation_result: Dict[str, Any]


@dataclass
class EnrichmentInput:
    """Input data structure for metadata_enrichment agent"""
    album_path: str
    folder_name: str
    artist: str
    title: str
    track_count: int
    current_metadata: Dict[str, Any]


class KnowledgeBase:
    """
    Read/write access to the persistent learning store in .claude/knowledge/.

    The schemas mirror exactly what utilities/embed_cover.py already writes, so
    this class and the cleanup utilities stay interoperable:

    - corrections.json:       {"corrections": [ {album_path, correction_type,
                              before, after, date, source}, ... ]}  (append-only)
    - cover_art_mapping.json: {"albums": {"Artist/Album": {correct_url,
                              verified_date, source, notes}, ... }}
    - patterns.json:          {"patterns": [ {id, name, description, detection,
                              ...}, ... ]}  (human-curated, read-mostly)

    All reads fail soft (return empty structures) so the toolkit runs even when
    the knowledge base is absent. See .claude/knowledge/README.md.
    """

    def __init__(self, knowledge_path: str = ".claude/knowledge"):
        self.knowledge_path = Path(knowledge_path)

    def _load(self, filename: str, default: Dict[str, Any]) -> Dict[str, Any]:
        path = self.knowledge_path / filename
        if not path.exists():
            return dict(default)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return dict(default)
        # Fail soft: a hand-edited file whose top level is not an object (e.g. a
        # bare array) must not make the downstream .get() calls explode.
        return data if isinstance(data, dict) else dict(default)

    def load_corrections(self) -> List[Dict[str, Any]]:
        """Return the list of logged corrections (empty if none)."""
        return self._load("corrections.json", {"corrections": []}).get("corrections", [])

    def load_cover_mapping(self) -> Dict[str, Any]:
        """Return the album_key -> cover-record mapping (empty if none)."""
        return self._load("cover_art_mapping.json", {"albums": {}}).get("albums", {})

    def load_patterns(self) -> List[Dict[str, Any]]:
        """Return the list of learned issue patterns (empty if none)."""
        return self._load("patterns.json", {"patterns": []}).get("patterns", [])

    @staticmethod
    def album_key(album_path: str) -> str:
        """Derive the "Artist/Album" key used in cover_art_mapping.json."""
        parts = album_path.rstrip("/\\").replace("\\", "/").split("/")
        return "/".join(parts[-2:]) if len(parts) >= 2 else parts[-1]

    def known_cover_url(self, album_path: str) -> Optional[str]:
        """
        Return a previously verified correct cover URL for an album, if known.

        This is the proactive hook described in the AI roadmap: before searching
        for cover art, check whether a human already corrected this album.
        """
        record = self.load_cover_mapping().get(self.album_key(album_path))
        return record.get("correct_url") if record else None

    def past_corrections(self, album_path: str) -> List[Dict[str, Any]]:
        """
        Return prior corrections logged for a given album.

        Matches on the root-independent "Artist/Album" key (same scheme as
        ``known_cover_url``) so a correction logged under one library root is
        still found when the album is processed from a different root. Falls
        back to a full-path equality check for older entries.
        """
        full = album_path.replace("\\", "/").rstrip("/")
        key = self.album_key(album_path)
        matches = []
        for c in self.load_corrections():
            logged = c.get("album_path", "").replace("\\", "/").rstrip("/")
            if logged == full or self.album_key(logged) == key:
                matches.append(c)
        return matches


class ClaudeAgentHelper:
    """
    Helper class for Claude agent integration.

    Provides methods to:
    - Format data for agent input
    - Load agent prompts
    - Invoke an agent through a host-supplied callable
    - Parse and validate agent output
    """

    def __init__(self, agents_path: str = ".claude/agents",
                 knowledge_path: str = ".claude/knowledge"):
        """
        Initialize helper.

        Args:
            agents_path: Path to Claude agent definitions
            knowledge_path: Path to the learning knowledge base
        """
        self.agents_path = Path(agents_path)
        self.knowledge = KnowledgeBase(knowledge_path)

    def load_agent_prompt(self, agent_name: str) -> Optional[str]:
        """
        Load an agent's prompt from its markdown file.

        Args:
            agent_name: Name of the agent (e.g., 'metadata_validator')

        Returns:
            Agent prompt text or None if not found
        """
        prompt_file = self.agents_path / f"{agent_name}.md"
        if prompt_file.exists():
            return prompt_file.read_text(encoding='utf-8')
        return None

    def prepare_validation_input(
        self,
        album_path: str,
        folder_name: str,
        current_metadata: Dict[str, Any],
        trusted_source_metadata: Optional[Dict[str, Any]],
        fingerprint_data: Optional[Dict[str, Any]] = None,
        sources_queried: List[str] = None,
        sources_matched: List[str] = None
    ) -> Dict[str, Any]:
        """
        Prepare input data for the metadata_validator agent.

        Args:
            album_path: Path to album folder
            folder_name: Album folder name
            current_metadata: Metadata from audio files
            trusted_source_metadata: Best match from sources
            fingerprint_data: Audio fingerprint results
            sources_queried: List of sources that were queried
            sources_matched: List of sources that returned results

        Returns:
            Formatted input dictionary for Claude agent
        """
        input_data = ValidationInput(
            album_path=album_path,
            folder_name=folder_name,
            current_metadata=current_metadata,
            trusted_source_metadata=trusted_source_metadata,
            fingerprint_data=fingerprint_data,
            sources_queried=sources_queried or [],
            sources_matched=sources_matched or [],
            track_count=current_metadata.get('track_count', 0),
            has_artwork=self._check_artwork(current_metadata)
        )

        return {
            'agent': 'metadata_validator',
            'input': asdict(input_data),
            'timestamp': datetime.now().isoformat(),
            'request_type': 'validation'
        }

    def prepare_conflict_input(
        self,
        album_path: str,
        folder_name: str,
        current_metadata: Dict[str, Any],
        trusted_sources: Dict[str, Any],
        fingerprint_data: Optional[Dict[str, Any]],
        validation_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Prepare input data for the conflict_resolver agent.

        Args:
            album_path: Path to album folder
            folder_name: Album folder name
            current_metadata: Metadata from audio files
            trusted_sources: Metadata from all trusted sources
            fingerprint_data: Audio fingerprint results
            validation_result: Output from metadata_validator

        Returns:
            Formatted input dictionary for Claude agent
        """
        input_data = ConflictInput(
            album_path=album_path,
            folder_name=folder_name,
            current_metadata=current_metadata,
            trusted_sources=trusted_sources,
            fingerprint_data=fingerprint_data,
            validation_result=validation_result
        )

        return {
            'agent': 'conflict_resolver',
            'input': asdict(input_data),
            'timestamp': datetime.now().isoformat(),
            'request_type': 'conflict_resolution'
        }

    def prepare_enrichment_input(
        self,
        album_path: str,
        folder_name: str,
        artist: str = "Various Artists",
        title: Optional[str] = None,
        track_count: int = 0,
        current_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Prepare input data for the metadata_enrichment agent.

        Args:
            album_path: Path to album folder
            folder_name: Album folder name
            artist: Album artist
            title: Album title (defaults to folder_name)
            track_count: Number of tracks
            current_metadata: Current metadata from files

        Returns:
            Formatted input dictionary for Claude agent
        """
        input_data = EnrichmentInput(
            album_path=album_path,
            folder_name=folder_name,
            artist=artist,
            title=title or folder_name,
            track_count=track_count,
            current_metadata=current_metadata or {}
        )

        return {
            'agent': 'metadata_enrichment',
            'input': asdict(input_data),
            'timestamp': datetime.now().isoformat(),
            'request_type': 'enrichment'
        }

    def format_for_agent(self, agent_name: str, data: Dict[str, Any]) -> str:
        """
        Format data as a prompt for Claude agent invocation.

        This creates a structured prompt that includes:
        1. Agent context
        2. Input data as JSON
        3. Expected output format

        Args:
            agent_name: Name of the agent
            data: Input data dictionary

        Returns:
            Formatted prompt string for Claude
        """
        agent_prompt = self.load_agent_prompt(agent_name)

        prompt = f"""# {agent_name.replace('_', ' ').title()} Task

## Agent Instructions
{agent_prompt or 'No specific instructions found.'}

## Input Data
```json
{json.dumps(data, indent=2, ensure_ascii=False)}
```

## Required Output
Respond with a valid JSON object following the output schema defined in the agent instructions.
Ensure all decisions are documented with rationale.
"""
        return prompt

    def run_agent(
        self,
        agent_name: str,
        request: Dict[str, Any],
        invoker: Optional[AgentInvoker] = None,
    ) -> Dict[str, Any]:
        """
        Load, format, invoke, parse, and validate an agent in one call.

        This is the single entry point the orchestrator should use. It closes
        the loop that the prepare_* helpers only opened: it actually formats the
        prompt and (when an invoker is supplied) runs it and validates the JSON.

        Args:
            agent_name: Agent to run (e.g. 'metadata_validator').
            request: A request envelope from a prepare_*_input helper (or any
                dict with an 'input' key).
            invoker: Host-supplied ``Callable[[str], str]`` that runs the prompt
                against a model and returns raw text. If None, no model is
                called and a 'pending' envelope with the formatted prompt is
                returned so callers can dispatch it themselves.

        Returns:
            A result dict::

                {
                  "agent": str,
                  "status": "ok" | "pending" | "invalid_schema"
                            | "parse_error" | "invoker_error",
                  "prompt": str,              # always included
                  "result": dict | None,      # parsed agent output when status ok
                  "error": str | None,
                }
        """
        prompt = self.format_for_agent(agent_name, request)
        base = {"agent": agent_name, "prompt": prompt, "result": None, "error": None}

        if invoker is None:
            base["status"] = "pending"
            return base

        try:
            raw = invoker(prompt)
        except Exception as exc:  # noqa: BLE001 - host callable may raise anything
            base["status"] = "invoker_error"
            base["error"] = str(exc)
            return base

        parsed = self.parse_agent_response(raw)

        # A model may emit a top-level JSON array or scalar; parse_agent_response
        # passes that through unchanged. Only a dict can carry the agent schema,
        # so anything else is a schema failure (and dict.get below is safe).
        if not isinstance(parsed, dict):
            base["status"] = "invalid_schema"
            base["error"] = f"expected a JSON object, got {type(parsed).__name__}"
            base["result"] = parsed
            return base

        if parsed.get("status") == "parse_error":
            base["status"] = "parse_error"
            base["error"] = parsed.get("error")
            base["result"] = parsed
            return base

        base["result"] = parsed
        base["status"] = "ok" if self.validate_response(parsed, agent_name) else "invalid_schema"
        return base

    def parse_agent_response(self, response: str) -> Dict[str, Any]:
        """
        Parse JSON response from Claude agent.

        Args:
            response: Raw response text from Claude

        Returns:
            Parsed dictionary or error dict
        """
        try:
            # Try to extract JSON from response
            # Handle cases where response includes markdown code blocks.
            # When the closing fence is missing (truncated output), take the
            # remainder of the string rather than dropping the last character.
            if '```json' in response:
                start = response.find('```json') + 7
                end = response.find('```', start)
                json_str = response[start:(end if end != -1 else len(response))].strip()
            elif '```' in response:
                start = response.find('```') + 3
                end = response.find('```', start)
                json_str = response[start:(end if end != -1 else len(response))].strip()
            else:
                json_str = response.strip()

            return json.loads(json_str)

        except json.JSONDecodeError as e:
            return {
                'status': 'parse_error',
                'error': str(e),
                'raw_response': response[:500]  # First 500 chars for debugging
            }

    def validate_response(self, response: Dict[str, Any], agent_name: str) -> bool:
        """
        Validate that response has required fields for agent type.

        Args:
            response: Parsed response dictionary
            agent_name: Name of the agent

        Returns:
            True if response is valid
        """
        required_fields = {
            'metadata_validator': ['overall_quality_score', 'validation_status'],
            'conflict_resolver': ['conflict_resolution_status', 'artwork_decision'],
            'metadata_enrichment': ['enrichment_status', 'tracks'],
            'fingerprint_validator': ['fingerprint', 'validation'],
            'report_generator': ['album', 'tracks', 'processing_info'],
            'cover_art_verifier': ['verdict', 'confidence'],
            'duplicate_detector': ['duplicate_groups', 'status'],
            'code_quality_auditor': ['findings', 'status'],
            'test_author': ['tests', 'status'],
        }

        agent_required = required_fields.get(agent_name, [])
        if not all(field in response for field in agent_required):
            # The in-repo local scorer (orchestrator/music_metadata_system.py)
            # emits the legacy `quality_score` key. Accept it as a stand-in for
            # `overall_quality_score` so that scorer can be wired through here
            # without being rejected as invalid_schema.
            if (
                agent_name == 'metadata_validator'
                and 'overall_quality_score' not in response
                and 'quality_score' in response
                and 'validation_status' in response
            ):
                return True
            return False
        return True

    def _check_artwork(self, metadata: Dict[str, Any]) -> bool:
        """Check if album has embedded artwork"""
        # This would need actual file checking in full implementation
        return metadata.get('has_artwork', False)

    def get_decision_thresholds(self) -> Dict[str, Any]:
        """
        Get decision thresholds for automated processing.

        Returns:
            Dictionary of thresholds
        """
        return {
            'quality_score': {
                'auto_accept': 90,
                'auto_accept_with_flag': 85,
                'manual_review': 70,
                'reject': 0
            },
            'fingerprint_confidence': {
                'trust_completely': 95,
                'likely_correct': 80,
                'verify_manually': 60,
                'reject': 0
            },
            'human_review_triggers': [
                'fingerprint_mismatch_below_60',
                'track_count_mismatch',
                'multiple_source_failures',
                'quality_score_below_70'
            ]
        }

    def should_auto_apply(self, validation_result: Dict[str, Any]) -> bool:
        """
        Determine if changes should be auto-applied based on validation.

        Args:
            validation_result: Output from metadata_validator

        Returns:
            True if changes can be auto-applied (95% automation target)
        """
        thresholds = self.get_decision_thresholds()

        # The metadata_validator schema emits `overall_quality_score`; accept the
        # legacy `quality_score` key too for forward/backward compatibility.
        quality_score = validation_result.get(
            'overall_quality_score', validation_result.get('quality_score', 0)
        )
        requires_review = validation_result.get('requires_human_review', False)

        # Critical blockers come first. A track-count mismatch means the wrong
        # album or missing tracks -- never auto-apply regardless of score.
        if validation_result.get('track_count_match') is False:
            return False

        if requires_review:
            return False

        # Auto-apply if quality clears the (flagged) auto-accept bar.
        if quality_score >= thresholds['quality_score']['auto_accept_with_flag']:
            return True

        return False


class AgentWorkflow:
    """
    Orchestrates the multi-agent workflow.

    Manages the sequence of agent invocations for album processing.
    """

    def __init__(self):
        self.helper = ClaudeAgentHelper()
        self.workflow_log = []

    def log_step(self, step: str, agent: str, result: str):
        """Log a workflow step"""
        self.workflow_log.append({
            'step': step,
            'agent': agent,
            'result': result,
            'timestamp': datetime.now().isoformat()
        })

    def get_workflow_summary(self) -> Dict[str, Any]:
        """Get summary of workflow execution"""
        return {
            'steps_executed': len(self.workflow_log),
            'log': self.workflow_log
        }

    def decide_auto_apply(
        self,
        album_path: str,
        folder_name: str,
        current_metadata: Dict[str, Any],
        enrichment_data: Dict[str, Any],
        fingerprint_data: Optional[Dict[str, Any]] = None,
        invoker: Optional[AgentInvoker] = None,
    ) -> Dict[str, Any]:
        """
        Run the validator -> conflict-resolver gate before auto-applying fixes.

        This is the concrete wire-in the orchestrator can call instead of
        auto-applying blindly. It chains the two decision agents and folds in the
        knowledge base, returning a single verdict the caller can branch on.

        Flow:
          1. metadata_validator scores the album.
          2. If the score clears the auto-apply bar (helper.should_auto_apply),
             conflict_resolver reconciles the sources for a final decision.
          3. The knowledge base is consulted for a known-correct cover URL and
             any prior corrections on this album.

        With no ``invoker`` the agent steps come back as 'pending' (carrying the
        formatted prompts) so a host can dispatch them; the knowledge-base hints
        are still returned. This keeps the function usable in standalone mode and
        unit tests without a live model.

        Returns:
            {
              "album_path": str,
              "auto_apply": bool,          # True only on an OK, high-confidence path
              "stage": "validation" | "conflict_resolution" | "pending",
              "validation": <run_agent result>,
              "conflict_resolution": <run_agent result> | None,
              "knowledge": {"known_cover_url": str|None,
                            "prior_corrections": int},
              "notes": [str, ...],
            }
        """
        notes: List[str] = []
        kb = self.helper.knowledge
        knowledge = {
            "known_cover_url": kb.known_cover_url(album_path),
            "prior_corrections": len(kb.past_corrections(album_path)),
        }
        if knowledge["known_cover_url"]:
            notes.append("Knowledge base has a verified cover URL for this album.")
        if knowledge["prior_corrections"]:
            notes.append(
                f"{knowledge['prior_corrections']} prior correction(s) logged for this album."
            )

        validation_request = self.helper.prepare_validation_input(
            album_path=album_path,
            folder_name=folder_name,
            current_metadata=current_metadata,
            trusted_source_metadata=enrichment_data.get("best_match"),
            fingerprint_data=fingerprint_data,
            sources_queried=enrichment_data.get("sources_queried", []),
            sources_matched=enrichment_data.get("sources_matched", []),
        )
        validation = self.helper.run_agent("metadata_validator", validation_request, invoker)
        self.log_step("validation", "metadata_validator", validation["status"])

        result: Dict[str, Any] = {
            "album_path": album_path,
            "auto_apply": False,
            "stage": "validation",
            "validation": validation,
            "conflict_resolution": None,
            "knowledge": knowledge,
            "notes": notes,
        }

        if validation["status"] != "ok":
            # Pending (no invoker), parse error, or schema mismatch: do not
            # auto-apply. 'pending' simply means the host still has to dispatch.
            result["stage"] = "pending" if validation["status"] == "pending" else "validation"
            notes.append(f"Validation not actionable (status={validation['status']}).")
            return result

        if not self.helper.should_auto_apply(validation["result"]):
            notes.append("Validation score below auto-apply threshold; human review required.")
            return result

        # Validation cleared the bar -> reconcile sources before applying.
        conflict_request = self.helper.prepare_conflict_input(
            album_path=album_path,
            folder_name=folder_name,
            current_metadata=current_metadata,
            trusted_sources=enrichment_data.get("trusted_sources", {}),
            fingerprint_data=fingerprint_data,
            validation_result=validation["result"],
        )
        conflict = self.helper.run_agent("conflict_resolver", conflict_request, invoker)
        self.log_step("conflict_resolution", "conflict_resolver", conflict["status"])
        result["conflict_resolution"] = conflict
        result["stage"] = "conflict_resolution"

        if conflict["status"] != "ok":
            notes.append(f"Conflict resolution not actionable (status={conflict['status']}).")
            return result

        cr = conflict["result"]
        resolved = cr.get("conflict_resolution_status") == "resolved"
        outstanding = bool(cr.get("requires_human_review"))
        if resolved and not outstanding:
            result["auto_apply"] = True
            notes.append("Validator and conflict resolver agree; safe to auto-apply.")
        else:
            notes.append("Conflicts require human review; not auto-applying.")
        return result

    def prepare_full_workflow(
        self,
        album_path: str,
        folder_name: str,
        current_metadata: Dict[str, Any],
        enrichment_data: Dict[str, Any],
        fingerprint_data: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Prepare all workflow steps for an album.

        This creates the sequence of agent invocations needed
        for complete album processing.

        Args:
            album_path: Path to album folder
            folder_name: Album folder name
            current_metadata: Metadata from audio files
            enrichment_data: Data from trusted sources
            fingerprint_data: Fingerprint results

        Returns:
            List of prepared agent inputs in execution order
        """
        steps = []

        # Step 1: Validation
        steps.append(self.helper.prepare_validation_input(
            album_path=album_path,
            folder_name=folder_name,
            current_metadata=current_metadata,
            trusted_source_metadata=enrichment_data.get('best_match'),
            fingerprint_data=fingerprint_data,
            sources_queried=enrichment_data.get('sources_queried', []),
            sources_matched=enrichment_data.get('sources_matched', [])
        ))

        # Step 2: Conflict Resolution (depends on validation result)
        # This would be prepared after validation completes with actual result
        steps.append({
            'agent': 'conflict_resolver',
            'depends_on': 'metadata_validator',
            'prepare_with': 'prepare_conflict_input'
        })

        # Step 3: Report Generation (depends on both above)
        steps.append({
            'agent': 'report_generator',
            'depends_on': ['metadata_validator', 'conflict_resolver'],
            'prepare_with': 'generate_report_input'
        })

        return steps
