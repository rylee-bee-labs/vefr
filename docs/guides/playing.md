# Playing: the keys and the one button

This page is for someone who has never played before.
Every sentence says what happens and what to do.
You cannot get anything wrong here; the game tells you what it is doing as you go.

## The keys

| Key | What it does |
|---|---|
| Arrow keys, or `W` `A` `S` `D` | Move one tile. On a touch screen, put a finger on the left side and slide it the way to go. In a note, `A` and `D` turn the page like the arrows. |
| `F`, `Space`, `Enter` | Interact. All three keys do the same one thing. |
| `Q` | Hear a rumor: what people are saying right now. |
| `B` | Open the bag. |
| `O` | Walk the unexplored dark. Press it again to stop. |
| `V` | Turn the dark off and on. |
| `Escape` | Open the pause menu. Press it again to close it. |

On the title screen, **Begin** has the focus and takes `Enter`, `Space` and `F`, so any of them starts the game. `Tab` keeps the focus on **Begin** instead of walking it off the screen.

One big button, **Interact**, sits at the bottom right and says what it will do. On a computer, beside it are
four small icon buttons: Talk (`F`), Listen (`Q`), Bag (`B`) and Explore (`O`). Each keeps its word for a screen
reader and a tooltip, and a tiny key letter. The Dusk and Dawn buttons live in the Menu, under Display, as "Time of day".

**Listen** hears a rumor from anywhere in town, so it is not a whisper to whoever is standing next to you.
The box says so: "You overhear <the speaker>". The Journal keeps what you overhear, and can ask for one.

On a touch screen the bottom right holds a smaller set. The big round button is Interact: it says what it
will do, so beside a person it says **Talk** and their name. Above it is **Bag**. To the left are **Listen**
and **Explore**; tap Explore again to stop. While a note, a shop or someone's line is open, these step aside
and a **B** button closes it. Under Display in the Menu you can choose a D-pad instead of the joystick, change
the Control size, or turn on Left-handed to swap the sides.

Display also holds the two reading settings, next to the Sound switch:

| Setting | What it does |
|---|---|
| **Larger text** | A fifth more on the body text and on every label. |
| **Reduced motion** | Nothing moves: no walking hop, no fading messages, no blinking. |
| **Volume** | How loud the sound cues are, when the game has sound at all. The **Sound** switch beside it says whether they sound; the slider says how much. |

Each one is remembered in this browser, separately for each game, and comes back the next time you play.
`Space` and `Enter` press the button that already has the focus.
While a note or someone's line is on screen, `F`, `Space` and `Enter` turn the page and then close it.
In the shop, `F` closes it too (`Escape` and the Close button still work).

The screen stays quiet. The how-to-move line goes after your first step. A place's name shows for a few
seconds when you arrive. The fight buttons appear only with a monster near. Everything else sits in a small
**Messages** panel in the top left that you can fold away; a screen reader still hears every line.
The map itself is named for where you are standing, and it changes when you walk through a door: the hero
is in the cottage kitchen, so a screen reader says "The cottage kitchen, seen from above", not "the town".

## What Interact does

Interact looks at what is near you and does the one thing that fits.
It picks one thing, in this order:

1. the thing on the tile you are FACING.
2. the thing you are standing on.
3. the nearest thing in reach.

People and the trader are in reach from two tiles away.
Doors, stairs, chests, notes on the ground, places and monsters are in
reach from one tile.

When two things tie, a door or stairs wins, then a chest, then a note
on the ground, then a trader, then a person, then a place, then a monster.

## The button says what the press will do

The Interact button always sits on the screen. It never hides and it is never switched off.
Its own words say what the next press will do:

- "Open the chest"
- "Read <title>" for a note lying on the ground
- "Talk to <name>"
- "Trade with <name>"
- "Go through the door", "Go down the stairs" or "Go up the stairs"
- "Look at <place>"
- "Fight <name>"

The same words appear in the hint line, and a screen reader reads them out.
A thin ring is drawn on the tile the button points at, so the picture and the words agree.

## When nothing is near

With nothing in reach, the button dims and the hint says "Nothing near you to use yet."
Press it anyway and Interact says one friendly line:

> Nothing to use here. Walk up to something and try again.

It costs you nothing and does not waste a turn.

## Fighting

Walking into a monster still hits it, exactly as before.
Interact on a monster is the other way in.
It opens the monster's own actions - "Strike", "Console", or whatever the game names -
and you choose one.
A monster with only one action acts at once, with no menu.
Either way the monsters take their turn once your action resolves.

## Wearing things

Press `B` for the bag. At the top is a **"You"** section: five slots - hand, body, head, feet
and charm - each in a row that says in words what is in it ("Body: a patched coat") or that it is
empty ("Hand: empty"). A slot with nothing in it draws a plain outline; a worn thing draws its own
picture.

A carried thing your game says can be worn gets an **Equip** button. Something you are wearing gets
**Take off**. Wearing a thing into a slot that is already full hands the old one back to the bag,
and the line under the buttons says what changed: *"You put on a green hooded cloak. Health up by
2."* A worn thing is not in the bag list, so you cannot sell or drink it while you have it on -
take it off first.

Tab moves between the buttons and `Enter` or `Space` presses one, the same as everywhere else.
Nothing here needs a mouse.

If your game gives no thing a slot, this section says "empty" five times and the game plays exactly
as it always did.

## Start over

Start over lives in the pause menu: press `Escape`, then choose **Start over**.
It asks once before it does anything:

> Start over? This clears your bag, gold, health, fog and the monsters you've beaten in this browser.

**Cancel** - or `Escape` - changes nothing.
Confirm and it clears your bag, your gold, your health,
the fog you have uncovered and the monsters you have beaten in this browser,
then returns you to the title screen.
It clears the saved games for every game on the same site,
so it cannot miss an old save.
