"""Tests for the pluggable AI validator framework.

These assert the zero-AI default contract: NullValidator abstains, the registry
resolves names (including the contrib template) without any network, and bad
names degrade to abstain rather than raising.
"""

import pytest

from validators import (
    BaseAIValidator,
    NullValidator,
    Verdict,
    available_validators,
    get_validator,
)

ALBUM_META = {"album": "Achtung Baby", "artist": "U2", "year": "1991"}
FAKE_IMAGE = b"\xff\xd8\xff" + b"\x00" * 64  # non-empty; validators don't decode it


def test_verdict_rejects_bad_label():
    with pytest.raises(ValueError):
        Verdict(verdict="definitely")


def test_verdict_clamps_confidence():
    assert Verdict(verdict="match", confidence=5.0).confidence == 1.0
    assert Verdict(verdict="match", confidence=-1.0).confidence == 0.0


def test_null_validator_abstains():
    validator = NullValidator({})
    assert validator.name == "null"
    assert validator.capabilities == {"vision": False}
    verdict = validator.verify_cover_match(FAKE_IMAGE, ALBUM_META)
    assert verdict.abstained
    assert verdict.verdict == "abstain"
    assert verdict.confidence == 0.0
    assert verdict.provider == "null"


def test_get_validator_default_is_null():
    # Missing, empty, and "null" all resolve to NullValidator.
    for name in (None, "", "null"):
        validator = get_validator(name, {})
        assert isinstance(validator, NullValidator)


def test_get_validator_unknown_name_degrades_to_null():
    validator = get_validator("does-not-exist", {})
    assert isinstance(validator, NullValidator)
    assert validator.verify_cover_match(FAKE_IMAGE, ALBUM_META).abstained


def test_registry_loads_contrib_example_by_name():
    validator = get_validator("example", {})
    assert isinstance(validator, BaseAIValidator)
    assert validator.name == "example"
    verdict = validator.verify_cover_match(FAKE_IMAGE, ALBUM_META)
    assert isinstance(verdict, Verdict)
    assert verdict.verdict in {"match", "mismatch", "uncertain", "abstain"}
    assert verdict.provider == "example"
    # The template received the bytes and referenced the album in its notes.
    assert "Achtung Baby" in verdict.notes


def test_contrib_example_abstains_on_empty_image():
    validator = get_validator("example", {})
    assert validator.verify_cover_match(b"", ALBUM_META).abstained


def test_available_validators_lists_builtins_and_contrib():
    found = available_validators()
    for builtin in ("null", "ollama", "openai_compat", "anthropic", "hermes"):
        assert found.get(builtin) == "builtin"
    assert found.get("example") == "contrib"


def test_parse_verdict_extracts_json_with_trailing_prose():
    from validators._prompt import parse_verdict

    text = '{"verdict": "mismatch", "confidence": 0.95, "notes": "wrong band"}. Note: {n/a}'
    verdict = parse_verdict(text, "test")
    assert verdict.verdict == "mismatch"
    assert verdict.confidence == 0.95


def test_parse_verdict_does_not_misread_negation():
    from validators._prompt import parse_verdict

    # Prose answer with no JSON: must NOT be classified as mismatch/match by
    # naive substring scanning; stays conservative as uncertain.
    for prose in (
        "The artwork is correct; there is no mismatch with this album.",
        "This is not a match for the album.",
    ):
        verdict = parse_verdict(prose, "test")
        assert verdict.verdict == "uncertain"


def test_parse_verdict_handles_non_string_content():
    from validators._prompt import parse_verdict

    # List-of-parts (some OpenAI-compatible servers) must not raise.
    verdict = parse_verdict([{"type": "text", "text": "x"}], "test")
    assert verdict.verdict in {"uncertain", "abstain"}
    assert parse_verdict(None, "test").abstained


def test_builtin_vision_validators_abstain_without_endpoint_or_key(monkeypatch):
    # Even with the providers selected, no endpoint/key means fail-soft abstain,
    # and crucially no network call is attempted (empty image short-circuits or
    # the missing-config guards return abstain first).
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("HERMES_API_KEY", raising=False)
    for name in ("anthropic", "hermes"):
        validator = get_validator(name, {"endpoint": "", "model": ""})
        verdict = validator.verify_cover_match(b"", ALBUM_META)
        assert verdict.abstained
