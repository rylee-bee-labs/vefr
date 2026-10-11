"""E8d: a warden's challenge, `yields` and `fightable` (ADR 0015 Amendment 1).

Section 2 of the amendment is three optional keys on the warden record, and
every one of them defaults to today's behaviour: `challenge` is `defeat`
(beat it and the flag is set), `yields` is no (a beaten warden vanishes) and
`fightable` is yes (a blow lands). Section 4 is the checks - the walk's first
step is the challenge rather than the killing, and a `rule` warden with no
rule to set its flag is one plain sentence.

This file holds the shapes, the plan record, the checks, and the two
Amendment 1 acceptance cases that E8c had already landed (`story_end` and
the list-form `town_states`), each named as such. The two cases that are the
player's - a `yields` warden staying on its anchor, and a `fightable: false`
warden that cannot be struck and still hunts - are at the bottom, in the
woven player through jsdom, and are skipped without node.

`tests/test_descent_parity.py` holds the two languages equal: the rolled
descent it walks names all three keys, so a JS twin that dropped any of them
would answer with a different plan.
"""

import copy
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

import pytest

from vefr import cli, delve, locks, maplab, shapes
from vefr.maplab import load_pack, validate

sys.path.insert(0, str(Path(__file__).resolve().parent / "fixtures"))
import make_town_pack  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_descent_deltas import TOWN, TOWN_HERO, _doc, _go, _go_fight, _play  # noqa: E402
from test_descent_floors import DESCENT  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "worlds" / "sample-world"

FAMILY = "cellar-boss"
RULE_ID = "the-old-king-is-answered"


def _descent(warden=None, families=None):
    """The fixture descent whose first Section (three floors) ends on a warden floor."""
    descent = copy.deepcopy(DESCENT)
    cellar = descent["sections"][0]
    cellar["pattern"] = ["entry", "n", "warden"]
    if warden is not None:
        cellar["warden"] = warden
    if families is not None:
        for section in descent["sections"]:
            section["families"] = families
    return descent


def _wardens(plan):
    return [m for m in plan["mobs"] if m.get("warden")]


def _say(warden):
    """Every shape sentence for a Section whose warden is `warden`."""
    return [p.sentence for p in
            shapes.check_section({"id": "c", "families": [], "warden": warden})]


# ---- the three keys are part of the record ---------------------------------

def test_a_warden_may_name_all_three_of_amendment_ones_keys():
    assert _say({"family": FAMILY, "challenge": "rule", "yields": True,
                 "fightable": False}) == []
    assert _say({"family": FAMILY, "challenge": "defeat"}) == []


def test_a_challenge_that_is_neither_word_is_refused_in_one_sentence():
    assert _say({"family": FAMILY, "challenge": "talk"}) == [
        'section.warden.challenge must be "defeat" or "rule"']


def test_yields_and_fightable_are_yes_or_no_and_nothing_else():
    assert _say({"family": FAMILY, "yields": "yes"}) == [
        "section.warden.yields must be a yes or a no"]
    assert _say({"family": FAMILY, "fightable": 0}) == [
        "section.warden.fightable must be a yes or a no"]


def test_fightable_false_without_the_rule_challenge_is_refused():
    """The refusal Amendment 1 §2's `fightable` needs: a warden nobody can
    fight and no rule can pass is a Section that cannot be finished."""
    assert _say({"family": FAMILY, "fightable": False}) == [
        'a warden that cannot be struck is one no rule can complete, so '
        '"fightable": false belongs beside "challenge": "rule"']
    assert _say({"family": FAMILY, "challenge": "defeat",
                 "fightable": False}) == _say({"family": FAMILY,
                                               "fightable": False})


def test_the_refusal_goes_away_when_the_challenge_is_the_rule_one():
    assert _say({"family": FAMILY, "challenge": "rule", "fightable": False}) == []


def test_a_fightable_true_needs_no_challenge():
    """Only `false` is the odd one: a warden that can be struck is the
    warden E8a shipped, whatever challenge it names."""
    assert _say({"family": FAMILY, "fightable": True}) == []
    assert _say({"family": FAMILY, "challenge": "rule", "fightable": True}) == []


# ---- the read -------------------------------------------------------------

def test_the_three_defaults_are_todays_behaviour():
    assert delve.WARDEN_CHALLENGES == ("defeat", "rule")
    for warden in (None, delve.warden_of({"warden": FAMILY}),
                   delve.warden_of({"warden": {"family": FAMILY}})):
        assert delve.warden_challenge(warden) == "defeat"
        assert delve.warden_yields(warden) is False
        assert delve.warden_fightable(warden) is True


def test_a_warden_reads_back_exactly_what_the_pack_wrote():
    assert delve.warden_of({"warden": {
        "family": FAMILY, "challenge": "rule", "yields": True,
        "fightable": False}}) == {"id": FAMILY, "family": FAMILY,
                                  "challenge": "rule", "yields": True,
                                  "fightable": False}


# ---- the floor plan -------------------------------------------------------

def test_the_plan_carries_the_challenge_the_keys_and_the_flag():
    plan = delve.floor_plan(_descent({"family": FAMILY, "challenge": "rule",
                                      "yields": True, "fightable": False}), 3)
    assert plan["warden"] == {"id": FAMILY, "flag": f"warden:{FAMILY}:c0",
                              "challenge": "rule", "yields": True,
                              "fightable": False}


def test_the_two_presentation_keys_ride_the_monster_the_player_fights():
    (warden,) = _wardens(delve.floor_plan(
        _descent({"family": FAMILY, "challenge": "rule", "yields": True,
                  "fightable": False}), 3))
    assert warden["fightable"] is False and warden["yields"] is True


def test_a_warden_naming_none_of_the_three_plans_exactly_as_it_did():
    """The compatibility sentence, as a fact about the plan: the record and
    the monster hold the same keys, and the same values, they held before
    Amendment 1 - which is why the digest below does not move."""
    plan = delve.floor_plan(_descent(FAMILY), 3)
    assert plan["warden"] == {"id": FAMILY, "flag": f"warden:{FAMILY}:c0"}
    (warden,) = _wardens(plan)
    assert "challenge" not in warden and "yields" not in warden
    assert "fightable" not in warden


# ---- the checks (Amendment 1 §4) ------------------------------------------

def _rule_pack(tmp_path, warden, sets=True, **kwargs):
    """The town fixture with its first warden replaced and a rule to set its flag.

    The rule fires on `picks-up` of the pebble the fixture's catalog
    declares, and the flag it sets is declared in `world.json`'s own
    `flags` block - both because a rule that names an undeclared item or
    sets an undeclared flag is refused by the pack's own rules, and a
    fixture that was refused would prove nothing about the walk.
    """
    sections = copy.deepcopy(make_town_pack.SECTIONS)
    sections["cellar"]["warden"] = warden
    rules = copy.deepcopy(make_town_pack.RULES)
    flags = copy.deepcopy(make_town_pack.FLAGS)
    if sets:
        flag = delve.warden_flag(warden["id"], 0)
        flags[flag] = "the warden of the cellar has been answered"
        rules.append({"id": RULE_ID,
                      "when": {"picks-up": {"what": "pebble"}},
                      "then": [{"set": flag}], "once": True})
    pack = make_town_pack.build(tmp_path, sections=sections, rules=rules, **kwargs)
    world = json.loads((pack / "world.json").read_text(encoding="utf-8"))
    world["flags"] = flags
    (pack / "world.json").write_text(json.dumps(world), encoding="utf-8")
    return pack


def test_a_rule_warden_with_a_rule_to_set_its_flag_passes_the_walk(tmp_path):
    pack = _rule_pack(tmp_path, {"family": "cellar-boss", "id": "the-old-king",
                                 "challenge": "rule"})
    assert locks.progress_findings(pack) == []
    assert validate(load_pack(pack), pack_dir=pack) == []


def test_a_rule_warden_with_no_rule_to_set_its_flag_is_one_sentence(tmp_path):
    pack = _rule_pack(tmp_path, {"family": "cellar-boss", "id": "the-old-king",
                                 "challenge": "rule"}, sets=False)
    assert locks.progress_findings(pack) == [
        "section cellar: the warden 'the-old-king' takes challenge 'rule' "
        "and no rule sets the flag 'warden:the-old-king:c0' that completes "
        "it, so nothing can ever pass it"]


def test_the_missing_rule_is_named_once_and_the_rest_of_the_walk_carries_on(tmp_path):
    """One fact, one sentence: the note is still read and the story still
    ends, so the walk does not say those are broken as well."""
    pack = _rule_pack(tmp_path, {"family": "cellar-boss", "id": "the-old-king",
                                 "challenge": "rule"}, sets=False)
    assert len(locks.progress_findings(pack)) == 1


def test_a_defeat_warden_is_still_beaten_by_the_walk_and_asked_for_nothing(tmp_path):
    pack = make_town_pack.build(tmp_path)
    assert locks.progress_findings(pack) == []
    listed = delve.descent_of(load_pack(pack), pack)["sections"]
    assert [delve.warden_challenge(delve.warden_of(s)) for s in listed] == \
        ["defeat", "defeat"]


def test_the_rule_wardens_own_flag_reaches_the_story_and_the_gate(tmp_path):
    """The flag a rule sets is the flag everything else already reads: the
    vault door (`vault.flag`) and the town gate do not change, because they
    never looked at anything but the flag."""
    pack = _rule_pack(tmp_path, {"family": "cellar-boss", "id": "the-old-king",
                                 "challenge": "rule"})
    listed = delve.descent_of(load_pack(pack), pack)["sections"]
    plan = delve.floor_plan({**delve.descent_of(load_pack(pack), pack),
                             "stamps": make_town_pack.stamp_records(pack)}, 3)
    assert plan["warden"]["flag"] == "warden:the-old-king:c0"
    assert plan["vault"]["flag"] == plan["warden"]["flag"]
    assert delve.town_seen_flag(listed[0]["id"], 0) == "town-seen:cellar:c0"


def test_the_walk_finds_the_missing_rule_where_the_author_looks(tmp_path):
    """The sentence at the door itself: `vefr check` prints these findings
    and exits non-zero on them."""
    import contextlib
    import io
    import types
    from vefr import cli as cli_mod

    def check(pack):
        buf = io.StringIO()
        args = types.SimpleNamespace(map_cmd="validate", pack=str(pack))
        with contextlib.redirect_stdout(buf):
            code = cli_mod.cmd_map(args)
        return code, buf.getvalue()

    good = _rule_pack(tmp_path / "good", {"family": "cellar-boss",
                                          "id": "the-old-king",
                                          "challenge": "rule"})
    code, out = check(good)
    assert code == cli.EXIT_OK, out

    bad = _rule_pack(tmp_path / "bad", {"family": "cellar-boss",
                                        "id": "the-old-king",
                                        "challenge": "rule"}, sets=False)
    code, out = check(bad)
    assert code == cli_mod.EXIT_ERROR, out
    assert "takes challenge 'rule' and no rule sets the flag" in out, out


# ---- the drops a warden's own family hands over ---------------------------

def _drop_pack(where, drops):
    """A real pack directory: the catalog, the Blueprint and one Section
    whose warden is a family of its own, outside its spawning list as the
    town fixture's is. The checks are asked of the pack, not of the helper,
    because a check nothing calls is not a check."""
    (where / "sections").mkdir(parents=True)
    (where / "world.json").write_text(json.dumps(
        {"items": {"pebble": {"name": "a grey pebble"}}}))
    defaults = {"name": "a grey rat", "hp": 1, "atk": 1, "sight": 5}
    (where / "blueprint.json").write_text(json.dumps({
        "blueprint": 1,
        "families": {"rat": {"defaults": {**defaults, "drops": ["pebble"]}},
                     "cellar-boss": {"defaults": {**defaults, "drops": drops}}},
        "regions": {}}))
    section = copy.deepcopy(make_town_pack.SECTIONS["cellar"])
    section["warden"] = {"family": "cellar-boss"}
    (where / "sections" / "cellar.json").write_text(json.dumps(section, indent=2))
    return where.resolve()


def test_a_warden_whose_family_drops_nothing_declared_is_refused(tmp_path):
    """D114's rule, on the last of the four drop surfaces: the warden's
    drops are its family's `drops` (delve draws them exactly as it draws
    every other monster's), and a drop the bag refuses is a drop that was
    never there."""
    bad = _drop_pack(tmp_path / "bad", ["brass-key"])
    assert maplab.section_errors(bad) == [
        "sections/cellar.json: /warden/family the warden drops 'brass-key', "
        "which is not an item world.json declares - the bag will refuse it"]
    good = _drop_pack(tmp_path / "good", ["pebble"])
    assert maplab.section_errors(good) == []


def test_a_pack_with_no_catalog_is_checked_and_not_refused(tmp_path):
    section = {"id": "c", "warden": {"family": "rat"}}
    bare = _drop_pack(tmp_path / "bare", ["brass-key"])
    assert maplab._warden_drop_errors(bare, section, "s") == []
    (bare / "world.json").write_text("{ not json")
    assert maplab._warden_drop_errors(bare, section, "s") == []


def test_a_section_with_no_warden_family_is_not_asked_about_drops(tmp_path):
    pack = _drop_pack(tmp_path / "quiet", ["brass-key"])
    assert maplab._warden_drop_errors(
        pack, {"id": "c", "warden": {"family": "ghost"}}, "s") == []
    assert maplab._warden_drop_errors(pack, {"id": "c"}, "s") == []


def test_a_drop_the_pack_declares_with_no_name_is_still_no_item(tmp_path):
    """`weave` bakes only what has a name and `bagAdd` refuses the rest, so
    an id under a nameless entry is an id no drop can hand over."""
    where = _drop_pack(tmp_path / "nameless", ["brass-key"])
    world = json.loads((where / "world.json").read_text(encoding="utf-8"))
    world["items"]["brass-key"] = {"sprite": "key"}
    (where / "world.json").write_text(json.dumps(world), encoding="utf-8")
    said = maplab.section_errors(where)
    assert len(said) == 1 and "brass-key" in said[0], said


def test_vefr_check_names_the_wardens_own_drop_too(tmp_path):
    """The same sentence at the door the author is standing at: `vefr check`
    prints these and exits non-zero. The pack is the town fixture with a
    Blueprint beside it, because that is the shape a descent pack has."""
    import contextlib
    import io
    import types
    from vefr import cli as cli_mod

    pack = make_town_pack.build(tmp_path)
    sections = copy.deepcopy(make_town_pack.SECTIONS)
    sections["cellar"]["warden"] = {"family": "rat"}
    (pack / "sections" / "cellar.json").write_text(json.dumps(sections["cellar"],
                                                             indent=2))
    (pack / "blueprint.json").write_text(json.dumps({
        "blueprint": 1,
        "families": {"rat": {"defaults": {"name": "a grey rat", "hp": 1,
                                          "atk": 1, "sight": 5,
                                          "drops": ["brass-key"]}}},
        "regions": {}}))
    buf = io.StringIO()
    args = types.SimpleNamespace(map_cmd="validate", pack=str(pack))
    with contextlib.redirect_stdout(buf):
        code = cli_mod.cmd_map(args)
    assert code == cli_mod.EXIT_ERROR
    assert "the warden drops 'brass-key'" in buf.getvalue()


# ---- Amendment 1 §5, the two cases E8c had already landed -----------------

def test_a_list_form_town_states_loads_each_region_on_its_own(tmp_path):
    """Amendment 1 §5, fourth bullet - the list form of `town_states` was
    E8c's and this is its own pin: two regions, two blocks, each loading
    its own last true state while the other keeps its own face."""
    pack = make_town_pack.build(tmp_path)
    blocks = delve.town_states_of(load_pack(pack))
    assert [b["region"] for b in blocks] == ["town", "tavern"]
    read = {"vault-1-read": True}
    # The tavern's one state is true and the town's first is true too: each
    # region answers for itself, and the tavern is unchanged by the town.
    assert delve.town_state_of(blocks, "town", read) == "town-act-2"
    assert delve.town_state_of(blocks, "tavern", read) == "tavern"
    # A third region with no block at all keeps its own face.
    assert delve.town_state_of(blocks, "cellar-entrance", read) == "cellar-entrance"


def test_a_story_end_a_rule_sets_on_entering_a_region_ends_the_story_with_no_boss(tmp_path):
    """Amendment 1 §5, last bullet - Cottage's ending. No vault note
    records the flag and no rule slays a king: the pack reaches a quiet
    room, a rule sets the flag on entering it, and the walk says the story
    can be finished. The endless board itself is phase 6's own slice; what
    this engine owes today is the flag and the walk."""
    pack = make_town_pack.build(
        tmp_path, story_end="the-quiet-room-is-reached",
        rules=make_town_pack.RULES + [{
            "id": "arriving-ends-it",
            "when": {"enters": {"place": "town"}},
            "then": [{"set": "the-quiet-room-is-reached"}], "once": True}])
    listed = delve.descent_of(load_pack(pack), pack)["sections"]
    # No boss anywhere: no Section's note records the flag, and the pack
    # names no `king-slain` at all.
    assert delve.story_end_of(load_pack(pack)["descent"]) == \
        "the-quiet-room-is-reached"
    assert "the-quiet-room-is-reached" not in delve.vault_flags_of(listed)
    assert locks._rule_setters(load_pack(pack)) == {
        "vault-1-read", "king-slain", "the-quiet-room-is-reached"}
    assert locks.progress_findings(pack) == []


# ---- nothing today changes ------------------------------------------------

# The bytes a pack contributes to its own weave, pinned. `web/packaged.html`
# is woven into every pack, so the whole-document digest in
# tests/test_skin_validator.py moves whenever the player does; this line is
# the pack's own half - the descent block and every Section in it - and it
# moved for nothing in this slice. E8d measured 467fecd4... on its own branch,
# but the stack was then rebased onto a main that had gained S349: that slice
# bakes an empty `"section_tiles": {}` into every descent, so the merged tree's
# own bytes were already fa71190... before E8d, and 467fecd4... is the value of
# the pre-S349 base the stack predates. Re-measured on the merged tree's town
# fixture pack (two Sections, two wardens, none of them naming a challenge):
#   fa7119034df3e3920be40aeff01bce0336626dde512a5f0ed0f101f7caed5ed4
# Moved again 2026-10-11, repairing the V352S re-cut: with vefr#346 in, `vefr
# check` runs the stamp sweep, and the town fixture's own `throne-hall` - a
# required landmark 21 wide and 21 tall - is too big for the 48x36 floors its
# Sections declare (a required room has to be a third of the small side or
# smaller). The stamp was shrunk to 11x9 in tests/fixtures/stamps, and the
# descent block a pack bakes carries its stamp records, so the fixture pack's
# own bytes moved with it. Nothing the warden keys contribute moved: the two
# Sections, their wardens and every `challenge` reading are the same bytes.
# Re-measured twice on the merged tree's town fixture pack, readings equal:
#   ee38bcbc25bc82b2ac4cde9667b14c3e374eb5be4f3e3648d19a333bec8020c1
#   ee38bcbc25bc82b2ac4cde9667b14c3e374eb5be4f3e3648d19a333bec8020c1
BAKED_DESCENT_SHA256 = \
    "ee38bcbc25bc82b2ac4cde9667b14c3e374eb5be4f3e3648d19a333bec8020c1"


def _baked_descent_line(html):
    line = re.search(r"^window\.VEFR_DESCENT_DEF = .*;$", html, re.M)
    assert line is not None, "the weave bakes no descent block"
    return line.group(0)


def test_a_pack_naming_none_of_the_three_keys_bakes_the_same_bytes(tmp_path):
    """The compatibility sentence, proved by digest: `challenge` defaults
    to `defeat`, `yields` and `fightable` to no and yes, so the descent
    block a pack contributes is byte for byte the one it contributed
    before Amendment 1."""
    pack = make_town_pack.build(tmp_path)
    line = _baked_descent_line(cli.weave_html(pack))
    assert hashlib.sha256(line.encode()).hexdigest() == BAKED_DESCENT_SHA256
    # And the pack really does name two wardens, neither of them naming a
    # challenge - a pin of nothing proves nothing.
    assert line.count('"warden":') == 2 and line.count("challenge") == 0


def test_the_two_shipped_packs_are_untouched():
    assert locks.progress_findings(SAMPLE) == []
    assert locks.section_findings(SAMPLE) == []
    assert validate(load_pack(SAMPLE), pack_dir=SAMPLE) == []
    assert "descent" not in load_pack(SAMPLE)


# ---- in the woven player (jsdom; skipped without node) --------------------

play_only = pytest.mark.skipif(shutil.which("node") is None,
                               reason="node not installed")


def _down_to(depth, descent):
    steps = ["begin", _go(TOWN, TOWN_HERO, descent["entry"]["at"]),
             "click:#interact", "wait:150"]
    for d in range(1, depth):
        plan = delve.floor_plan(descent, d)
        steps += [_go(plan, plan["anchors"]["up"], plan["anchors"]["down"]),
                  "click:#interact", "wait:150"]
    return steps


def _fight_to_the_warden(tmp_path, descent, warden, patch):
    """The whole walk to the warden floor and the bump that reaches it,
    with the harness's window onto the fight read back.

    `play_kit.play` rather than the shared `_play`, because this asks for
    its own reads: the fight is read off `VEFR_COMBAT`, which is where
    `alive`, `yields` and the mind state are published.
    """
    import play_kit

    plan = delve.floor_plan(descent, 3)
    steps = _down_to(3, descent) + [_go_fight(plan, warden)] + ["wait:100"] * 6
    html = play_kit.weave(play_kit.pack(tmp_path, "descent", patch=patch),
                          tmp_path)
    played = play_kit.play(html, {
        "steps": steps,
        "read": ["VEFR_COMBAT.region", "VEFR_COMBAT.enemies",
                 "VEFR_COMBAT.minds", "VEFR_DESCENT.doc", "store"]})
    assert played["errors"] == [], played["errors"]
    assert played["reads"]["VEFR_COMBAT.region"] == plan["name"]
    live = played["reads"]["VEFR_COMBAT.enemies"]
    (there,) = [e for e in live if e["id"] == "w"]
    return played, there


@play_only
def test_a_yields_warden_stays_on_its_anchor_after_defeat(tmp_path):
    """Amendment 1 §5, second bullet, in the player that draws it."""
    descent = _descent({"family": FAMILY, "carries": "cellar-key",
                        "yields": True}, families=[])
    patch = {"world.json": {"descent": descent,
                            "items": {"cellar-key": {"name": "a wax key",
                                                     "keep": True}}}}
    plan = delve.floor_plan(descent, 3)
    (warden,) = _wardens(plan)
    fought, there = _fight_to_the_warden(tmp_path, descent, warden, patch)
    # It fell, it is no longer a living hazard, and it is still there.
    assert there["alive"] is False, there
    assert there["yields"] is True, there
    assert there["at"] == plan["anchors"]["warden"], there
    assert _doc(fought)["flags"].get(plan["warden"]["flag"]) is True


@play_only
def test_a_warden_that_does_not_yield_is_gone_after_defeat(tmp_path):
    """The other half of the same sentence: without `yields` a beaten
    warden still vanishes, and this is the control that says the test
    above is about the key."""
    descent = _descent({"family": FAMILY}, families=[])
    patch = {"world.json": {"descent": descent}}
    plan = delve.floor_plan(descent, 3)
    (warden,) = _wardens(plan)
    fought, there = _fight_to_the_warden(tmp_path, descent, warden, patch)
    assert there["alive"] is False and there["yields"] is False, there
    assert _doc(fought)["flags"].get(plan["warden"]["flag"]) is True


@play_only
def test_a_fightable_false_warden_cannot_be_attacked(tmp_path):
    """Amendment 1 §5, third bullet. The blow lands on nothing."""
    descent = _descent({"family": FAMILY, "challenge": "rule",
                        "fightable": False}, families=[])
    patch = {"world.json": {"descent": descent}}
    plan = delve.floor_plan(descent, 3)
    (warden,) = _wardens(plan)
    fought, there = _fight_to_the_warden(tmp_path, descent, warden, patch)
    assert there["hp"] == warden["hp"], there      # no damage landed
    assert _doc(fought)["flags"].get(plan["warden"]["flag"]) is None


@play_only
def test_a_warden_that_cannot_be_struck_still_hunts(tmp_path):
    """Scope, ADR 0014: `fightable: false` takes the blow away and nothing
    else. The warden still wakes and comes, so the hall is still a hall."""
    descent = _descent({"family": FAMILY, "challenge": "rule",
                        "fightable": False}, families=[])
    patch = {"world.json": {"descent": descent}}
    plan = delve.floor_plan(descent, 3)
    (warden,) = _wardens(plan)
    fought, there = _fight_to_the_warden(tmp_path, descent, warden, patch)
    assert there["alive"] is True, there
    assert there["atk"] >= 1, there
    # It woke and it came: the warden is never asleep (ADR 0015), and it
    # closed the distance towards the hero rather than standing on its
    # anchor while the player walked up to it.
    minds = fought["reads"]["VEFR_COMBAT.minds"]
    (mind,) = [m for m in minds if m["id"] == "w"]
    assert mind["awake"] is True, mind
    assert there["at"] != plan["anchors"]["warden"], there


@play_only
def test_a_rule_that_sets_a_rule_wardens_flag_hands_over_its_key(tmp_path):
    """Amendment 1 §2: the moment the flag is set, the key goes into the
    bag with a line, the same as on death.

    The rule fires on `starts`, which is the one event a play session
    always raises, so the whole seam is proved without a floor walk: the
    rules engine sets the flag, `performRuleAction` asks the descent, and
    the key lands in the bag.
    """
    key = "cellar-key"
    descent = _descent({"family": FAMILY, "id": "the-old-king",
                        "challenge": "rule", "carries": key}, families=[])
    flag = delve.warden_flag("the-old-king", 0)
    patch = {"world.json": {"descent": descent,
                            "items": {key: {"name": "a wax key", "keep": True}},
                            "flags": {flag: "the old king has been answered"},
                            "rules": [{"id": "answered", "when": {"starts": {}},
                                       "then": [{"set": flag}], "once": True}]}}
    played = _play(tmp_path, ["begin", "wait:400"], patch=patch)
    assert played["errors"] == [], played["errors"]
    assert key in json.loads(played["store"].get("vefr-bag-descent-test") or "[]")
    assert _doc(played)["flags"].get(flag) is True


@play_only
def test_a_rule_warden_is_not_passed_by_killing_it(tmp_path):
    """The other half of §2's `rule`: the flag is a pack rule's to set, so
    a warden that is killed anyway has still not been passed - and its key
    comes with the flag, not with the death."""
    key = "cellar-key"
    descent = _descent({"family": FAMILY, "id": "the-old-king",
                        "challenge": "rule", "carries": key}, families=[])
    patch = {"world.json": {"descent": descent,
                            "items": {key: {"name": "a wax key", "keep": True}}}}
    plan = delve.floor_plan(descent, 3)
    (warden,) = _wardens(plan)
    fought = _play(tmp_path, _down_to(3, descent) + [_go_fight(plan, warden)]
                   + ["wait:100"] * 6, patch=patch)
    assert fought["errors"] == [], fought["errors"]
    assert _doc(fought)["flags"].get("warden:the-old-king:c0") is None
    assert key not in json.loads(
        fought["store"].get("vefr-bag-descent-test") or "[]")
