import copy
import json

import pytest

from vefr import generator, maplab, stefna
from vefr.stefna import build_payload, generate_letter
from vefr.world import PackError


GOOD = json.dumps({"letter": "Keep the door shut at night. The rest is yours."})


def test_payload_asks_for_a_letter():
    p = build_payload()
    assert p["format"]["required"] == ["letter"]
    assert "letter" in p["prompt"]
    assert p["options"]["temperature"] == 0.8


def test_stefna_voice_falls_back_to_the_packs_first_voice(monkeypatch):
    # A pack that never named its bell voice still works: the first
    # declared voice takes the role. The engine holds no default -
    # the pack declares itself.
    monkeypatch.setattr(
        stefna, "load_world",
        lambda: {"voices": {"keeper": {"strike": "strike text"}, "other": {"strike": "other"}}},
    )
    assert stefna.stefna_voice_key() == "keeper"


def test_stefna_voice_refuses_a_voiceless_pack(monkeypatch):
    monkeypatch.setattr(stefna, "load_world", lambda: {"voices": {}})
    with pytest.raises(PackError):
        stefna.stefna_voice_key()


def test_stefna_voice_refuses_unknown_declared_voice(monkeypatch):
    monkeypatch.setattr(
        stefna, "load_world",
        lambda: {"stefna_voice": "keepr", "voices": {"keeper": {"strike": "s"}}},
    )
    with pytest.raises(PackError) as exc:
        stefna.stefna_voice_key()
    assert "keepr" in str(exc.value)


def test_validator_catches_stefna_voice_typo():
    from vefr.world import load_world
    w = copy.deepcopy(load_world("sample-world"))  # load_world is lru_cached: never edit the shared copy
    w["stefna_voice"] = "nonexistent_voice"
    errs = maplab.validate(w)
    assert any("stefna_voice 'nonexistent_voice'" in e for e in errs)


def test_validator_catches_missing_voice_strike():
    from vefr.world import load_world
    w = copy.deepcopy(load_world("sample-world"))  # load_world is lru_cached: never edit the shared copy
    w["voices"]["keeper"]["strike"] = ""
    errs = maplab.validate(w)
    assert any("missing required non-empty 'strike'" in e for e in errs)


def test_letter_parses(monkeypatch):
    monkeypatch.setattr(generator, "_completion", lambda *a, **k: GOOD)
    letter = generate_letter()
    assert "door" in letter.letter


def test_letter_retries(monkeypatch):
    calls = []

    def flaky(*a, **k):
        calls.append(1)
        return GOOD if len(calls) > 1 else "{oops"

    monkeypatch.setattr(generator, "_completion", flaky)
    assert "door" in generate_letter().letter
    assert len(calls) == 2

