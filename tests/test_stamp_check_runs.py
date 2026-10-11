"""`vefr check` runs the stamp check, so a room that never places is not green (vefr#346).

The reported bug: `vefr check` ran the shape checks and stopped, while the
gate that actually catches a room which never places - `vefr stamp check` -
was a separate command nobody had to run. So a pack could print `ok:` while
carrying a REQUIRED stamp that never places, and a room that never places is
a floor with no warden hall in it. The author found out in play.

Every fixture here is a REAL pack built the shipped way (`normalized_pack`,
which runs a real `vefr normalize`), carrying `stamps/` and `sections/`, and
every assertion is on the sentences `vefr check` prints and on its exit code.
The refusal is the plain sentence `stamps.sentence` already builds -
`stamp <id>: <what is wrong> <json pointer>` - which names the stamp and its
JSON pointer, and is not reworded here.

The three acceptance shapes, one each:

* a pack whose required stamp never places exits non-zero, naming the stamp;
* a pack whose stamps all place stays green, exactly as before;
* a pack with no `stamps/` at all is unaffected and says nothing.

And the fourth, which is the seam itself: the check reaches
`stamp_check.report`, the same call `vefr stamp check` makes, so the two
cannot drift. `test_the_check_reaches_the_same_call_the_standalone_gate_does`
pins that - it fails if the rule is copied into the CLI instead of called.

Run with:

    bash tests/run.sh tests/test_stamp_check_runs.py
"""

from __future__ import annotations

import inspect
import json
import re
import shutil
import sys
from types import SimpleNamespace

import pytest

import vefr.cli as cli
from blueprint_helpers import mk, normalized_pack, vefr

# ---- the stamps ----------------------------------------------------------
#
# Three required roles, each a 5x5 room with one door socket in its west
# wall, which is the shape rule `stamps.read_v1` enforces. Small on
# purpose: this file is about what the check SAYS, not how long it takes.

LANDMARK = {
    "stamp": 1, "id": "test-alcove", "role": "landmark", "tags": ["cellar"],
    "weight": 2, "poi": "the test alcove",
    "rows": ["#####", "#...#", "+....", "#...#", "#####"],
}
HALL = {
    "stamp": 1, "id": "test-hall", "role": "warden-hall", "tags": ["cellar"],
    "weight": 1,
    "rows": ["#####", "#...#", "+W..#", "#...#", "#####"],
    "legend": {"W": {"anchor": "warden"}},
}
VAULT = {
    "stamp": 1, "id": "test-vault", "role": "vault", "tags": ["cellar"],
    "weight": 1,
    "rows": ["#####", "#CNH#", "+...#", "#####", "#####"],
    "legend": {"C": {"anchor": "chest"}, "N": {"anchor": "note"},
               "H": {"anchor": "home"}},
}
GOOD_STAMPS = (LANDMARK, HALL, VAULT)

# The one Section they land on: 64x48 cellar floors, the size the fit rule
# and the placement sentence are both measured against.
GOOD_SECTION = {
    "section": 1, "id": "cellar", "floors": 2,
    "size": {"w": [64, 80], "h": [48, 56]}, "rooms": [12, 18],
    "families": [{"family": "beetle", "weight": 5}],
    "elites": {"per_floor": [1, 2], "affixes": ["broad", "quick"]},
    "groups": {"per_floor": [1, 2], "minions": [2, 3]},
    "pois": ["the drowned well"], "warden": "ashwing",
    "vault": "vault-cellar",
    "stamps": ["cellar", "any"],
}

# The affixes `GOOD_SECTION` names. A Section that names an affix the pack
# does not define is refused by the SHAPE check, so a stamp fixture that
# wants to prove the STAMP check is what failed has to define them.
GOOD_AFFIXES = [
    {"id": "broad", "label": "Broad {name}", "hp": 1.5, "atk": 1.0,
     "xp": 1.5, "scale": 1.3, "extra_drops": 1},
    {"id": "quick", "label": "Quick {name}", "sight": 1},
]

# The pack whose required room never places.
#
# Twelve rival landmarks join the three good stamps, and a floor has ONE
# landmark slot. The alcove is a required room, so it must place on every
# single floor - and with thirteen landmarks competing for one slot it
# places on a handful out of sixty-four. The room is legal, the Section is
# legal, every stamp is legal, and every floor is still drawn as v3: this
# pack does not fall back to v2 even once.
#
# That last part is the whole point of this fixture. `vefr check` already
# swept every Section (locks.section_findings), and that sweep is SILENT
# here - see `test_the_section_sweep_alone_misses_this_pack`, which asserts
# it, because a fixture the older sweep already caught would prove nothing
# about this fix. What catches it is the placement rate, which only the
# stamp check computes.
RIVAL_LANDMARKS = tuple(
    {"stamp": 1, "id": f"rival-{number:02d}", "role": "landmark",
     "tags": ["cellar"], "weight": 1, "poi": f"rival {number}",
     "rows": ["#####", "#...#", "+....", "#...#", "#####"]}
    for number in range(12)
)
CROWDED_STAMPS = GOOD_STAMPS + RIVAL_LANDMARKS

# The room that is on every floor but a few - the case a small sweep cannot
# see, and the reason the sweep is 200 seeds rather than 8.
#
# Exactly the good pack, with the alcove weighed 99 and ONE rival landmark
# weighed 1 against it. There is one landmark slot on a floor and the draw
# is by weight, so the alcove takes it on 99 of every 100 floors and the
# rival takes the rest. Nothing here is malformed: every room is a legal
# room, the weights are whole numbers of 0 or more, and the Section is the
# legal one from above. The pack simply has a required room that is not on
# every floor it is required for - which is the failure, in the exact shape
# the 100% bar exists to catch.
#
# The measured consequence, off this fixture and not asserted here: the
# room misses on check-58 and after, so the first eight seeds are clean and
# an 8-seed sweep says nothing at all. `0.99 ** 8 = 0.923`: a check that
# drew eight seeds would print `ok:` on 92 packs in 100 like this one. The
# seeds it takes to miss a 99% room 99% of the time is
# `ceil(log(0.01) / log(0.99)) = 459`, so 200 is the same order as the
# standalone gate and the two sweeps now sit at one confidence.
NEAR_MISS_RIVAL = {
    "stamp": 1, "id": "rival-00", "role": "landmark", "tags": ["cellar"],
    "weight": 1, "poi": "rival 0",
    "rows": ["#####", "#...#", "+....", "#...#", "#####"],
}
NEAR_MISS_STAMPS = (
    dict(LANDMARK, weight=99), HALL, VAULT, NEAR_MISS_RIVAL,
)

def a_pack(tmp_path, stamps=GOOD_STAMPS, section=None):
    """A real pack carrying `stamps/` and `sections/`, built the shipped way.

    `section` defaults to `GOOD_SECTION`; the base is a Blueprint pack that
    has been through a real `vefr normalize`, because a Section names its
    families by id and the family checks need one. Passing `stamps=None`
    builds the same pack with no `stamps/` directory at all, which is every
    pack in the tree today.
    """
    built = normalized_pack(tmp_path, blueprint=mk.STD_BLUEPRINT)
    (built / "affixes.json").write_text(
        json.dumps(GOOD_AFFIXES, indent=2) + "\n", encoding="utf-8")
    (built / "sections").mkdir(exist_ok=True)
    (built / "sections" / "cellar.json").write_text(
        json.dumps(GOOD_SECTION if section is None else section, indent=2) + "\n",
        encoding="utf-8")
    if stamps is not None:
        (built / "stamps").mkdir(exist_ok=True)
        for record in stamps:
            (built / "stamps" / f"{record['id']}.json").write_text(
                json.dumps(record) + "\n", encoding="utf-8")
    return built


def check(pack):
    """The real `vefr check` front door, in-process: the exit code and output."""
    class _Cap:
        def __init__(self):
            self.out = []

        def write(self, text):
            self.out.append(text)
            return len(text)

        def flush(self):
            pass

    cap, real = _Cap(), sys.stdout
    sys.stdout = cap
    try:
        code = cli.cmd_map(SimpleNamespace(map_cmd='validate', pack=str(pack),
                                           segments=None, force=False))
    except SystemExit as exc:
        code = exc.code
    finally:
        sys.stdout = real
    return code, ''.join(cap.out)


# ---- 1. a required room that never places is not green ------------------

def test_a_required_room_that_never_places_fails_the_check(tmp_path):
    """The bug, through the door.

    Nothing in this pack is malformed - every stamp is a legal room, the
    Section is a legal one, and every floor is still drawn as v3 - so every
    shape check passes and the ONLY thing wrong is that a required room is
    not on the floors it is required for. Before the fix this printed `ok:`
    and exited 0.
    """
    pack = a_pack(tmp_path, stamps=CROWDED_STAMPS)
    code, out = check(pack)
    assert code == cli.EXIT_ERROR, out


def test_the_geometry_line_still_says_the_geometry_passed(tmp_path):
    """The stamp check does not rewrite the shape check's own verdict. The
    pack's GEOMETRY is fine and maplab says so; the refusals come after,
    which is what makes it obvious that this is a placement problem and not
    a broken map."""
    pack = a_pack(tmp_path, stamps=CROWDED_STAMPS)
    _code, out = check(pack)
    assert 'geometry, reachability, voices all pass' in out, out


def test_the_section_sweep_alone_misses_this_pack(tmp_path):
    """Why this fixture and not an easier one.

    `vefr check` ALREADY swept every Section before this change
    (`locks.section_findings`, 200 seeds), and on this pack that sweep
    finds nothing at all - every floor is still v3. So a fixture the older
    sweep caught would have gone on being green and would prove nothing
    about the placement rate. This one is caught by the placement rate and
    by nothing else.
    """
    from vefr import locks
    pack = a_pack(tmp_path, stamps=CROWDED_STAMPS)
    assert locks.section_findings(pack) == []
    _code, out = check(pack)
    assert 'stamp test-alcove:' in out, (
        'the stamp check must be what catches this pack')


def test_the_refusal_names_the_stamp_that_never_places(tmp_path):
    pack = a_pack(tmp_path, stamps=CROWDED_STAMPS)
    code, out = check(pack)
    assert code == cli.EXIT_ERROR, out
    assert 'stamp test-alcove:' in out, out


def test_the_refusal_says_how_often_the_room_placed(tmp_path):
    """The share sentence, to the digits - the author's only handle on how
    rare a room became, and the reason it is that rare."""
    pack = a_pack(tmp_path, stamps=CROWDED_STAMPS)
    _code, out = check(pack)
    assert 'stamp test-alcove: placed on ' in out, out
    assert 'it needs 100%' in out, out
    # ...and the numbers, not a paraphrase of them.
    [share] = re.findall(r'stamp test-alcove: placed on (\d+) of (\d+)', out)
    assert share, out


def test_the_refusal_is_far_below_the_bar_the_room_needs(tmp_path):
    """A room that places on a handful of sixty-four floors is a room that
    is not there, which is what the check is for. Pinned as a rate rather
    than as an exact count so the sentence's wording stays free to change."""
    pack = a_pack(tmp_path, stamps=CROWDED_STAMPS)
    _code, out = check(pack)
    [placed, eligible] = re.findall(
        r'stamp test-alcove: placed on (\d+) of (\d+)', out)[0]
    assert int(placed) < int(eligible), (placed, eligible)


def test_the_refusal_carries_the_json_pointer(tmp_path):
    """The pointer says WHICH value to fix - here the room's `rows`."""
    pack = a_pack(tmp_path, stamps=CROWDED_STAMPS)
    _code, out = check(pack)
    line = [ln for ln in out.splitlines()
            if ln.startswith('stamp test-alcove:')][0]
    assert line.rstrip().endswith('/rows'), line


def test_each_broken_room_is_named_exactly_once(tmp_path):
    """One sentence per room, said once - so the crowded landmarks are
    named once each and not twice.

    The count is the pack's own: thirteen rooms compete for one landmark
    slot and each says one sentence. The warden hall and the vault are NOT
    among them - each is the only room of its role, each places on every
    floor, and a check that named them would be crying wolf.
    """
    pack = a_pack(tmp_path, stamps=CROWDED_STAMPS)
    code, out = check(pack)
    sentences = [ln for ln in out.splitlines() if ln.startswith('stamp ')]
    assert code == cli.EXIT_ERROR, out
    assert len(sentences) == len(RIVAL_LANDMARKS) + 1, out   # rivals + the alcove
    assert len(sentences) == len(set(sentences)), out
    for quiet in ('stamp test-hall:', 'stamp test-vault:'):
        assert not [ln for ln in sentences if ln.startswith(quiet)], out


def test_the_refusal_is_one_plain_sentence_on_its_own_line(tmp_path):
    """The shape every other rule in this path already speaks: one line,
    no nesting, no table, no `FAIL:` decoration of its own."""
    pack = a_pack(tmp_path, stamps=CROWDED_STAMPS)
    _code, out = check(pack)
    line = [ln for ln in out.splitlines()
            if ln.startswith('stamp test-alcove:')][0]
    assert line.startswith('stamp '), line
    assert not line.startswith('  '), line
    assert '\n' not in line


# ---- 2. a pack whose stamps all place stays green ------------------------

def test_a_pack_whose_stamps_all_place_stays_green(tmp_path):
    """The no-breaking-change half: a check that refuses its own good work
    would be worse than no check at all."""
    pack = a_pack(tmp_path)
    code, out = check(pack)
    assert code == cli.EXIT_OK, out
    assert 'ok:' in out, out


def test_a_green_stamp_pack_says_nothing_about_its_stamps(tmp_path):
    """`vefr check` speaks only when it is unhappy. `vefr stamp check` prints
    a header and a problem count on every run; `vefr check` does not, because
    its own `ok:` line is already the summary."""
    pack = a_pack(tmp_path)
    _code, out = check(pack)
    assert 'stamp check:' not in out, out
    assert 'problems' not in out, out


def test_the_shipped_sample_world_still_checks_ok():
    """The pack in the tree, unchanged: it ships no `stamps/`, so the new
    sweep is skipped before it costs anything."""
    code, out = vefr('check', '--pack', 'worlds/sample-world')
    assert code == 0, out
    assert 'ok:' in out, out


# ---- 3. a pack with no stamps is unaffected and says nothing -------------

def test_a_pack_with_no_stamps_directory_says_nothing(tmp_path):
    """Every pack in the tree today. The gate costs it nothing and prints
    nothing - not a header, not a count, not a usage line.

    The claim is measured on the findings, not on the word: a pack's own
    path can carry the word `stamp` (a tmp folder named after this very
    test), so `'stamp' not in out` would be unsatisfiable. What the gate
    would print if it ran is a finding - a line `stamp_check.report`
    builds, `stamp <id>: ...` - so that is what is asserted to be absent.
    Every other thing the word could have carried already has its own
    assertion in this file: the header and the count in
    `test_a_green_stamp_pack_says_nothing_about_its_stamps`, and the two
    usage lines in the two tests after this one."""
    pack = a_pack(tmp_path, stamps=None)
    code, out = check(pack)
    assert code == cli.EXIT_OK, out
    assert not [ln for ln in out.splitlines() if ln.startswith('stamp ')], out


def test_a_pack_with_no_stamps_is_not_given_the_usage_error(tmp_path):
    """`stamp_check.report` returns its USAGE code for "no stamps directory".
    Inside `vefr check` that is not a problem to report - it is a pack that
    does not have stamps - so it must not leak out as a refusal."""
    from vefr import stamp_check
    pack = a_pack(tmp_path, stamps=None)
    assert stamp_check.report(str(pack), seeds=1)[0] == stamp_check.USAGE
    code, out = check(pack)
    assert code == cli.EXIT_OK, out
    assert 'no stamps directory' not in out, out


def test_a_pack_with_stamps_but_no_sections_says_nothing(tmp_path):
    """The other half of USAGE. `stamps/` with no `sections/` is still no
    stamped room to place, so it is silent - the same answer as no stamps.

    The directory is REMOVED, not just emptied: an empty `sections/` is a
    legal pack that sweeps zero floors and is green, which is a different
    case and is not what this test is about.
    """

    from vefr import stamp_check
    pack = a_pack(tmp_path)
    shutil.rmtree(pack / 'sections')
    assert stamp_check.report(str(pack), seeds=1)[0] == stamp_check.USAGE
    code, out = check(pack)
    assert code == cli.EXIT_OK, out
    assert 'no sections directory' not in out, out


# ---- 4. the seam: one call site, so the two cannot drift -----------------

def test_the_check_reaches_the_same_call_the_standalone_gate_does(
        monkeypatch, tmp_path):
    """`cmd_map` calls `stamp_check.report`, the same function
    `cmd_stamp_check` calls. If the rule were copied into the CLI instead,
    the two would drift and this would stop seeing the call.

    That is the whole of #346's second half: the old gap was not that the
    rule was wrong, it was that the check and the gate were two places, and
    a pack could pass one and never be asked the other.
    """
    from vefr import stamp_check
    seen = []
    real = stamp_check.report

    def spy(pack, seeds=200):
        seen.append((str(pack), seeds))
        return real(pack, seeds=seeds)

    pack = a_pack(tmp_path)
    monkeypatch.setattr(stamp_check, 'report', spy)
    # Through the real `vefr check`, not through the helper: the point is
    # that the CHECK reaches the call, so calling the helper directly would
    # pass even with the wiring deleted.
    check(pack)
    assert seen, 'vefr check did not reach stamp_check.report'
    assert seen[0][1] == cli.CHECK_STAMP_SEEDS, seen


def test_the_standalone_gate_and_the_check_agree_on_a_bad_pack(tmp_path, capsys):
    """The two doors, one answer. Whatever `vefr stamp check` refuses here,
    `vefr check` refuses too - which is what stops a pack being green in one
    place and red in the other.

    The gate PRINTS its report and returns an exit code, so its sentences
    are read back off stdout; the check's are read the same way `check()`
    reads them. Both are the lines `stamp_check.report` built.
    """
    pack = a_pack(tmp_path, stamps=CROWDED_STAMPS)
    cli_code, cli_out = check(pack)
    gate_code = cli.cmd_stamp_check(
        SimpleNamespace(pack=str(pack), seeds=cli.CHECK_STAMP_SEEDS))
    gate_out = capsys.readouterr().out
    assert cli_code == cli.EXIT_ERROR
    assert gate_code == cli.EXIT_ERROR
    shared = [ln for ln in gate_out.splitlines()
              if ln.startswith('stamp test-alcove:')]
    assert shared, gate_out
    for line in shared:
        assert line in cli_out.splitlines(), (line, cli_out)


def test_the_check_skips_the_sweep_entirely_for_a_pack_with_no_stamps(
        monkeypatch, tmp_path):
    """Not "it prints nothing" - it does not RUN. A pack with no `stamps/`
    pays no sweep at all, which is what keeps the change free for the
    99% of packs that have no stamped rooms."""
    from vefr import stamp_check

    def explode(*_a, **_k):
        raise AssertionError('the sweep ran for a pack with no stamps')

    monkeypatch.setattr(stamp_check, 'report', explode)
    # Through `vefr check`, so this holds for the path an author actually
    # runs rather than for a helper nothing else calls.
    code, out = check(a_pack(tmp_path, stamps=None))
    assert code == cli.EXIT_OK, out


def test_the_check_sweeps_two_hundred_seeds_and_not_eight():
    """The seed count is 200, and this is the test that says so out loud.

    It used to be 8, on the reasoning that the sweep is the slow half of a
    command that runs on every pack write. That reasoning is retired: the
    bar a required room clears is 100%, so a room placing on 99 of 100
    floors is ALREADY a failure, and `0.99 ** 8 = 0.923` means eight seeds
    miss it on 8 packs in 10. `NEAR_MISS_STAMPS` above is that room, and
    the two tests after it are what it does at each count.

    Pinned as a floor (`>= 200`) and as an equality with the standalone
    gate, so the constant cannot quietly drift back down to a sample that
    cannot see its own bar - and so if the gate's own default ever moves,
    the two are compared rather than diverged.
    """
    assert cli.CHECK_STAMP_SEEDS >= 200, (
        f'CHECK_STAMP_SEEDS is {cli.CHECK_STAMP_SEEDS}; a required room '
        f'placing on 99% of floors passes 8 seeds 92% of the time')
    assert cli.CHECK_STAMP_SEEDS == stamp_check_default_seeds(), (
        'the check and the standalone gate must sweep at one confidence')


def test_the_sweep_the_check_runs_is_two_hundred_seeds_wide(tmp_path):
    """Not "the constant says 200" - the floors really were laid.

    The refusal prints its own denominator: `placed on 248 of 1600 cellar
    floors`. One seed lays this pack's floors-per-seed - two depths and
    four floor kinds - so 1600 of them is 200 seeds and 64 of them is the
    8 this used to draw. Asserting the number the author's terminal
    actually shows is what makes this more than a restatement of the
    constant above.
    """
    depths = GOOD_SECTION["floors"]
    from vefr import delve_v3
    floors_per_seed = depths * len(delve_v3.FLOOR_KINDS)
    pack = a_pack(tmp_path, stamps=CROWDED_STAMPS)
    _code, out = check(pack)
    [placed, eligible] = re.findall(
        r'stamp test-alcove: placed on (\d+) of (\d+)', out)[0]
    assert int(eligible) == floors_per_seed * cli.CHECK_STAMP_SEEDS == 1600, (
        placed, eligible, floors_per_seed)


def test_a_room_on_99_of_100_floors_is_not_green(tmp_path):
    """The case eight seeds cannot see, caught through the real command.

    The good pack with the alcove weighed 99 against one rival weighed 1:
    a required room that is on nearly every floor and on no floor the hero
    may rely on. `vefr check` refuses it and names it.
    """
    pack = a_pack(tmp_path, stamps=NEAR_MISS_STAMPS)
    code, out = check(pack)
    assert code == cli.EXIT_ERROR, out
    assert 'stamp test-alcove: placed on ' in out, out
    [placed, eligible] = re.findall(
        r'stamp test-alcove: placed on (\d+) of (\d+)', out)[0]
    # Nearly every floor, and still a refusal - this is what 100% means.
    assert 0.9 < int(placed) / int(eligible) < 1.0, (placed, eligible)


def test_that_same_room_says_nothing_over_eight_seeds(tmp_path):
    """Why the sweep is 200: the arithmetic, on a real pack.

    Seeds are `check-0`, `check-1`, ... so an eight-seed sweep is a strict
    PREFIX of the 200-seed one and can only see the first eight of them.
    This room misses on check-58 and later, so the prefix is clean and the
    eight-seed check prints nothing. That is the whole reason the constant
    moved: a green light wrong 8 times in 100 is worse than no light.

    Asserted on the behaviour at each count rather than left as prose, so
    if an edit to the pack, the placer or the seeds ever moved the first
    miss into the first eight, this test would say so instead of quietly
    going stale.
    """
    pack = a_pack(tmp_path, stamps=NEAR_MISS_STAMPS)
    assert not [f for f in cli._stamp_findings(pack, seeds=8)
                if f.startswith('stamp test-alcove')], (
        'the fixture no longer demonstrates the gap - move the weights')
    assert [f for f in cli._stamp_findings(pack, seeds=cli.CHECK_STAMP_SEEDS)
            if f.startswith('stamp test-alcove')], (
        '200 seeds must catch what 8 misses')


def stamp_check_default_seeds() -> int:
    """The default `vefr stamp check` sweeps. Read off the parser rather than
    written out here, so this cannot drift from the command it compares to."""
    source = inspect.getsource(cli)
    marker = "'--seeds', type=int, default="
    line = [ln for ln in source.splitlines() if marker in ln][0]
    return int(line.split('default=')[1].split(',')[0].strip())


def test_the_seeds_are_named_the_way_the_standalone_gate_names_them():
    """`check-<n>` is the name a report line is pasted into, and it is the
    same name both sweeps draw - so a floor that fails in one can be
    redrawn with the other."""
    from vefr import stamp_check, locks
    assert stamp_check.SEED_PREFIX == locks.SECTION_SEED_PREFIX == 'check-'


@pytest.mark.parametrize('seeds', [1, 2, 8])
def test_a_required_room_that_never_places_is_caught_at_every_seed_count(
        tmp_path, seeds):
    """The guarantee does not depend on the sample size. A room crowded off
    its slot places on almost none of the floors at one seed just as it
    does at eight - which is why the reported bug was caught at any count.
    It is NOT the same argument for a small default: a room on 99 of 100
    floors is a different animal, and `NEAR_MISS_STAMPS` is it.
    """
    pack = a_pack(tmp_path, stamps=CROWDED_STAMPS)
    findings = cli._stamp_findings(pack, seeds=seeds)
    assert [f for f in findings if f.startswith('stamp test-alcove:')], findings
    # ...and through the real command at the default the CLI actually uses.
    code, out = check(pack)
    assert code == cli.EXIT_ERROR, out