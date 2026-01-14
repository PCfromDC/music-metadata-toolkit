#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Claude Agent Integration Module

Provides utilities for preparing data for Claude agent decisions.
The actual Claude subagent invocation happens through Claude Code's Task tool,
but this module helps format data and parse results.

Agent Prompts are stored in: .claude/agents/
    - metadata_validator.md
    - metadata_enrichment.md
    - fingerprint_validator.md
    - conflict_resolver.md
    - report_generator.md

Usage:
    from orchestrator.claude_agents import ClaudeAgentHelper

    helper = ClaudeAgentHelper()
    validation_input = helper.prepare_validation_input(album_data, source_data)
    # Then invoke Claude subagent with this data
"""

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


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


class ClaudeAgentHelper:
    """
    Helper class for Claude agent integration.

    Provides methods to:
    - Format data for agent input
    - Load agent prompts
    - Parse agent output
    - Validate agent responses
    """

    def __init__(self, agents_path: str = ".claude/agents"):
        """
        Initialize helper.

        Args:
            agents_path: Path to Claude agent definitions
        """
        self.agents_path = Path(agents_path)

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
            # Handle cases where response includes markdown code blocks
            if '```json' in response:
                start = response.find('```json') + 7
                end = response.find('```', start)
                json_str = response[start:end].strip()
            elif '```' in response:
                start = response.find('```') + 3
                end = response.find('```', start)
                json_str = response[start:end].strip()
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
            'metadata_validator': ['quality_score', 'validation_status'],
            'conflict_resolver': ['conflict_resolution_status', 'artwork_decision'],
            'metadata_enrichment': ['enrichment_status', 'tracks'],
            'fingerprint_validator': ['fingerprint', 'validation'],
            'report_generator': ['album', 'tracks', 'processing_info']
        }

        agent_required = required_fields.get(agent_name, [])
        return all(field in response for field in agent_required)

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

        quality_score = validation_result.get('quality_score', 0)
        requires_review = validation_result.get('requires_human_review', False)

        # Auto-apply if quality >= 85 and no human review required
        if quality_score >= thresholds['quality_score']['auto_accept_with_flag'] and not requires_review:
            return True

        # Check for critical issues that require human review
        if validation_result.get('track_count_match') is False:
            return False

        if quality_score >= thresholds['quality_score']['auto_accept']:
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
