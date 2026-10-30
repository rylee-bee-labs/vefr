# 0023 - Show it: the spell card, "Wear it?", hit numbers and the quick bar

Date: 2026-10-30

## Status

**Accepted direction; implemented in one PR.** After her first Gate 0 run of
the Cottage 1.0 build the owner said: "The spells and combat and gear
weren't really there? The potion icons are nice". Offered four ways to put
them where the player looks, she picked all four on 2026-10-30: "Spell
learned card", "Wear it? on pickup", "Hit numbers over monsters" and "Hotbar
for potions". That pick is the ask-first answer for the four `display` keys
below. The words on the card, the question and the buttons, the keys 5 to
8, the bar's order and putting spells on it are Claude's calls, named as
such.

**Every key is opt-in.** A pack that names none of them weaves and plays as
it did: `tests/test_show_it_play.py` plays the opt-out fight, kill, pickup
and level and finds no card, no question, no number and the old quickslots.

## Context

The rules of ADR 0021 work, and they were invisible:

- a spell learned on a level was only a line in the Bag panel, which is not
  on screen in play; nothing said what it did or how to cast it;
- gear better than what is worn went into the bag, and wearing it meant
  opening the Bag and comparing names;
- a blow's number, a miss and a critical hit were words in one live line,
  which the monster's answer replaced in the same turn;
- potions were drunk from the Bag; a phone had two quickslots and a desk
  had none.

None of it needs a new rule. Each is a place to show what a rule already
decided.

## Decision

Four `display` keys, each a `true` or `false`, in `shapes.DISPLAY`:

- **`spell_card`.** When a spell becomes known - a level reached
  (`growAward` compares the known list before and after) or a book read for
  the first time - a card like the fall's says "You learn <spell>." and,
  one short line each, what it does (in the words the cast will say), what
  it costs in mana, and how to cast it: the quick bar's key when the spell
  is on the bar, Cast on the fight row when it is the spell that button
  casts, and the Bag always. Two spells on one level are two cards in the
  pack's order. Interact, Enter, Space or the menu key closes it, and a tap
  on the dim; a walking key does nothing while it is up, so a player
  pressing on through a fight does not dismiss it unread. The line is kept
  on the quiet page.
- **`wear_prompt`.** Picking up a thing with a slot that would raise one of
  the hero's numbers asks "Wear <thing>?" with each change ("Attack 3 to
  5") and what comes off, as the stake offer asks (vefr#504): two buttons
  under the messages, Y and N, focus on the answer that changes nothing,
  and the game going on while it waits. The change counts only what the
  player can know - the thing's own `mods`, and the traits of an instance
  the town has read - so the question never gives away an unread trait or
  a curse (ADR 0017). Y wears it through the Bag's own Equip; N keeps it in
  the bag. A thing that raises nothing does not ask.
- **`hit_numbers`.** Each blow's number over the one it struck: the hero's
  blow (`3`, `CRIT 6`, `miss`), a spell's harm, thorns, a monster's blow
  over the hero (`-2`, `CRIT -6`, `miss`), a burn's bite, and heals (`+3`).
  The layer is `aria-hidden`: the fight's own line still says every number
  in words, and the number's text, not its colour, says what it is. It
  rises and fades; under either reduced-motion blanket (the OS setting or
  the player's switch) it holds still and stays 600 ms longer.
- **`hotbar`.** The quickslots' box becomes a bar on every screen: up to
  four buttons, first each kind of carried thing used in one tap (a `heal`,
  a `light`, a thing that `casts`) in the pack's item order with how many
  are carried, then the spells the hero knows in the pack's order with
  their mana cost (dimmed, and saying so in its name, when the hero cannot
  pay). Keys 5 to 8 are four new rows in the keybinds table
  (`quick1`..`quick4`), listed in Controls only when the bar is on, and the
  player may give them other keys, 5 to 9 included. With the bar on, the
  fight row's number keys stop at 4, so a digit always means one button. A
  press is the Bag's own Use or Cast (aimed at the foe the fight row
  names), and what it said goes to the fight's line, ahead of a monster's
  answer in the turn it cost. On a touch screen the top row has no room for
  four more buttons, so the bar stands where a thumb is: over the stick,
  level with the fight verbs on the other side.

**And one fix, for every pack.** The fall card's note says "Your bag, your
gold and the ground you have walked are as you left them." On a fall that
left the bag on the floor (ADR 0021, `fall: "home"`) that was false. That
fall's note now says what was kept: "What you wear, your gold and the ground
you have walked are as you left them." Every other fall keeps the card's
own words.

## Consequences

- Four pack-contract keys, in `shapes.DISPLAY` and
  `docs/guides/world-creation.md` ("Show it").
- New parts: `227-show-it.js` (the card, the question, the bar's contents
  and keys) and `507-hit-numbers.js` (inside the fight's closure, after
  `afterDraw` exists). The bar is drawn by the quickslots' own
  `renderQuickslots` in part 515.
- Not in this change: choosing what goes on the bar (it is the first four in
  a fixed order, so when a potion kind runs out the slots after it move
  left), a number for a sting or a status that does no harm, and any change
  to what a fight decides.

## Acceptance

`tests/test_show_it_play.py` and the full gate.
