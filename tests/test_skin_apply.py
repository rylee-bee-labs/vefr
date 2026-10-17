"""Skin loader, K2 (design/ui-skin.md "How it is drawn" and the Rules): the player paints the skin.

The REAL woven player is driven in jsdom (tests/fixtures/skin_apply_harness.mjs). A skinned game
gets one `<style id="vefr-skin-css">` built from the baked skin; a game with no skin gets nothing
and looks exactly as it did.

Interface slices 4 and 5 are here too: the nine parts a skin may carry and the player did not
draw, the five HUD icons, and the speech box's portrait.
"""

import copy
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from vefr import cli

sys.path.insert(0, str(Path(__file__).parent / "fixtures"))
import make_skin_pack as mk  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(Path(__file__).parent))
from test_teal_contrast import contrast  # noqa: E402  (the WCAG maths, used as it is)

# ---- interface slices 4 and 5 ----
# The nine parts a skin may carry and the player does not draw, in the order
# design/ui-skin.md lists them. `mk.PARTS_SKIN` owns the parts, their picture
# keys and their sizes; every picture is its own solid colour, so "this rule
# carries the slot picture" is a string test and not a guess at a shape.
NEW_PARTS = ("slot", "tab", "toggle", "tooltip", "speech",
             "divider", "banner", "corner", "gold-plate")
GUARD = "@media (prefers-contrast: no-preference) and (not (forced-colors: active))"
PLAYER_CSS = (ROOT / "web" / "player" / "parts" / "020-style.css").read_text(encoding="utf-8")
# The five HUD words an icon sits beside, and what each icon is called.
ICONS = ("heart", "star", "coin", "bag", "door")
# Anything the player's own sheet treats as a control. A skin may not set a
# size below the 44 px floor on one of these (the picture can be smaller than
# its hit area, the hit area may not).
CONTROLS = ("button", ".cta", ".gbtn", "input", "select", "textarea",
            "toggle", 'role="button"')


@pytest.fixture(scope="module")
def ran(tmp_path_factory):
    if shutil.which("node") is None:
        pytest.skip("node not installed")
    home = tmp_path_factory.mktemp("skin-apply")
    skinned, plain = home / "skinned.html", home / "plain.html"
    dressed, contrast = home / "dressed.html", home / "contrast.html"
    skinned.write_text(cli.weave_html(mk.build(home, name="skin-plain")), encoding="utf-8")
    plain.write_text(cli.weave_html(ROOT / "worlds" / "sample-world"), encoding="utf-8")
    dressed.write_text(cli.weave_html(mk.build(home, skin=_dressed_skin(), files=_dressed_files(),
                                              name="skin-dressed")), encoding="utf-8")
    contrast.write_text(dressed.read_text(encoding="utf-8"), encoding="utf-8")
    # every part the skin contract names: the four already drawn, plus the nine
    # of interface slice 4.
    parts = home / "parts.html"
    parts.write_text(cli.weave_html(mk.build_parts(home)), encoding="utf-8")
    # a second pack wearing a second skin (#503): the swap proof.
    second = home / "second.html"
    second.write_text(cli.weave_html(mk.build_second(home)), encoding="utf-8")
    run = subprocess.run(["node", str(ROOT / "tests/fixtures/skin_apply_harness.mjs"),
                          "skinned", str(skinned), "plain", str(plain),
                          "dressed", str(dressed), "contrast", str(contrast),
                          "parts", str(parts), "second", str(second)],
                         capture_output=True, text=True, timeout=300)
    assert run.returncode == 0, run.stderr + run.stdout
    return json.loads(run.stdout)


def _dressed_skin():
    """The same test skin plus the two optional parts of the in-world
    interface: a backdrop (the ground outside the map) and a font choice."""
    skin = copy.deepcopy(mk.SKIN)
    skin["backdrop"] = "table.png"
    skin["fonts"] = {"display": "Cinzel", "body": "Crimson Pro"}
    return skin


def _dressed_files():
    return dict(mk.FILES, **{"table.png": (128, 128)})


def test_a_skinned_game_gets_one_style_element(ran):
    s = ran["skinned"]
    assert s["hasStyle"] is True
    assert "has-skin" in (s["bodyClass"] + " " + s["htmlClass"])


def test_the_css_paints_panels_buttons_bars_and_the_cursor_from_the_pictures(ran):
    css = ran["skinned"]["css"]
    assert "border-image" in css and "url(data:image/png;base64," in css
    assert ".glass" in css and ".gbtn" in css                       # the player's panel and button
    assert "cursor:" in css.replace(" :", ":")                      # the skin's cursor part


def test_a_skin_never_removes_focus_or_shrinks_targets(ran):
    css = ran["skinned"]["css"]
    assert "outline: none" not in css and "outline:none" not in css
    assert "min-height: 44px" in css or "min-height:44px" in css


def test_high_contrast_and_forced_colors_fall_back_to_the_plain_style(ran):
    css = ran["skinned"]["css"]
    assert "prefers-contrast" in css and "forced-colors" in css


def test_text_is_never_inside_a_picture(ran):
    assert ran["skinned"]["imgsWithText"] == 0
    assert "content: url(" not in ran["skinned"]["css"]            # no picture used as text


def test_no_skin_means_no_change(ran):
    p = ran["plain"]
    assert p["hasStyle"] is False and p["css"] == ""
    assert "has-skin" not in (p["bodyClass"] + " " + p["htmlClass"])


def test_the_ink_reaches_text_inside_panels_and_buttons_stay_readable(ran):
    """Measured on Cottage's real skin before this fix: the reader's body text was cream on
    parchment (1.4:1) and the health label gold on parchment (1.2:1), because only the panel
    itself took the ink. Text inside a skinned panel now takes the ink; buttons get light text."""
    css = ran["skinned"]["css"]
    assert "#2B2118 !important" in css                   # the test skin's on_panel ink
    assert ":not(button, button *, .cta, .cta *, .gbtn, .gbtn *, kbd)" in css
    assert "color: #F6F0E2 !important" in css            # light text on the wooden button face


def test_a_panel_middle_is_flat_not_a_tiled_patch(ran):
    """A 32 px patch tiled across a wide panel showed as stripes behind the text (seen on the
    real Cottage skin). Panels keep only the carved border from the picture."""
    css = ran["skinned"]["css"]
    panel_rule = css[css.index(".glass, #npc-box"):]
    panel_rule = panel_rule[:panel_rule.index("}")]
    assert "var(--vefr-skin-ground," in panel_rule
    assert " fill " not in panel_rule                    # no tiled middle
    assert "#menu .carved" in css and "#menu .pm button" in css


def test_skinned_buttons_have_a_dark_base_under_the_picture(ran):
    """axe saw the gold Whisper button's own gold background under the wood (3.2:1 with the
    light text). A dark base keeps the text readable even with the picture missing."""
    assert "background-color: #5F5043 !important" in ran["skinned"]["css"]


# ---- the backdrop (docs/plans/interface/PLAN.md, slice 2) ----


def test_the_ground_outside_the_map_takes_the_skins_table(ran):
    """A skin with a backdrop paints it on the ground the map does not cover:
    the picture arrives as a data URI, and the map is redrawn when it decodes."""
    d = ran["dressed"]
    assert d["backdropUrl"].startswith("data:image/png;base64,")
    assert d["withPicture"]["ready"] is True
    assert d["withPicture"]["drawn"] > 0        # tiles of the table on the ground
    assert d["withPicture"]["bands"], "nothing was painted"
    # A picture that arrives after the first frame repaints the map by itself.
    assert d["hasRedraw"] is True


def test_the_ground_is_painted_only_where_the_map_is_not(ran):
    """The bands are the window minus the map's own rectangle, clipped to the
    window: ground on all four sides of a small map, and none at all when the
    map fills the window."""
    bands = ran["dressed"]["bands"]
    assert len(bands["smallMap"]) == 4
    assert bands["fullWindow"] == []
    map_x, map_y, map_w, map_h = 250, 180, 300, 240     # 800x600 window, map centred
    for x, y, w, h in bands["smallMap"]:
        overlap_x = max(0, min(x + w, map_x + map_w) - max(x, map_x))
        overlap_y = max(0, min(y + h, map_y + map_h) - max(y, map_y))
        assert overlap_x == 0 or overlap_y == 0, (x, y, w, h)


def test_the_backdrop_paints_only_when_the_picture_is_there(ran):
    """No picture, no painting: the bands are the flat ground exactly as before."""
    assert ran["dressed"]["withoutPicture"]["drawn"] == 0
    assert ran["dressed"]["withoutPicture"]["ready"] is False
    assert ran["dressed"]["bands"]["noPicture"] == []
    # A skin with no backdrop never even asks for one.
    assert ran["skinned"]["backdropUrl"] is None
    assert ran["skinned"]["withoutPicture"]["drawn"] == 0


def test_a_game_with_no_skin_keeps_todays_dark_ground(ran):
    """Even with a picture on the table, a pack with no skin paints the flat
    ground: the backdrop is a skin's, and only a skin's."""
    p = ran["plain"]
    assert p["backdropUrl"] is None
    assert p["withPicture"]["drawn"] == 0
    assert p["withPicture"]["ready"] is False
    assert p["hasStyle"] is False


def test_the_ground_is_never_asked_about_picture_only(ran):
    """A backdrop is a picture; every word in the game is still real text."""
    css = ran["dressed"]["css"]
    assert "content: url(" not in css
    assert ran["dressed"]["imgsWithText"] == 0


# ---- the type a skin chooses (docs/plans/interface/PLAN.md, slice 3) ----


def test_the_display_and_body_families_come_from_the_skin(ran):
    css = ran["dressed"]["css"]
    assert "--display: 'Cinzel', Georgia" in css
    assert "--read: 'Crimson Pro', Georgia" in css


def test_a_family_the_engine_does_not_bundle_is_never_asked_for(ran):
    """The player draws the three bundled families and nothing else, so a hand
    edited skin cannot name a typeface that would 404 into a fallback."""
    parts = (ROOT / "web" / "player" / "parts" / "540-the-skin.js").read_text(encoding="utf-8")
    stacks = re.search(r"var SKIN_FONT_STACKS = \{(.*?)\};", parts, re.S).group(1)
    assert set(re.findall(r"'([^']+)':", stacks)) == {"Cinzel", "Atkinson Hyperlegible Next", "Crimson Pro"}
    assert "--read:" not in ran["skinned"]["css"]    # a skin with no fonts keeps the player's own


def test_contrast_more_keeps_the_flat_ground_and_the_plain_type(ran):
    """`prefers-contrast: more` returns the plain flat style: no backdrop, and
    the skin's fonts inside the same media guard as the rest of the sheet."""
    c = ran["contrast"]
    assert c["backdropUrl"] is None
    assert c["withoutPicture"]["drawn"] == 0
    assert c["hasStyle"] is True and "prefers-contrast" in c["css"] and "forced-colors" in c["css"]

# ===========================================================================
# interface slice 4: the parts a skin may carry and the loader ignores today
#
# `maplab.SKIN_PARTS` accepts all nine and `cli._baked_skin` bakes their picture
# keys as data URIs; what is missing is that applySkin() writes no CSS for them.
# The `parts` page of the harness is a skin carrying every part: the four the
# player draws today plus these nine. The `skinned` page carries only the four,
# and is the negative control.
# ===========================================================================

def _rules(css):
    """(selector, body) for every rule inside the guard, a multi-line selector
    list kept whole and the guard's own block not mistaken for a rule."""
    text = css
    if GUARD in css:
        open_at = css.index("{", css.index(GUARD))
        text = css[open_at + 1:css.rindex("}")]
    return re.findall(r"([^{}]+)\{([^{}]*)\}", text)


def _guard_span(css):
    """The (first, last) offsets of the guard's own block."""
    open_at = css.index("{", css.index(GUARD))
    depth = 0
    for i in range(open_at, len(css)):
        if css[i] == "{":
            depth += 1
        elif css[i] == "}":
            depth -= 1
            if depth == 0:
                return open_at + 1, i
    return open_at + 1, len(css)


def _pictures():
    """Every one of the nine parts' pictures: (part, picture key, data URI).
    `slice` is a number, not a picture, so only the named files are listed."""
    return [(part, key, mk.picture_uri(fname))
            for part, spec in mk.PARTS_SKIN.items() for key, fname in spec.items()
            if isinstance(fname, str)]


def _drawn(css, part, key, *selector_groups, idiom=("border-image", "background")):
    """The rules that paint this part's own picture, onto the element the
    selector names, in one of the idioms the existing panel/button/bar rules use.

    Each group is the set of acceptable spellings for one thing the selector has
    to say (`".npc-box"` or `"#npc-box"`); every group has to match at least one.
    """
    uri = mk.picture_uri(mk.PARTS_SKIN[part][key])
    return [(sel, body) for sel, body in _rules(css)
            if uri in body
            and any(word in body for word in idiom)
            and all(any(spelling in sel for spelling in group) for group in selector_groups)]


def _need(hits, what):
    assert hits, f"the loader writes no rule that paints {what}"


# What each part paints, as the selectors the player already uses for it. A
# rule that names one of these is a rule about that part, whether or not it
# carries a picture, so the rules-that-never-bend tests below can see it.
PART_ELEMENTS = {
    "slot": (".equip-row",),
    "tab": ("#menu .pm button",),
    "toggle": (".phase-rail", "#fog-toggle"),
    "tooltip": (".gbtn--tool[title]",),
    "speech": (".npc-box", "#npc-box"),
    "divider": ("header.game-head",),
    "banner": (".toasts",),
    "corner": ("::before", "::after"),
    "gold-plate": (".cta--gold", ".gbtn--gold", "button.primary"),
}


def _new_rules(css):
    """Every rule that draws one of the nine parts' pictures."""
    uris = [uri for _part, _key, uri in _pictures()]
    return [(sel, body) for sel, body in _rules(css) if any(uri in body for uri in uris)]


def _part_rules(css):
    """Every rule that is about one of the nine parts: it names the part's
    element, or it carries the part's picture."""
    uris = [uri for _part, _key, uri in _pictures()]
    elements = [e for spellings in PART_ELEMENTS.values() for e in spellings]
    return [(sel, body) for sel, body in _rules(css)
            if any(uri in body for uri in uris) or any(e in sel for e in elements)]


def test_the_fixture_skin_carries_exactly_the_nine_parts(ran):
    """The `parts` page is the skin the rest of this section reads: the four the
    player already drew, plus the nine of interface slice 4. A part added or
    dropped here changes what every test below is about."""
    assert tuple(mk.PARTS_SKIN) == NEW_PARTS, tuple(mk.PARTS_SKIN)
    assert set(mk.ALL_SKIN["parts"]) == set(mk.SKIN["parts"]) | set(NEW_PARTS)
    assert "has-skin" in ran["parts"]["bodyClass"]


def test_the_slot_paints_the_equipment_rows(ran):
    """`slot` is a worn thing's row in the Bag panel: the plain file on the row,
    `hover` under the pointer, `selected` on the row that is worn - the one
    carrying the Take off control."""
    css = ran["parts"]["css"]
    _need(_drawn(css, "slot", "file", (".equip-row",)), "the slot picture on .equip-row")
    _need(_drawn(css, "slot", "hover", (".equip-row",), (":hover",)),
          "the slot hover picture on .equip-row:hover")
    _need(_drawn(css, "slot", "selected", (".equip-row",), ('[data-action="takeoff"]',)),
          "the slot selected picture on the worn row (the one with Take off)")


def test_the_tab_paints_the_menu_tabs(ran):
    """`tab` is a menu tab: the plain file, and `selected` on the tab that is
    the current one."""
    css = ran["parts"]["css"]
    _need(_drawn(css, "tab", "file", ("#menu .pm button",)), "the tab picture")
    _need(_drawn(css, "tab", "selected", ("#menu .pm button",), ('[aria-current="true"]',)),
          "the tab selected picture on the current tab")


def test_the_toggle_paints_the_phase_rail_and_the_fog_switch(ran):
    """`toggle` is the phase rail and the fog switch: `off` is how a switch
    rests, `on` is the state it is pressed into."""
    css = ran["parts"]["css"]
    for element in (".phase-rail button", "#fog-toggle"):
        _need(_drawn(css, "toggle", "off", (element,)), f"the toggle-off picture on {element}")
        _need(_drawn(css, "toggle", "on", (element,), ('[aria-pressed="true"]',)),
              f"the toggle-on picture on {element}[aria-pressed=true]")


def test_each_toggle_picture_reaches_only_the_switches_in_its_own_state(ran):
    """Read off the real DOM, not off the selector text. For each of the two
    switches, every rule that carries one of the two pictures and reaches that
    switch must reach it in the state that picture belongs to: the resting
    picture only on a switch at rest, the pressed picture only on a switch
    pressed. A state-blind rule paints both states the same, which is the bug."""
    css = ran["parts"]["css"]
    rules = _rules(css)
    state = ran["parts"]["stateRules"]
    hits = {p["name"]: p["hits"] for p in state["probes"]}
    assert all(name in hits for name in
               ("phase-resting", "phase-pressed", "fog-resting", "fog-pressed")), hits.keys()
    pictures = {"off": mk.picture_uri("toggle-off.png"), "on": mk.picture_uri("toggle-on.png")}
    for switch in ("phase", "fog"):
        resting, pressed = hits[f"{switch}-resting"], hits[f"{switch}-pressed"]
        for which, wanted, unwanted in (("off", resting, pressed), ("on", pressed, resting)):
            mine = [i for i, (sel, body) in enumerate(rules)
                    if pictures[which] in body and (resting[i] or pressed[i])]
            _need(mine, f"the toggle-{which} picture on the {switch} switch")
            for i in mine:
                assert wanted[i] is True, (
                    f"the toggle-{which} rule {state['rules'][i]!r} never reaches the "
                    f"{switch} switch in its {which} state")
                assert unwanted[i] is False, (
                    f"the toggle-{which} rule {state['rules'][i]!r} reaches the {switch} "
                    f"switch in the state it is not in")


def test_the_tooltip_paints_the_tool_buttons_that_carry_a_title(ran):
    """`tooltip` is the small tool buttons' tooltip, on hover and on keyboard
    focus, so the keyboard sees what the pointer sees."""
    css = ran["parts"]["css"]
    _need(_drawn(css, "tooltip", "file", (".gbtn--tool[title]",), (":hover",)),
          "the tooltip picture on .gbtn--tool[title]:hover")
    _need(_drawn(css, "tooltip", "file", (".gbtn--tool[title]",), (":focus-visible",)),
          "the tooltip picture on .gbtn--tool[title]:focus-visible")


def test_the_tooltip_says_what_the_button_does(ran):
    """The rule used to paint a blank plate: `content: ""` with nothing in it,
    so the skin's tooltip was a picture with no words on it and no size. It
    says what the button does now, out of the shell's own `data-tip`, which is
    the same word the button already carries for a screen reader."""
    css = ran["parts"]["css"]
    uri = mk.picture_uri(mk.PARTS_SKIN["tooltip"]["file"])
    rules = [(sel, body) for sel, body in _rules(css) if uri in body]
    _need(rules, "the tooltip rule")
    for sel, body in rules:
        assert "content: attr(data-tip)" in body, (
            f"{sel.strip()} paints the tooltip with no words in it")
    tips = ran["parts"]["tips"]
    assert len(tips) >= 4, tips
    for button in tips:
        assert button["tip"], f"the {button['id']} button has a title and no words to show"
        assert button["tip"] == button["sr"], (
            f"the {button['id']} tooltip says {button['tip']!r} and its screen-reader "
            f"text says {button['sr']!r}")
    # the words on the tooltip, not just on the button: the tooltip paints them
    # on the player's own dark face, and they clear the 4.5:1 floor there.
    ink, base = "#F4EEDD", "#15181D"
    for _sel, body in rules:
        assert f"color: {ink}" in body and f"background-color: {base}" in body, body
    got = contrast(ink, base)
    assert got >= 4.5, f"the tooltip words are {got:.2f}:1 on their own base"


def test_the_speech_part_paints_the_speech_box_like_a_panel(ran):
    """`speech` is a nine-slice like `panel`, and the words inside it keep the
    skin's ink rather than taking a colour of their own."""
    css = ran["parts"]["css"]
    _need(_drawn(css, "speech", "file", (".npc-box", "#npc-box"), idiom=("border-image",)),
          "the speech picture as a nine-slice on the speech box")
    ink = mk.ALL_SKIN["ink"]["on_panel"]
    assert any(ink in body for sel, body in _rules(css)
               if (".npc-box" in sel or "#npc-box" in sel) and "color:" in body), (
        "the words inside the speech box must keep the skin's declared ink")


def test_the_divider_paints_the_rule_under_the_game_head(ran):
    """`divider` is the rule under the game head: its bottom edge, by border
    image or by a bottom border picture."""
    css = ran["parts"]["css"]
    _need(_drawn(css, "divider", "file", ("header.game-head",),
                 idiom=("border-image", "border-bottom")),
          "the divider picture on header.game-head's bottom edge")


def test_the_divider_does_not_take_part_in_the_headers_flex_flow(ran):
    """The game head is a wrapping flex box, so a pseudo-element drawn there is
    a flex item: with `flex-basis: 100%` the divider took a row of the head's
    own wrap instead of drawing a line under it. A border-image on the head is
    out of the flow; a pseudo-element would have to be taken out of it."""
    assert "flex-wrap: wrap" in PLAYER_CSS, "the game head no longer wraps"
    uri = mk.picture_uri(mk.PARTS_SKIN["divider"]["file"])
    rules = [(sel, body) for sel, body in _rules(ran["parts"]["css"]) if uri in body]
    _need(rules, "the divider rule")
    for sel, body in rules:
        assert "flex-basis" not in body and "flex-wrap" not in body, (
            f"{sel.strip()} puts the divider in the header's flex flow")
        if "::" in sel:
            assert "position: absolute" in body, (
                f"{sel.strip()} draws the divider in the header's flex flow")


def test_the_divider_is_drawn_in_the_bottom_border_only(ran):
    """On the head itself, a border-image with `fill` (or a slice that gives
    the picture to the middle) would paint the divider over the whole head.
    The picture belongs to the bottom edge: no `fill`, and the border-image
    width is the bottom one alone."""
    uri = mk.picture_uri(mk.PARTS_SKIN["divider"]["file"])
    rules = [body for sel, body in _rules(ran["parts"]["css"])
             if uri in body and "game-head" in sel and "::" not in sel]
    _need(rules, "the divider on header.game-head")
    for body in rules:
        assert " fill" not in body, "the divider fills the game head's face"
        assert "0 0 100% 0" in body and "0 0 8px 0" in body, (
            "the divider is not sliced to the head's bottom edge")


def test_the_banner_paints_the_messages_and_leaves_the_map_alone(ran):
    """`banner` is the message panel. It is a picture behind the messages; it
    must not repaint the map canvas or the HUD frame that sit on the map."""
    css = ran["parts"]["css"]
    _need(_drawn(css, "banner", "file", (".toasts",), idiom=("background",)),
          "the banner picture behind the messages")
    assert "#town-canvas" not in css
    assert ".hud-frame" not in css and "#hud-frame" not in css


def test_the_corner_paints_the_four_studs(ran):
    """`corner` replaces the flat accent dot on the four corner studs with the
    corner picture - all four of them, so no panel keeps a plain dot."""
    css = ran["parts"]["css"]
    for stud in (".carved::before", ".carved::after", "#config::before", "#config::after"):
        _need(_drawn(css, "corner", "file", (stud,)), f"the corner picture on {stud}")


def test_the_corner_paints_four_studs_at_the_four_corners(ran):
    """The rule used to stretch the picture over the player's own 6 px accent
    dots, which sit at the two top corners: a stretched picture, not a stud.
    The four studs are four corners of the panel, each with a size of its own,
    and they take no pointer - a decoration that spans the panel may never sit
    between a person and a control."""
    css = ran["parts"]["css"]
    uri = mk.picture_uri(mk.PARTS_SKIN["corner"]["file"])
    rules = [(sel, body) for sel, body in _rules(css) if uri in body]
    _need(rules, "the corner rule")
    corners = set()
    for sel, body in rules:
        assert "background-size: 100% 100%" not in body, (
            f"{sel.strip()} stretches the corner picture over a dot")
        for size in re.findall(r"background-size:\s*([^;}]+)", body):
            for value in size.split(","):
                px = re.match(r"\s*(\d+)px\s+(\d+)px\s*$", value)
                assert px and int(px.group(1)) >= 16, (
                    f"{sel.strip()} draws a {value.strip()} stud, which is no stud at all")
        assert "pointer-events: none" in body, (
            f"{sel.strip()} spreads the studs over the panel and may take a click")
        where = re.search(r"background-position:\s*([^;}]+)", body)
        assert where, f"{sel.strip()} does not place its studs"
        corners |= {v.strip() for v in where.group(1).split(",")}
    assert corners == {"left top", "right top", "left bottom", "right bottom"}, corners


def test_the_gold_plate_paints_the_gold_controls(ran):
    """`gold-plate` is a plate behind the words on a gold control. The words
    stay real text on top of it, so the picture may not be a picture of words."""
    css = ran["parts"]["css"]
    for control in (".cta--gold", ".gbtn--gold", ".stage button.primary"):
        _need(_drawn(css, "gold-plate", "file", (control,)), f"the gold plate on {control}")
    assert "content: url(" not in css


def test_every_new_part_rule_sits_inside_the_media_guard(ran):
    """prefers-contrast: more and forced colours return the plain flat style, so
    every painted rule is inside the one guard - and the guard is still the
    first thing in the sheet, before it but after any @font-face."""
    css = ran["parts"]["css"]
    assert GUARD in css
    lo, hi = _guard_span(css)
    for part, _key, uri in _pictures():
        assert uri in css, f"the {part} picture is never drawn at all"
        assert lo <= css.index(uri) < hi, f"the {part} rule is outside the media guard"
    before = css[:css.index(GUARD)].strip()
    assert before == "" or before.startswith("@font-face"), before


def test_a_part_the_skin_does_not_carry_is_left_alone(ran):
    """The negative half, which is the half that is easy to get wrong. The
    `skinned` page carries only panel, button, bar and cursor, so none of these
    nine pictures may appear anywhere in its CSS and none of the elements they
    paint may be named at all. Every picture is its own solid colour, so "the
    rule is absent" is a plain string test."""
    css = ran["skinned"]["css"]
    for part, key, uri in _pictures():
        assert uri not in css, (
            f"the default skin carries no {part} picture, yet a rule draws it ({key})")
    for element in (".equip-row", "header.game-head", ".toasts", ".phase-rail",
                    "#fog-toggle", ".cta--gold", ".gbtn--gold", ".gbtn--tool[title]",
                    "::before", "::after"):
        assert element not in css, f"a skin without the matching part writes a {element} rule"
    assert _new_rules(css) == []


def test_no_new_part_rule_invents_a_colour(ran):
    """Every colour on a skinned surface is the skin's declared ink or a colour
    the player already has. The loader must not invent one for the tab, the
    toggle, the slot, the tooltip, the speech box, the divider, the banner, the
    corner or the gold plate."""
    css = ran["parts"]["css"]
    assert _new_rules(css), "the loader draws no rule for any of the nine parts"
    allowed = {c.lower() for c in re.findall(r"#[0-9A-Fa-f]{3,8}\b", PLAYER_CSS)}
    allowed |= {c.lower() for c in mk.ALL_SKIN["ink"].values()}
    # Not colours: references to a colour the player or the skin already sets.
    borrows = {"currentcolor", "inherit", "transparent", "unset", "initial"}
    offenders = []
    for sel, body in _part_rules(css):
        for value in re.findall(r"(?<![-\w])color:\s*([^;}]+)", body):
            value = value.replace("!important", "").strip().lower()
            if value.startswith("var(") or value in borrows:
                continue
            hexes = re.findall(r"#[0-9a-f]{3,8}\b", value)
            if not hexes or any(h not in allowed for h in hexes):
                offenders.append(f"{sel.strip()} -> color: {value}")
    assert not offenders, "a skin part may not bring its own text colour:\n  " + \
        "\n  ".join(offenders)


def test_no_new_part_rule_shrinks_a_target_below_44px(ran):
    """The picture can be smaller than its hit area; the hit area may not be
    smaller than 44 px."""
    css = ran["parts"]["css"]
    assert _new_rules(css), "the loader draws no rule for any of the nine parts"
    for sel, body in _part_rules(css):
        if not any(word in sel for word in CONTROLS):
            continue
        for prop, value in re.findall(
                r"(?<![-\w])(min-height|min-width|height|width)\s*:\s*([0-9.]+)px", body):
            assert float(value) >= 44, (
                f"{sel.strip()} sets {prop}: {value}px, under the 44 px target floor")


def test_the_new_parts_leave_the_focus_ring_and_the_motion_alone(ran):
    """A skin may add a decoration and never take the focus ring away, and it
    adds no motion of its own: the player's reduced-motion blanket already
    covers everything."""
    css = ran["parts"]["css"]
    assert _new_rules(css), "the loader draws no rule for any of the nine parts"
    assert "outline: none" not in css.replace(" :", ":")
    for sel, body in _part_rules(css):
        assert "transition" not in body and "animation" not in body, (
            f"{sel.strip()} adds motion of its own")
    assert "@media (prefers-reduced-motion: reduce)" in PLAYER_CSS


# ---- the contrast floor, measured on the colours the loader actually uses ----

def _button_face(css):
    """The (text colour, background colour) of the player's button face."""
    for sel, body in _rules(css):
        if sel.strip() == ".gbtn, .cta, .verb-row button" and "color:" in body:
            ink = re.search(r"color:\s*(#[0-9A-Fa-f]{6})\s*!important", body)
            base = re.search(r"background-color:\s*(#[0-9A-Fa-f]{6})\s*!important", body)
            if ink and base:
                return ink.group(1), base.group(1)
    raise AssertionError("the skin sheet writes no button face")


@pytest.mark.parametrize("page", ["skinned", "parts"])
def test_the_skins_ink_clears_four_and_a_half_on_the_panel_ground(ran, page):
    """`ink.on_panel` against the flat ground the loader falls back to under a
    panel - the colour that is there when the picture's middle cannot be read."""
    css = ran[page]["css"]
    ink = mk.ALL_SKIN["ink"]["on_panel"]
    ground = re.search(r"var\(--vefr-skin-ground,\s*(#[0-9A-Fa-f]{6})\)", css)
    assert ground, f"the {page} skin writes no panel ground"
    got = contrast(ink, ground.group(1))
    assert got >= 4.5, (
        f"{page}: ink {ink} on the panel ground {ground.group(1)} is {got:.2f}:1")


@pytest.mark.parametrize("page", ["skinned", "parts"])
def test_the_button_ink_clears_four_and_a_half_on_the_buttons_own_base(ran, page):
    """The words on a skin button, against the base the loader puts under the
    picture (so the words survive a checker that cannot see the picture)."""
    css = ran[page]["css"]
    ink, base = _button_face(css)
    got = contrast(ink, base)
    assert got >= 4.5, f"{page}: button ink {ink} on {base} is {got:.2f}:1"


# ===========================================================================
# interface slice 5: the HUD icons and the speech portrait
# ===========================================================================

def test_a_skinned_page_draws_one_icon_beside_each_hud_word(ran):
    """Five small inline SVGs in currentColor, one for each HUD line. They sit
    BESIDE the line, in the same HUD block, and never inside it - so a line
    that is hidden today (this world neither grows nor trades) still has its
    icon, and the words do not move when the line appears."""
    icons = ran["parts"]["icons"]
    for name in ICONS:
        icon = icons[name]
        assert icon["count"] == 1, (
            f"expected exactly one svg[data-icon=\"{name}\"], found {icon['count']}")
        assert icon["beside"] is True, f"the {name} icon is not beside its HUD line"
        assert icon["inside"] is False, f"the {name} icon is a child of its HUD line"
        assert icon["viewBox"], f"the {name} icon has no viewBox"
        assert icon["shapes"] >= 1, f"the {name} icon draws nothing"


def test_every_icon_is_decoration_painted_in_the_words_own_ink(ran):
    """An icon adds nothing a screen reader needs to hear, and it is painted in
    currentColor so it follows the words it sits beside (the house style for
    `.gbtn--tool svg` in 020-style.css is fill: none; stroke: currentColor)."""
    for name in ICONS:
        icon = ran["parts"]["icons"][name]
        assert icon["ariaHidden"] == "true", f"the {name} icon is not aria-hidden"
        assert icon["alt"] is None, f"the {name} icon carries an alt attribute"
        assert (icon["text"] or "").strip() == "", f"the {name} icon has text in it"
        assert icon["currentColor"] is True, (
            f"the {name} icon is not painted in currentColor in its own markup")


def test_the_words_survive_their_icons(ran):
    """The icon is decoration beside the words. The words are still the words."""
    hud = ran["parts"]["hud"]
    assert hud["gold"] == "5 gold"
    assert "Health" in hud["hp"]
    assert hud["menuOpen"] == "Menu"
    # The same page with no skin says exactly the same things: the icons changed
    # nothing about the text.
    plain = ran["plain"]["hud"]
    assert plain["gold"] == hud["gold"]
    assert plain["hp"] == hud["hp"]
    assert plain["menuOpen"] == hud["menuOpen"]


def test_the_bag_icon_is_not_a_child_of_the_bag_strip(ran):
    """One thing carried is one pip in the strip - the same count
    tests/test_combat_loop.py pins on a no-skin pack. The icon is beside the
    strip, never one of the things in it."""
    hud = ran["parts"]["hud"]
    assert hud["bagChildren"] == 1, hud["bagChildTags"]
    assert "svg" not in hud["bagChildTags"]
    assert ran["plain"]["hud"]["bagChildren"] == 1
    assert ran["parts"]["icons"]["bag"]["inside"] is False


def test_a_speaker_with_a_picture_gets_a_decorative_portrait(ran):
    """A speech box shows a portrait when the speaker has one. It is
    decoration: the speaker's name is already real text in .speaker."""
    box = ran["parts"]["npcBox"]
    assert box["error"] is None, box["error"]
    shown = box["withPortrait"]
    assert shown["hidden"] is False
    assert shown["speaker"] == "marta"
    assert shown["images"] == 1, (
        f"the speech box draws no portrait for a speaker the pack gave a picture: "
        f"{shown['children']}")
    assert shown["srcs"] == [box["expectedSrc"]], shown["srcs"]
    assert shown["alts"] == [""], shown["alts"]
    assert shown["ariaHidden"] == ["true"], shown["ariaHidden"]


def test_a_speaker_with_no_picture_gets_no_portrait_slot(ran):
    """And no empty one, and no broken one: a speaker the pack gave no picture
    leaves the box exactly as it is, including after a speaker who had one."""
    box = ran["parts"]["npcBox"]
    assert box["error"] is None, box["error"]
    shown = box["withoutPortrait"]
    assert shown["speaker"] == "nobody"
    assert shown["images"] == 0, f"a portrait with no picture is still a portrait: {shown}"
    assert shown["srcs"] == []
    assert shown["portraitSlots"] == 0
    assert shown["children"] == ["p#npc-name", "p#npc-line", "p#npc-note", "button#npc-close"]


def test_the_three_argument_call_still_works(ran):
    """showSpeech(speaker, line, note) is what every player path calls
    (tests/fixtures/overlay_interact_harness.mjs calls it with three arguments).
    The third argument is still the note, and nothing else is now required."""
    for page in ("parts", "plain"):
        box = ran[page]["npcBox"]
        assert box["error"] is None, f"{page}: {box['error']}"
        for half, who in (("withPortrait", "marta"), ("withoutPortrait", "nobody")):
            shown = box[half]
            assert shown["hidden"] is False, f"{page}/{half}"
            assert shown["speaker"] == who
            assert shown["line"].startswith("A line from ")
            assert shown["noteHidden"] is True


@pytest.fixture(scope="module")
def orders():
    """The speech box and the skin in one script tag each, in both orders."""
    if shutil.which("node") is None:
        pytest.skip("node not installed")
    run = subprocess.run(["node", str(ROOT / "tests/fixtures/skin_speech_order_harness.mjs")],
                         capture_output=True, text=True, timeout=120)
    assert run.returncode == 0, run.stderr + run.stdout
    return json.loads(run.stdout)


def test_the_portrait_does_not_depend_on_which_part_loads_first(orders):
    """The wrap was written at load time, so it only ever found a speech box
    that was already on the window: a page that declared the speech box after
    the skin got a hook that wrapped nothing and every portrait silently
    vanished. The speech box asks for its portrait when it shows a speaker, so
    both orders draw it - the one the parts ship in and the reverse."""
    for name in ("shipped", "reversed"):
        got = orders[name]
        assert got["error"] is None, f"{name}: {got['error']}"
        assert got["speaker"] == "marta", name
        assert got["images"] == 1, f"{name}: no portrait in {got['children']}"
        assert got["srcs"] == [got["expectedSrc"]], f"{name}: {got['srcs']}"
    # And the words the speech box writes are its own either way.
    assert orders["shipped"]["children"] == orders["reversed"]["children"]


def test_a_pack_with_no_skin_has_no_hook_and_no_portrait(orders):
    """The negative half of the hook: with no skin the speech box is the box it
    always was, one read of a hook that is not there and nothing else."""
    nope = orders["nope"]
    assert nope["error"] is None, nope["error"]
    assert nope["images"] == 0 and nope["icons"] == 0, nope
    assert nope["children"] == ["p", "p", "p", "button"], nope["children"]


def test_a_page_with_no_skin_has_no_icons_and_no_portrait(ran):
    """The icons belong to a skin: a pack with no skin plays exactly as it did."""
    for name in ICONS:
        assert ran["plain"]["icons"][name]["count"] == 0, name
    assert ran["plain"]["npcBox"]["withPortrait"]["images"] == 0


def test_the_marks_and_the_portrait_go_only_to_a_skin_that_carries_them(ran):
    """They are a skin's, and only for a skin that opted into the themed
    interface. The `skinned` page carries the four parts the loader always drew
    and none of the nine of interface slice 4, so it is not a themed skin and
    its HUD is the plain player's HUD - no mark, no portrait. The `parts` page
    carries the nine and gets all of it."""
    for page, wanted in (("skinned", 0), ("parts", 1)):
        for name in ICONS:
            got = ran[page]["icons"][name]["count"]
            assert got == wanted, f"{page}: {name} icon drawn {got} times, wanted {wanted}"
        box = ran[page]["npcBox"]
        assert box["error"] is None, f"{page}: {box['error']}"
        assert box["withPortrait"]["images"] == wanted, (
            f"{page}: {box['withPortrait']['children']}")


def test_a_pack_with_no_skin_gains_no_element_of_any_kind(ran):
    """No style element, no has-skin class, no icon, no portrait, and the HUD
    row is the row the shell builds."""
    plain = ran["plain"]
    assert plain["hasStyle"] is False and plain["css"] == ""
    assert "has-skin" not in (plain["bodyClass"] + " " + plain["htmlClass"])
    assert plain["hud"]["hudTlChildren"] == [
        "hud-hp", "touch-quick", "hud-level", "hud-state", "hud-gold",
        "bag-strip", "light-live"]
    assert plain["hud"]["bagChildren"] == 1
    assert plain["npcBox"]["withPortrait"]["children"] == [
        "p#npc-name", "p#npc-line", "p#npc-note", "button#npc-close"]


# ===========================================================================
# the swap proof (vefr#503): two packs, two skins, one engine
#
# Every skin test above proves one skin is drawn. None of them could tell a
# page wearing THIS pack's skin from a page still wearing the last one, because
# there was only ever one synthetic skin to wear. A second one - another name,
# another credit, another ink, another colour on every picture - is the control
# that makes the first one a measurement.
# ===========================================================================

def test_two_packs_wearing_two_skins_each_get_their_own_style_element(ran):
    """Each woven game builds its one `<style id="vefr-skin-css">` from its OWN
    pack's baked skin: the picture and the ink in the sheet are that skin's,
    and the other skin's are not in it at all. The two sheets are not the same
    string, so neither page is showing the other pack's skin."""
    a, b = ran["skinned"], ran["second"]
    assert a["hasStyle"] is True and b["hasStyle"] is True
    assert "has-skin" in (a["bodyClass"] + " " + a["htmlClass"])
    assert "has-skin" in (b["bodyClass"] + " " + b["htmlClass"])
    assert a["css"] != b["css"]

    panel_a = mk.picture_uri("panel.png")                       # the parchment panel
    panel_b = mk.picture_uri("panel.png", mk.SECOND_COLOURS)    # the teal one
    assert panel_a != panel_b
    assert panel_a in a["css"] and panel_b not in a["css"]
    assert panel_b in b["css"] and panel_a not in b["css"]

    ink_a, ink_b = mk.SKIN["ink"]["on_panel"], mk.SECOND["ink"]["on_panel"]
    assert ink_a != ink_b
    assert ink_a in a["css"] and ink_b not in a["css"]
    assert ink_b in b["css"] and ink_a not in b["css"]

    # The rest of the sheet is the engine's, built the same way for both: the
    # button face, the 44 px floor and the media guard are in both.
    for css in (a["css"], b["css"]):
        assert "background-color: #5F5043 !important" in css
        assert "min-height: 44px" in css
        assert GUARD in css


def test_the_second_skins_ink_clears_four_and_a_half_on_the_panel_ground(ran):
    """The second skin declares its own ink, and that ink reads on the flat
    ground the loader falls back to under a panel - measured, like the first
    skin's, on the colours the loader actually writes."""
    css = ran["second"]["css"]
    ink = mk.SECOND["ink"]["on_panel"]
    ground = re.search(r"var\(--vefr-skin-ground,\s*(#[0-9A-Fa-f]{6})\)", css)
    assert ground, "the second skin writes no panel ground"
    got = contrast(ink, ground.group(1))
    assert got >= 4.5, (
        f"the second skin: ink {ink} on the panel ground {ground.group(1)} is {got:.2f}:1")


def test_two_skins_swap_and_no_engine_byte_moves(tmp_path):
    """A skin is DATA, and this is the proof: two packs with the same world and
    the two skins weave to files that differ in the baked `window.VEFR_SKIN`
    line alone. Swapping a pack's skin changes what is painted and nothing
    else - no engine edit rides along with a skin."""
    same = "skin-swap"
    a = cli.weave_html(mk.build(tmp_path / "a", name=same))
    b = cli.weave_html(mk.build_second(tmp_path / "b", name=same))
    assert a != b

    def skin_line(html):
        m = re.search(r"window\.VEFR_SKIN = ([^\n]*);\n", html)
        assert m, "no VEFR_SKIN line in the weave"
        return m.group(1)

    assert skin_line(a) != skin_line(b)

    def engine(html):
        return re.sub(r"window\.VEFR_SKIN = [^\n]*;\n", "window.VEFR_SKIN = <skin>;\n", html)

    assert engine(a) == engine(b)
