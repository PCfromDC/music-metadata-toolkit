"""Tests for the Claude agent integration layer (orchestrator/claude_agents.py).

These cover the agent-loading API, the knowledge base accessors, and the
invoker-driven run_agent / decide_auto_apply wire-in. No model is called; a
deterministic fake invoker stands in for Claude.
"""

import json

import pytest

from orchestrator.claude_agents import (
    AgentWorkflow,
    ClaudeAgentHelper,
    KnowledgeBase,
)

# Every agent spec that should exist and be loadable + schema-checkable.
AGENTS = [
    "metadata_validator",
    "conflict_resolver",
    "metadata_enrichment",
    "fingerprint_validator",
    "report_generator",
    "cover_art_verifier",
    "duplicate_detector",
    "code_quality_auditor",
    "test_author",
]


@pytest.fixture
def helper():
    return ClaudeAgentHelper()


@pytest.mark.parametrize("agent", AGENTS)
def test_every_agent_prompt_loads(helper, agent):
    prompt = helper.load_agent_prompt(agent)
    assert prompt is not None, f"{agent}.md should exist under .claude/agents"
    assert len(prompt) > 100


def test_unknown_agent_returns_none(helper):
    assert helper.load_agent_prompt("does_not_exist") is None


def test_format_for_agent_embeds_prompt_and_data(helper):
    request = helper.prepare_validation_input(
        album_path="/m/A/B",
        folder_name="B",
        current_metadata={"track_count": 3},
        trusted_source_metadata=None,
    )
    text = helper.format_for_agent("metadata_validator", request)
    assert "Metadata Validator" in text
    assert "track_count" in text


def test_run_agent_pending_without_invoker(helper):
    request = helper.prepare_validation_input(
        album_path="/m/A/B", folder_name="B", current_metadata={}, trusted_source_metadata=None
    )
    out = helper.run_agent("metadata_validator", request, invoker=None)
    assert out["status"] == "pending"
    assert out["prompt"]
    assert out["result"] is None


def test_run_agent_ok_with_valid_invoker(helper):
    request = helper.prepare_validation_input(
        album_path="/m/A/B", folder_name="B", current_metadata={}, trusted_source_metadata=None
    )
    payload = {"overall_quality_score": 95, "validation_status": "excellent"}
    out = helper.run_agent("metadata_validator", request, invoker=lambda _p: json.dumps(payload))
    assert out["status"] == "ok"
    assert out["result"]["overall_quality_score"] == 95


def test_run_agent_invalid_schema(helper):
    request = helper.prepare_validation_input(
        album_path="/m/A/B", folder_name="B", current_metadata={}, trusted_source_metadata=None
    )
    out = helper.run_agent("metadata_validator", request, invoker=lambda _p: '{"foo": 1}')
    assert out["status"] == "invalid_schema"


def test_run_agent_parse_error(helper):
    request = helper.prepare_validation_input(
        album_path="/m/A/B", folder_name="B", current_metadata={}, trusted_source_metadata=None
    )
    out = helper.run_agent("metadata_validator", request, invoker=lambda _p: "not json at all")
    assert out["status"] == "parse_error"


def test_run_agent_invoker_error(helper):
    request = helper.prepare_validation_input(
        album_path="/m/A/B", folder_name="B", current_metadata={}, trusted_source_metadata=None
    )

    def boom(_prompt):
        raise RuntimeError("model down")

    out = helper.run_agent("metadata_validator", request, invoker=boom)
    assert out["status"] == "invoker_error"
    assert "model down" in out["error"]


def test_parse_agent_response_handles_code_fences(helper):
    raw = "Here you go:\n```json\n{\"a\": 1}\n```\n"
    assert helper.parse_agent_response(raw) == {"a": 1}


def test_should_auto_apply_reads_overall_quality_score(helper):
    assert helper.should_auto_apply(
        {"overall_quality_score": 96, "track_count_match": True}
    )
    assert not helper.should_auto_apply(
        {"overall_quality_score": 96, "track_count_match": False}
    )
    assert not helper.should_auto_apply({"overall_quality_score": 50})


def test_knowledge_base_reads_committed_files():
    kb = KnowledgeBase()
    assert len(kb.load_patterns()) >= 1
    assert isinstance(kb.load_corrections(), list)
    assert isinstance(kb.load_cover_mapping(), dict)


def test_known_cover_url_for_seeded_album():
    kb = KnowledgeBase()
    url = kb.known_cover_url("/music/Ben Harper/Diamonds On The Inside")
    assert url and url.startswith("http")


def test_known_cover_url_missing_returns_none():
    kb = KnowledgeBase()
    assert kb.known_cover_url("/music/Nobody/Unknown Album") is None


def test_album_key_uses_last_two_segments():
    assert KnowledgeBase.album_key("/x/y/Artist/Album") == "Artist/Album"
    assert KnowledgeBase.album_key("Album") == "Album"


def test_knowledge_base_missing_path_fails_soft(tmp_path):
    kb = KnowledgeBase(str(tmp_path / "nope"))
    assert kb.load_patterns() == []
    assert kb.load_corrections() == []
    assert kb.load_cover_mapping() == {}


def _two_stage_invoker(prompt):
    """Fake Claude: returns a valid validator or resolver payload by prompt."""
    if "Metadata Validator" in prompt:
        return json.dumps(
            {
                "overall_quality_score": 95,
                "validation_status": "excellent",
                "track_count_match": True,
                "requires_human_review": False,
            }
        )
    return json.dumps(
        {
            "conflict_resolution_status": "resolved",
            "artwork_decision": "PRESERVE",
            "requires_human_review": [],
        }
    )


def test_decide_auto_apply_pending_without_invoker():
    wf = AgentWorkflow()
    decision = wf.decide_auto_apply(
        album_path="/m/A/B",
        folder_name="B",
        current_metadata={"track_count": 3},
        enrichment_data={"best_match": {}},
    )
    assert decision["auto_apply"] is False
    assert decision["stage"] == "pending"
    assert decision["validation"]["status"] == "pending"


def test_decide_auto_apply_green_path():
    wf = AgentWorkflow()
    decision = wf.decide_auto_apply(
        album_path="/m/Ben Harper/Diamonds On The Inside",
        folder_name="Diamonds On The Inside",
        current_metadata={"track_count": 12},
        enrichment_data={"best_match": {}, "trusted_sources": {}},
        invoker=_two_stage_invoker,
    )
    assert decision["auto_apply"] is True
    assert decision["stage"] == "conflict_resolution"
    # Knowledge base hint surfaced for this seeded album.
    assert decision["knowledge"]["known_cover_url"]


def test_decide_auto_apply_blocks_on_human_review():
    wf = AgentWorkflow()

    def invoker(prompt):
        if "Metadata Validator" in prompt:
            return json.dumps(
                {
                    "overall_quality_score": 95,
                    "validation_status": "excellent",
                    "track_count_match": True,
                    "requires_human_review": False,
                }
            )
        return json.dumps(
            {
                "conflict_resolution_status": "requires_review",
                "artwork_decision": "PRESERVE",
                "requires_human_review": ["track 3 title"],
            }
        )

    decision = wf.decide_auto_apply(
        album_path="/m/A/B",
        folder_name="B",
        current_metadata={"track_count": 3},
        enrichment_data={"best_match": {}, "trusted_sources": {}},
        invoker=invoker,
    )
    assert decision["auto_apply"] is False
    assert decision["stage"] == "conflict_resolution"
