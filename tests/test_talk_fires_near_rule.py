"""Talking to someone fires `comes-near`.

The Talk button and the canvas click find the nearest speaker themselves
and fire the event; the Interact verb - what the F key and the button
that reads `Talk to <name>` reach - named the speaker straight out of
its target list and spoke to them with no event at all. A pack that
wrote a `comes-near` rule over a person therefore stayed silent for the
one press most players make: F at someone, and hear their line.

The fixture is the rules pack (sample-world's own town, the keeper at
[7, 4] with seeded lines) with its own POI beside the start removed - a
walk fires `comes-near` for a place, and this test is about the person -
and one rule that fires only when the hero comes near the keeper within
two tiles, the reach the verb has. The hero starts at [3, 4] and walks
two tiles right, so the keeper is in reach and named by the button; the
only event that can fire the rule is a talk.

The player is the REAL woven one in jsdom - nothing is stubbed but the
canvas - and every read is a published snapshot (`window.VEFR_WHY`,
`window.VEFR_HERO_AT`) or what the page shows.

Run with:

    bash tests/run.sh tests/test_talk_fires_near_rule.py
"""

import shutil

import pytest

from play_kit import pack, play, weave

pytestmark = pytest.mark.skipif(shutil.which("node") is None,
                                reason="node not installed")

# One rule, over the sample's own keeper, at the reach the verb has.
# Not `once`: the second test presses both roads and wants two firings.
RULES = [
    {"id": "keeper-hears-you",
     "when": {"comes-near": {"who": "keeper", "distance": 2}},
     "then": [{"say": "The Keeper looks up."}],
     "once": False},
]

READS = [
    "VEFR_WHY",
    "VEFR_HERO_AT",
    "text:#interact-label",
    "text:#combat-live",
]

# Begin, two steps right (the hero stands at [5, 4], two tiles from the
# keeper), then the F press a player makes.
TALK = ["begin", "walk:right,right", "wait:200", "key:f", "wait:400"]


def fixture_pack(tmp_path):
    """The rules pack, its beside-the-start POI gone, and one watcher rule."""
    return pack(tmp_path, "rules", patch={
        # The fixture puts a POI named `keeper` one step right of the
        # start so a walk fires `comes-near`; a talk must be the only
        # road to this rule, so the POI is taken away.
        "acts/act-1/town/contract.json": {"pois": {"4,4": None}},
        "world.json": {"rules": RULES},
    })


def why_ids(reads) -> list:
    return [e["id"] for e in reads["VEFR_WHY"]]


def test_the_interact_verb_fires_comes_near_for_the_speaker_it_names(tmp_path):
    """The F key is the road a player takes to a resident's line, and it
    fires the same event the Talk button does."""
    html = weave(fixture_pack(tmp_path), tmp_path)
    out = play(html, {"steps": TALK, "read": READS})
    assert out["errors"] == [], out["errors"]
    reads = out["reads"]
    # The hero walked to the tile the button names the keeper from.
    assert reads["VEFR_HERO_AT"] == {"x": 5, "y": 4, "region": "town"}
    assert reads["text:#interact-label"] == "Talk to The Keeper"
    assert "keeper-hears-you" in why_ids(reads), \
        "the talk did not fire the rule that watches for the keeper"
    assert "The Keeper looks up." in reads["text:#combat-live"]


def test_the_talk_button_and_the_interact_verb_fire_the_same_event(tmp_path):
    """Both roads to a resident's line reach the same event, so a pack's
    rule cannot answer one press and not the other."""
    html = weave(fixture_pack(tmp_path), tmp_path)
    out = play(html, {"steps": ["begin", "walk:right,right", "wait:200",
                                "click:#talk", "wait:400",
                                "click:#npc-close", "wait:200",
                                "key:f", "wait:400"],
                      "read": READS})
    assert out["errors"] == [], out["errors"]
    # The Talk button fired it, and so did the verb behind the F key -
    # the rule is not `once`, so a second firing is a second entry.
    assert why_ids(out["reads"]).count("keeper-hears-you") == 2, why_ids(out["reads"])
