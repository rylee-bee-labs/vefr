"""ADR 0014, slice E7.1: the closed shapes behind elites and linked
groups, and `vefr.blueprint.resolve_family`.

What is frozen here, one golden sentence and one JSON pointer per
refusal, in the house style of the blueprint tests (`expected-error.txt`
line 1 is a sentence, line 2 a pointer; this file asserts both whole):

- `affixes.json` holds one list of affix records, closed on `id`,
  `label`, `hp`, `atk`, `xp`, `sight`, `scale`, `extra_drops`. `id` and
  `label` are required, and a label must carry the literal `{name}`. The
  three multipliers live in [1.0, 2.0] and `scale` in [1.0, 1.5], all in
  whole hundredths; `sight` and `extra_drops` are whole numbers in
  [0, 2]. `moves` is reserved and rejected as the unknown key it is
  today: it is a format-2 key, and this slice adds no format.
- a Section's `elites` block carries `per_floor` (`hi` at most 2) and
  `affixes`; both are required.
- a Section's `groups` block is closed on `per_floor` (`hi` at most 3),
  `minions` (1 to 3, so at most four members counting the leader),
  `leader` (`elite` or `normal`), `same_family`, `wake` (only `all`) and
  `leash` (3 to 12).
- the checks that span records: an affix id the pack does not define, a
  repeated affix id, a Section family the Blueprint does not have, a
  family that resolves without `hp` or without `atk`, and an
  elite-led group in a Section that names no affix.
- `resolve_family(source, family_id)`: the base record of one family,
  the merged defaults of its root-first chain, with the same three
  refusals `_resolve_family` raises (unknown family, cycle, unknown
  parent), each with a pointer.

Two boundaries this slice does not move, asserted here so a later one
cannot move them by accident:

1. **Blueprint stays at format 1.** `FIELD_KEYS` is unchanged, and
   `resolve_family` returns a record over that set and no other.
2. **The floor-level caps are not here.** 36 monsters, 2 lone elites,
   3 groups, 4 members per group and 1 elite-led group per 8 rooms
   belong to the generator and the property sweep (ADR 0014, "Pop
   stage"), not to the pack validator.

A note on the test vocabulary: every id below is neutral. Display names
are a pack's `label`, and Cozy affix names arrive with a sample pack in
a later slice, so nothing game-specific is written here.
"""

import pytest

from vefr import blueprint, shapes


# ------------------------------------------------------------------ helpers

AFFIX = shapes.BLOCKS['affix']
ELITES = shapes.BLOCKS['elites']
GROUPS = shapes.BLOCKS['groups']


def only(problems) -> shapes.Problem:
    """The one problem a value earns, or a failure naming what it earned."""
    assert len(problems) == 1, [p.sentence for p in problems]
    return problems[0]


def sentence_and_pointer(problems) -> tuple[str, str]:
    (problem,) = problems
    return problem.sentence, problem.pointer


def a_good_affix() -> dict:
    return {
        "id": "big",
        "label": "Big {name}",
        "hp": 1.5,
        "atk": 1.0,
        "xp": 1.25,
        "sight": 0,
        "scale": 1.3,
        "extra_drops": 1,
    }


def a_good_section() -> dict:
    return {
        "section": 1,
        "id": "cellar",
        "families": [{"family": "beast", "weight": 1}],
        "elites": {"per_floor": [1, 2], "affixes": ["big"]},
        "groups": {
            "per_floor": [1, 2],
            "minions": [2, 3],
            "leader": "elite",
            "same_family": True,
            "wake": "all",
            "leash": 6,
        },
    }


def a_good_blueprint() -> dict:
    return {
        "blueprint": 1,
        "families": {
            "beast": {"defaults": {"name": "beast", "hp": 3, "atk": 2, "xp": 1}},
            "wide-beast": {"extends": "beast", "defaults": {"hp": 6, "sight": 7}},
            # `thin` has an `atk` and no `hp`; `soft` has an `hp` and no
            # `atk`. One of each, so both halves of the rule are exercised.
            "thin": {"defaults": {"atk": 1}},
            "soft": {"defaults": {"hp": 2}},
            "loop": {"extends": "loop", "defaults": {"hp": 1}},
            "wandering": {"extends": "loop"},
            "widened": {"extends": "nowhere", "defaults": {"hp": 1}},
        },
        "regions": {},
    }


def resolver(source: dict):
    """A `resolve` for `check_section`: the base record, or None for a
    family the Blueprint does not have.

    `blueprint.resolve_family` refuses an unknown family rather than
    returning None, so the caller answers that half of the question
    itself. This is the wrapper every caller of `check_section` writes,
    and it is why `shapes` needs no import from `vefr`.
    """
    def resolve(family_id: str):
        if family_id not in (source.get("families") or {}):
            return None
        return blueprint.resolve_family(source, family_id)

    return resolve


# ------------------------------------------------------- the affix record

def test_a_good_affix_has_no_problems():
    assert shapes.check(AFFIX, a_good_affix()) == []


def test_only_id_and_label_are_required():
    """Every other field is optional, and a default is no change."""
    minimal = {"id": "plain", "label": "Plain {name}"}
    assert shapes.check(AFFIX, minimal) == []
    assert only(shapes.check(AFFIX, {"label": "Plain {name}"})) == shapes.Problem(
        'missing-key', '/affix/id',
        'affix must hold its id, such as {"id": "big", "label": "Big {name}"}')
    assert only(shapes.check(AFFIX, {"id": "plain"})) == shapes.Problem(
        'missing-key', '/affix/label',
        'affix must hold its label, such as {"id": "big", "label": "Big {name}"}')


def test_an_affix_that_is_not_an_object_says_what_an_affix_looks_like():
    assert sentence_and_pointer(shapes.check(AFFIX, ["big"])) == (
        'affix must be an object such as '
        '{"id": "big", "label": "Big {name}"}',
        '/affix')


def test_moves_is_an_unknown_key_today():
    """`moves` is a format-2 key. Nothing in this slice adds format 2, so
    an affix carrying it is refused as the unknown key it is."""
    assert sentence_and_pointer(
        shapes.check(AFFIX, dict(a_good_affix(), moves=1))) == (
        "affix has an unknown key 'moves'; it may only hold id, label, hp, "
        "atk, xp, sight, scale and extra_drops",
        '/affix/moves')


def test_any_other_unknown_key_is_refused_the_same_way():
    assert sentence_and_pointer(
        shapes.check(AFFIX, dict(a_good_affix(), inflicts="fire"))) == (
        "affix has an unknown key 'inflicts'; it may only hold id, label, hp, "
        "atk, xp, sight, scale and extra_drops",
        '/affix/inflicts')


def test_a_label_must_name_the_monster_it_names():
    assert sentence_and_pointer(
        shapes.check(AFFIX, dict(a_good_affix(), label="Big"))) == (
        'affix.label must name the monster as {name}',
        '/affix/label')


def test_a_multiplier_is_a_number():
    assert sentence_and_pointer(
        shapes.check(AFFIX, dict(a_good_affix(), hp="1.5"))) == (
        'affix.hp must be a number, such as 1.5',
        '/affix/hp')


def test_a_multiplier_is_in_whole_hundredths():
    assert sentence_and_pointer(
        shapes.check(AFFIX, dict(a_good_affix(), hp=1.234))) == (
        'affix.hp must be a whole number of hundredths, such as 1.25',
        '/affix/hp')


@pytest.mark.parametrize("key", ["hp", "atk", "xp"])
def test_a_multiplier_is_between_1_and_2(key):
    assert sentence_and_pointer(
        shapes.check(AFFIX, dict(a_good_affix(), **{key: 2.5}))) == (
        f'affix.{key} must be between 1.0 and 2.0',
        f'/affix/{key}')


@pytest.mark.parametrize("key", ["hp", "atk", "xp"])
def test_a_multiplier_below_one_is_refused(key):
    assert only(shapes.check(AFFIX, dict(a_good_affix(), **{key: 0.5}))).pointer \
        == f'/affix/{key}'


def test_scale_is_between_1_and_1_5():
    assert sentence_and_pointer(
        shapes.check(AFFIX, dict(a_good_affix(), scale=1.6))) == (
        'affix.scale must be between 1.0 and 1.5',
        '/affix/scale')
    # 1.55 is a whole number of hundredths and out of range, so it is
    # reported as the range it missed, not as a value it never was.
    assert sentence_and_pointer(
        shapes.check(AFFIX, dict(a_good_affix(), scale=1.55))) == (
        'affix.scale must be between 1.0 and 1.5',
        '/affix/scale')
    assert sentence_and_pointer(
        shapes.check(AFFIX, dict(a_good_affix(), scale=1.555))) == (
        'affix.scale must be a whole number of hundredths, such as 1.25',
        '/affix/scale')


@pytest.mark.parametrize("key", ["sight", "extra_drops"])
def test_sight_and_extra_drops_are_whole_numbers_in_0_to_2(key):
    assert sentence_and_pointer(
        shapes.check(AFFIX, dict(a_good_affix(), **{key: 3}))) == (
        f'affix.{key} must be between 0 and 2',
        f'/affix/{key}')
    assert sentence_and_pointer(
        shapes.check(AFFIX, dict(a_good_affix(), **{key: 1.5}))) == (
        f'affix.{key} must be a whole number',
        f'/affix/{key}')


def test_a_good_affix_may_carry_only_the_two_required_keys():
    plain = {"id": "plain", "label": "Plain {name}"}
    assert shapes.check(AFFIX, plain) == []
    assert shapes.check(ELITES, {"per_floor": [0, 2], "affixes": ["plain"]}) == []


# --------------------------------------------------------- the elites block

def test_a_good_elites_block_has_no_problems():
    assert shapes.check(ELITES, {"per_floor": [1, 2], "affixes": ["big"]}) == []


def test_elites_needs_both_its_keys():
    assert sentence_and_pointer(shapes.check(ELITES, {"affixes": ["big"]})) == (
        'elites must hold its per_floor, such as '
        '{"per_floor": [1, 2], "affixes": ["big"]}',
        '/elites/per_floor')
    assert sentence_and_pointer(shapes.check(ELITES, {"per_floor": [1, 2]})) == (
        'elites must hold its affixes, such as '
        '{"per_floor": [1, 2], "affixes": ["big"]}',
        '/elites/affixes')


def test_elites_is_a_block_of_an_object():
    assert sentence_and_pointer(shapes.check(ELITES, [1, 2])) == (
        'elites must be an object such as '
        '{"per_floor": [1, 2], "affixes": ["big"]}',
        '/elites')


def test_its_unknown_keys_are_refused():
    assert sentence_and_pointer(
        shapes.check(ELITES, {"per_floor": [1, 2], "affixes": ["big"],
                              "inflicts": "fire"})) == (
        "elites has an unknown key 'inflicts'; it may only hold per_floor "
        "and affixes",
        '/elites/inflicts')


def test_per_floor_is_a_pair_of_whole_numbers():
    assert sentence_and_pointer(
        shapes.check(ELITES, {"per_floor": "1, 2", "affixes": ["big"]})) == (
        'elites.per_floor must be a [lo, hi] pair of whole numbers, such as [1, 2]',
        '/elites/per_floor')
    assert sentence_and_pointer(
        shapes.check(ELITES, {"per_floor": [1, 2, 3], "affixes": ["big"]})) == (
        'elites.per_floor must be a [lo, hi] pair of whole numbers, such as [1, 2]',
        '/elites/per_floor')
    assert sentence_and_pointer(
        shapes.check(ELITES, {"per_floor": [1, 1.5], "affixes": ["big"]})) == (
        'elites.per_floor must be a [lo, hi] pair of whole numbers, such as [1, 2]',
        '/elites/per_floor')


def test_elites_per_floor_is_capped_at_two():
    assert sentence_and_pointer(
        shapes.check(ELITES, {"per_floor": [1, 3], "affixes": ["big"]})) == (
        'elites.per_floor[1] must be between 0 and 2',
        '/elites/per_floor/1')


def test_affixes_is_a_list_of_affix_ids():
    assert sentence_and_pointer(
        shapes.check(ELITES, {"per_floor": [1, 2], "affixes": "big"})) == (
        'elites.affixes must be a list of affix ids, such as ["big"]',
        '/elites/affixes')
    assert sentence_and_pointer(
        shapes.check(ELITES, {"per_floor": [1, 2], "affixes": [1]})) == (
        'elites.affixes[0] must be an affix id, such as "big"',
        '/elites/affixes/0')


# --------------------------------------------------------- the groups block

def test_a_good_groups_block_has_no_problems():
    assert shapes.check(GROUPS, a_good_section()["groups"]) == []


def test_the_minimum_groups_block_is_two_keys():
    """A pack writes what it draws; the rest has a default."""
    assert shapes.check(GROUPS, {"per_floor": [1, 2], "minions": [2, 3]}) == []


def test_groups_is_a_block_of_an_object():
    assert sentence_and_pointer(shapes.check(GROUPS, "one group")) == (
        'groups must be an object such as '
        '{"per_floor": [1, 2], "minions": [2, 3], "leader": "elite", '
        '"same_family": true, "wake": "all", "leash": 6}',
        '/groups')


def test_a_group_unknown_key_is_refused():
    assert sentence_and_pointer(
        shapes.check(GROUPS, {"per_floor": [1, 2], "minions": [2, 3],
                              "warden": "big"})) == (
        "groups has an unknown key 'warden'; it may only hold per_floor, "
        "minions, leader, same_family, wake and leash",
        '/groups/warden')


def test_per_floor_is_capped_at_three():
    assert sentence_and_pointer(
        shapes.check(GROUPS, {"per_floor": [1, 4], "minions": [2, 3]})) == (
        'groups.per_floor[1] must be between 0 and 3',
        '/groups/per_floor/1')


def test_a_group_has_at_least_one_minion_and_at_most_three():
    assert sentence_and_pointer(
        shapes.check(GROUPS, {"per_floor": [1, 2], "minions": [0, 3]})) == (
        'groups.minions[0] must be between 1 and 3',
        '/groups/minions/0')
    assert sentence_and_pointer(
        shapes.check(GROUPS, {"per_floor": [1, 2], "minions": [2, 4]})) == (
        'groups.minions[1] must be between 1 and 3',
        '/groups/minions/1')


def test_the_leader_is_an_elite_or_a_normal():
    assert sentence_and_pointer(
        shapes.check(GROUPS, {"per_floor": [1, 2], "minions": [2, 3],
                              "leader": "boss"})) == (
        'groups.leader must be "elite" or "normal"',
        '/groups/leader')


def test_same_family_is_a_yes_or_a_no():
    assert sentence_and_pointer(
        shapes.check(GROUPS, {"per_floor": [1, 2], "minions": [2, 3],
                              "same_family": "yes"})) == (
        'groups.same_family must be a yes or a no',
        '/groups/same_family')


def test_wake_is_all_and_nothing_else():
    """ADR 0014 freezes `wake` at `all`: waking one member wakes the rest,
    and a partial wake is a rule this slice does not have."""
    assert sentence_and_pointer(
        shapes.check(GROUPS, {"per_floor": [1, 2], "minions": [2, 3],
                              "wake": "some"})) == (
        'groups.wake must be "all"',
        '/groups/wake')


@pytest.mark.parametrize("leash", [2, 13])
def test_the_leash_is_between_three_and_twelve(leash):
    assert sentence_and_pointer(
        shapes.check(GROUPS, {"per_floor": [1, 2], "minions": [2, 3],
                              "leash": leash})) == (
        'groups.leash must be between 3 and 12',
        '/groups/leash')


# ------------------------------------------------------ the blocks in order

def test_the_emission_order_is_unknown_keys_then_table_order():
    """The order `shapes` froze: unknown keys in the value's own order,
    then each table key in table order."""
    problems = shapes.check(AFFIX, {
        "zeta": 1,
        "id": "big",
        "alpha": 2,
        "hp": 1.234,
        "scale": 1.6,
    })
    assert [(p.code, p.pointer) for p in problems] == [
        ("unknown-key", "/affix/zeta"),
        ("unknown-key", "/affix/alpha"),
        ("missing-key", "/affix/label"),
        ("not-hundredths", "/affix/hp"),
        ("out-of-range", "/affix/scale"),
    ]


def test_a_non_object_stops_at_one_problem():
    assert len(shapes.check(GROUPS, 7)) == 1


def test_the_three_blocks_are_in_the_table():
    assert {"affix", "elites", "groups"} <= set(shapes.BLOCKS)


def test_the_two_earlier_blocks_are_untouched():
    assert shapes.check(shapes.BLOCKS["saves"], {"rules": "persist"}) == []
    assert sentence_and_pointer(
        shapes.check(shapes.BLOCKS["saves"], {"extra": 1})) == (
        "saves has an unknown key 'extra'; it may only hold rules and legacy",
        '/saves/extra')
    assert sentence_and_pointer(shapes.check(shapes.BLOCKS["sound"], {})) == (
        'sound must hold a theme, such as {"theme": "soft"}',
        '/sound/theme')


# ---------------------------------------------------- the cross-record checks

def test_a_good_section_with_its_affixes_has_no_problems():
    source = a_good_blueprint()
    assert shapes.check_section(
        a_good_section(), [a_good_affix()], resolver(source)) == []


def test_an_affix_id_the_pack_does_not_define_is_refused():
    section = a_good_section()
    section["elites"]["affixes"] = ["big", "glowing"]
    assert sentence_and_pointer(shapes.check_section(
        section, [a_good_affix()], resolver(a_good_blueprint()))) == (
        "every affix a section names must be defined by the pack, and "
        "'glowing' is not",
        '/elites/affixes/1')


def test_a_repeated_affix_id_is_refused():
    twice = [a_good_affix(), dict(a_good_affix(), label="Wide {name}")]
    assert sentence_and_pointer(shapes.check_section(
        a_good_section(), twice, resolver(a_good_blueprint()))) == (
        "every affix id must be its own, and 'big' is used twice",
        '/affixes/1/id')


def test_a_repeated_affix_id_is_refused_away_from_its_neighbour():
    """The pair that collides need not be side by side.

    "Ids are unique" (ADR 0014, "Affix") is a claim about the whole
    list, so `[big, quick, big]` is as much a repeat as `[big, big]`
    is. A check that only compared each id with the one before it would
    call this list good and let two packs' elites draw the same record.
    The pointer is the second record that carries the id, so the pair
    that collides is named whichever distance apart they are.
    """
    apart = [a_good_affix(),
             dict(a_good_affix(), id="quick", label="Quick {name}"),
             dict(a_good_affix(), label="Wide {name}")]
    assert sentence_and_pointer(shapes.check_section(
        a_good_section(), apart, resolver(a_good_blueprint()))) == (
        "every affix id must be its own, and 'big' is used twice",
        '/affixes/2/id')


def test_a_family_the_blueprint_does_not_have_is_refused():
    section = a_good_section()
    section["families"] = [{"family": "beast", "weight": 1},
                           {"family": "ghost", "weight": 1}]
    assert sentence_and_pointer(shapes.check_section(
        section, [a_good_affix()], resolver(a_good_blueprint()))) == (
        "unknown family 'ghost'",
        '/families/1/family')


@pytest.mark.parametrize("family,missing", [("thin", "hp"), ("soft", "atk")])
def test_a_family_that_resolves_without_a_stat_is_refused(family, missing):
    """An elite is scaled from a base record, so a family with no `hp` or
    no `atk` has nothing to scale."""
    section = a_good_section()
    section["families"] = [{"family": family, "weight": 1}]
    (problem,) = shapes.check_section(
        section, [a_good_affix()], resolver(a_good_blueprint()))
    assert problem.pointer == '/families/0/family'
    assert problem.sentence == (
        f"every family a section names needs an {missing} in the blueprint, "
        f"and {family!r} has none")


def test_a_family_is_scaled_from_its_merged_record_not_its_own():
    """`wide-beast` names no `atk` of its own; the one it extends has it,
    and that merged record is what an elite is scaled from."""
    source = a_good_blueprint()
    assert blueprint.resolve_family(source, "wide-beast")["atk"] == 2
    section = a_good_section()
    section["families"] = [{"family": "wide-beast", "weight": 1}]
    assert shapes.check_section(
        section, [a_good_affix()], resolver(source)) == []


def test_an_elite_led_group_needs_an_affix_to_give_its_leader():
    section = a_good_section()
    section["elites"]["affixes"] = []
    assert sentence_and_pointer(shapes.check_section(
        section, [a_good_affix()], resolver(a_good_blueprint()))) == (
        "a group led by an elite needs at least one affix, and the section "
        "names none",
        '/groups/leader')


def test_a_normal_led_group_needs_no_affix():
    section = a_good_section()
    section["elites"]["affixes"] = []
    section["groups"]["leader"] = "normal"
    assert shapes.check_section(
        section, [a_good_affix()], resolver(a_good_blueprint())) == []


def test_a_section_that_names_no_elites_at_all_is_fine():
    section = a_good_section()
    del section["elites"]
    assert shapes.check_section(
        section, [a_good_affix()], resolver(a_good_blueprint())) == []


def test_the_cross_record_checks_stand_alone():
    """`check_affixes` is the affix half on its own, so a caller that only
    has the affix list and the Section's ids can ask."""
    problems = shapes.check_affixes(
        {"elites": {"per_floor": [1, 2], "affixes": ["glowing"]}},
        [a_good_affix()])
    assert sentence_and_pointer(problems) == (
        "every affix a section names must be defined by the pack, and "
        "'glowing' is not",
        '/elites/affixes/0')


def test_the_affix_list_itself_is_checked_one_record_at_a_time():
    problems = shapes.check_affixes(
        {"elites": {"per_floor": [1, 2], "affixes": ["big"]}},
        [a_good_affix(), {"id": "plain", "label": "Plain"}])
    assert sentence_and_pointer(problems) == (
        'affix.label must name the monster as {name}',
        '/affixes/1/label')


def test_an_affix_list_that_is_not_a_list_is_refused():
    assert sentence_and_pointer(shapes.check_affixes(
        {"elites": {"per_floor": [1, 2], "affixes": ["big"]}},
        {"big": a_good_affix()})) == (
        'affixes must be a list of affix records',
        '/affixes')


def test_the_section_blocks_are_checked_by_check_section_too():
    section = a_good_section()
    section["groups"]["leash"] = 40
    assert sentence_and_pointer(shapes.check_section(
        section, [a_good_affix()], resolver(a_good_blueprint()))) == (
        'groups.leash must be between 3 and 12',
        '/groups/leash')


def test_a_bad_affix_short_circuits_the_ids_it_would_otherwise_name():
    """A record that is not an object cannot have an id, so the pack's
    affix table is refused where it is wrong and the id checks wait."""
    problems = shapes.check_affixes(
        {"elites": {"per_floor": [1, 2], "affixes": ["big"]}}, ["big"])
    assert sentence_and_pointer(problems) == (
        'affix must be an object such as {"id": "big", "label": "Big {name}"}',
        '/affixes/0')


# ------------------------------------------------------------ resolve_family

def test_resolve_family_returns_the_merged_defaults_of_the_chain():
    source = a_good_blueprint()
    assert blueprint.resolve_family(source, "beast") == {
        "name": "beast", "hp": 3, "atk": 2, "xp": 1}
    assert blueprint.resolve_family(source, "wide-beast") == {
        "name": "beast", "hp": 6, "atk": 2, "xp": 1, "sight": 7}


def test_the_child_wins_whole_values():
    source = a_good_blueprint()
    assert blueprint.resolve_family(source, "wide-beast")["hp"] == 6


def test_the_record_is_over_the_closed_enemy_fields_and_nothing_else():
    """ADR 0014: Blueprint stays at format 1. `resolve_family` is how a
    Section pack reads a family, so it hands back exactly FIELD_KEYS."""
    # ADR 0021 added `guard`, `drop_chance` and `gold` to the closed set, and
    # ADR 0024 `skills`.
    assert blueprint.FIELD_KEYS == {
        "name", "sprite", "hp", "atk", "xp", "sight", "drops",
        "guard", "drop_chance", "gold", "skills"}
    record = blueprint.resolve_family(a_good_blueprint(), "wide-beast")
    assert set(record) <= blueprint.FIELD_KEYS


def test_the_returned_record_is_the_caller_s_to_mutate():
    """A caller that scales a record may not edit the Blueprint behind it."""
    source = a_good_blueprint()
    source["families"]["beast"]["defaults"]["drops"] = ["coin"]
    record = blueprint.resolve_family(source, "beast")
    record["drops"].append("gem")
    record["hp"] = 99
    assert source["families"]["beast"]["defaults"] == {
        "name": "beast", "hp": 3, "atk": 2, "xp": 1, "drops": ["coin"]}


def test_an_unknown_family_is_refused_with_its_pointer():
    with pytest.raises(blueprint.BlueprintError) as err:
        blueprint.resolve_family(a_good_blueprint(), "ghost")
    assert str(err.value) == "unknown family 'ghost'"
    assert err.value.pointer == "/families/ghost"


def test_a_self_cycle_names_the_family():
    with pytest.raises(blueprint.BlueprintError) as err:
        blueprint.resolve_family(a_good_blueprint(), "loop")
    assert str(err.value) == "family 'loop' extends itself (cycle)"
    assert err.value.pointer == "/families/loop"


def test_a_longer_cycle_names_the_family_table():
    with pytest.raises(blueprint.BlueprintError) as err:
        blueprint.resolve_family(a_good_blueprint(), "wandering")
    assert str(err.value) == "family inheritance has a cycle"
    assert err.value.pointer == "/families"


def test_an_unknown_parent_names_the_child_that_extends_it():
    with pytest.raises(blueprint.BlueprintError) as err:
        blueprint.resolve_family(a_good_blueprint(), "widened")
    assert str(err.value) == "unknown parent 'nowhere'"
    assert err.value.pointer == "/families/widened/extends"


def test_a_family_id_must_be_a_string():
    with pytest.raises(blueprint.BlueprintError) as err:
        blueprint.resolve_family(a_good_blueprint(), 3)
    assert str(err.value) == "a family id must be a string"
    assert err.value.pointer == "/families"


def test_a_source_that_is_not_an_object_is_refused():
    with pytest.raises(blueprint.BlueprintError) as err:
        blueprint.resolve_family([], "beast")
    assert str(err.value) == "blueprint must be a JSON object"
    assert err.value.pointer == ""


def test_a_families_table_that_is_not_an_object_is_refused():
    with pytest.raises(blueprint.BlueprintError) as err:
        blueprint.resolve_family({"families": []}, "beast")
    assert str(err.value) == "families must be an object"
    assert err.value.pointer == "/families"


def test_a_blueprint_with_no_families_has_no_family():
    with pytest.raises(blueprint.BlueprintError) as err:
        blueprint.resolve_family({"blueprint": 1, "regions": {}}, "beast")
    assert str(err.value) == "unknown family 'beast'"
    assert err.value.pointer == "/families/beast"


def test_reading_a_format_1_blueprint_still_expands_unchanged(tmp_path):
    """The additive promise: `resolve_family` is a new door, and the old
    ones still work."""
    from blueprint_helpers import mk

    pack = mk.build(tmp_path)
    source = mk.STD_BLUEPRINT
    assert blueprint.expand(blueprint.read_v1(source), pack_dir=pack)
    assert blueprint.plan(source, pack_dir=pack)[0]["act-1/cave-2"]["owns_enemies"]
    # The same family, read the new way, is the base record the old way
    # wrote into every record of that family.
    record = blueprint.resolve_family(source, "beetle")
    written = blueprint.expand(source, pack_dir=pack)["act-1/cave-2"][0]
    for key, value in record.items():
        assert written[key] == value
