# Glossary: what things are called

What is a floor? In this project it used to mean three different things. That is a problem if you are new,
because a word that means three things means nothing. This page fixes it: one plain name for each thing,
the studio name beside it, and the old names so you can still read older pages.

**The rule:** nouns name things, verbs name actions, adjectives name states, and adverbs say how an action happens. The plain name comes first.
The Norse or studio name sits beside it. It never replaces it. If you add a new name, add it here first.

**Status:** *decided* means Rylee chose it. *proposed* means it is the best candidate and still needs her OK.
*in use* means the code or the screens already say it. Where a name is only in the docs so far, the table says so.

## Things (nouns)

| Plain name | What it is | Studio or old names | Status |
|---|---|---|---|
| **game** | One game's folder: its story, settings and art. Lives in `worlds/<name>/`. | "pack", "world pack", "world" | decided; docs first, code says `pack` for now |
| **gameplay feature** | A reusable way to play that more than one game can use: dialogue, turns, detection, scoring, cards or a timer. | "gameplay system", "game mechanic"; not "module" or "bundle" | decided 2026-10-04; architecture name in [ADR 0012](../adr/0012-gameplay-features.md) |
| **act** | A chapter of a game. | (same) | in use |
| **level** | How far the hero has grown in `levels` mode. The hero starts at level 1; enough experience reaches the next level. | "hero level" | in use (`design/growth.md`) |
| **experience** | The points a defeated enemy is worth in `levels` mode. Enough experience is a new level. | "XP" | in use (`design/growth.md`) |
| **practice** | The other growth mode: doing a thing a lot makes the hero better at it, with no levels and no experience. | "learn by doing" | in use (`design/growth.md`) |
| **dungeon floor** | One dungeon map that `delve` makes. Stairs join floors. | "floor", "region", older "level" | decided |
| **chamber** | A carved space inside a dungeon floor. | "room" (dungeon sense) | decided |
| **stakes** | How much the numbers matter in an act: `costume`, `story` or `stakes`. | the `floor` setting | decided; the file key stays `floor` for now |
| **room** | One screen of the studio, such as the Desk or the Library. | "department", "module", "screen" | decided |
| **map** | The grid drawing of one place (`map.md`). | the Map Room screen draws it | in use |
| **tile** | One square of ground. | (the picture is a "tile picture") | in use |
| **variant** | One of several pictures for the same tile name, so a floor does not repeat. | `name.2.webp`, `name.3.webp` | in use after the pack-tiles change lands |
| **item** | A thing the hero can carry. | "Vault" (the screen), "keepsake", "bag" | proposed |
| **book** | A text the player can find and read. | the Library holds them | in use |
| **achievement** | A goal you can earn. | "sticker book" (where they are kept) | decided |
| **sticker** | The picture you collect for an achievement. | (same) | decided |
| **line** | A short piece of story the model writes. | "whisper", "letter", "beat" | proposed |
| **character** | A person or monster in a game. | "folks" (the screen), "speaker" | proposed |
| **sprite** | The small picture of a character that walks around. | "character picture" | in use |
| **portrait** | A larger picture of a character, shown when they talk. | (same) | proposed |
| **model** | The AI program that writes or reads. | "brain" (retired), "provider" | proposed |
| **role** | A job a model has: narrator, translator or helper. | "storyteller", "narrate", "interface" | decided 2026-10-01 (Rylee: "narrator is great"); code names `storyteller` and `VEFR_STORYTELLER` stay as aliases |
| **bundle** | The one-file game you send to a friend. | "weave" (the old verb), "shareable file" | proposed |
| **storage** | Disk space that holds games and history for a container. | "volume" | proposed |
| **style kit** | A game's look: palette, rules, anchor pictures and the shared style words. Never mixed between games. | (same) | decided (making-art guide) |
| **credits line** | One line saved beside a picture: who made it, with what tool, the prompt, the date and its status. | (same) | decided |
| **edit** | One checked change to a game that the player keeps: put a person in, paint the map. Always previewed first, always backed up. | "change", "commit" | in use (people and the map) |
| **edit log** | The list of kept edits, so the last one can be undone. The studio keeps the full log; the game folder keeps a short `EDITS.md`. | "history" | in use |
| **skin** | A swappable set of pictures for a game's panels, buttons and bars. | "theme", "UI pack" | proposed (`design/ui-skin.md`) |
| **reaction** | One thing's own "when this happens, it does that" (the cat looks up when you come near). | "trigger", "event" | in use (`docs/guides/rules.md`) |
| **rule** | A game-wide "when this happens, do that", using flags. A reaction is a small rule attached to one thing. | "trigger", "script" | in use (`docs/guides/rules.md`) |
| **belief** | What a character thinks is true. It can be wrong. | "knowledge" | in use (`docs/guides/rules.md`) |
| **kept thing** | An item that can be used again and again - a quest tool, a lantern. Using a kept thing never spends it. | "key item", "quest item" | in use (`docs/guides/rules.md`) |
| **locked door** | A door or stair a game gates on a key item or a flag. Used without it, it says one line and the hero stays put; with it, it opens. The key is never spent. | `requires` / `locked_text` (the pack fields) | in use (`design/gates-and-guardians.md`) |
| **Rule saves** | A game's choice of how much of a run the rules remember: `reset` (the default, fresh each load) or `persist`, which keeps flags, fired markers, beliefs and items across a reload. | the `saves` block in `world.json` | in use (`docs/guides/rules.md`) |
| **Why did that happen?** | The menu panel that shows what the world did and what made it happen - only real records, never guesses. | "debug log" | in use (the woven player) |
| **Where next?** | The menu panel that keeps what the world has pointed the player toward, so the way can be found again. | "quest log" | in use (the woven player) |
| **slot** | A place on the hero for one worn item: hand, body, head, feet or charm. | "equipment slot" | in use (`design/equipment.md`, `docs/guides/rulesets.md`) |
| **blueprint** | A Blueprint is an optional file at a pack root that expands a small family source into the owned regions' `enemies` records. It is the edited truth for the regions it owns. Acts shape only. | (same) | in use (`docs/guides/blueprint.md`) |

## Actions (verbs)

| Plain verb | What it does | Old or studio verb | Status |
|---|---|---|---|
| **check** | Tests a game's map, voices and reachability, or a running studio's health. | `validate`, `verify`, `skipa`, `doctor` | proposed, being built as `vefr check` and `vefr doctor` |
| **bundle** | Packs a game into one file. | `weave` | proposed |
| **play** | Opens a game. | (same) | in use |
| **find** | Searches a game's text and your notes. Says UNKNOWN when it finds nothing. | (new) | proposed |
| **back up** | Saves a game and its history somewhere safe. | `carry` | proposed |
| **ship** | Moves a game between machines. | `ferry` | proposed |
| **fetch** | Downloads a game from a repository. | (same, already plain) | in use |
| **generate a dungeon** | Makes dungeon levels from a seed. | `delve` | proposed |
| **write the manual** | Writes the mechanics manual from real play. | `handbok` | proposed |
| **interview** | Asks questions to start a new game. | `chat` | proposed |
| **keep** | Saves one thing to your collection. | "star" marks; "keep" saves | in use |
| **put in the game** | Turn a kept character into a real person in the game, standing on a tile. | "place", "keep" (keep only saves them to the vault) | in use |
| **play it here** | Open the game you are making inside the studio, in a pane, with no download. | "weave and open" | in use |
| **undo** | Put the last kept edit back, in plain words. One step only. | "revert" | in use |
| **equip** / **take off** | Wear or remove an item in a slot. From the Bag panel: a "You" section shows all five slots, a carried thing gets **Equip**, a worn one gets **Take off**, and wearing something into a full slot hands the old one back to the bag. | "wield" | in use (`design/equipment.md`, `docs/guides/rulesets.md`) |
| **interact** | Looks at what is near you and does the one thing that fits: talk, trade, open, go through, look or fight. | `tryNPC` "talk", `useHere` "use", the separate `E` / `F` keys | in use |
| **start over** | Clears the saved games for every game on the same site, then returns to the title screen. | `clear saves` | in use |
| **normalize** | Expands a Blueprint into the owned regions' `enemies` lists and refreshes `blueprint.lock.json`. Read-only without `--out`. | (new) | in use (`docs/guides/blueprint.md`) |

## States (adjectives)

| Plain word | Means | Old or clashing words | Status |
|---|---|---|---|
| **draft** | Made, not yet judged. | (same) | in use |
| **mockup** | A design idea shown as a picture: to look at, not a decision. | "concept", "comp" | decided 2026-10-12 |
| **prototype** | A design idea that works well enough to try: still not a decision. | "proof of concept" | decided 2026-10-12 |
| **approved** | The owner said yes. For a design, the only stage that gets built for real (mockup, then prototype, then approved). | "accepted" | decided 2026-10-12 |
| **released** | Shared with others. | "live" (for a pack), "published" | proposed |
| **running** | A program is on right now. | "live" (for a process) | proposed |
| **ok** | Checked and fine. | "healthy", "passing" | proposed |
| **not checked** | We could not tell. This is not a failure and not a pass. | "unknown" folded into health | proposed |
| **complete** | A request or task is finished. | "done" | proposed |
| **skipped** | Chosen not to do it now. | "not now" | proposed |

## How an action happens (adverbs)

Flags that change *how* a command acts are the adverbs of the tool. Say what they mean in plain words, and keep them few.
A flag that starts with `--no-` always means "without".

| Flag | In plain words | Status |
|---|---|---|
| `--dry-run` | **first, without changing anything:** show what would happen | in use |
| `--json` | **as data:** print a result a program can read | in use |
| `--force` | **even if it replaces something** | in use |
| `--push` | **and then send it** | in use |
| `--inspect` | **only look:** change nothing | in use |
| `--no-git` | **without saving to version control** | in use |
| `--no-world` | **without the game itself** | in use |
| `--blind` | **without names:** hide which model made which answer | in use |

Words we want available for new flags, because a newcomer already knows them: *quietly* (`--quiet`), *again* (`--retry`), *only*
(`--only X`), *offline* (`--offline`: no model, no network), *safely* (`--safe`: the more careful way).
Most other flags name a thing (`--pack`, `--url`, `--seed`, `--floors`). Those are nouns and follow the noun rules above.

## Places in the studio (rooms)

Plain name first, studio name beside it. The studio names stay because they are part of the story.

| Room | Studio name | What you do there |
|---|---|---|
| **Brief** | the Desk | Say what the game is for, in your own words. |
| **Maps** | the Map Room | Draw places and check them. |
| **Characters** | the Folks | Invite people into the game. |
| **Items** | the Vault | See what the hero can carry. |
| **Books** | the Library | Read and write books. Fróði keeps it. |
| **History** | the Chronicle | Read what happened. Urðr keeps it. |
| **Inspiration** | the Casting Table | Cast stones for ideas. |
| **Canon** | the Archives | Keep the facts the story must not break. |
| **Collection** | the Hall | See what you kept, and your achievements. |
| **All rooms** | the Studio Floor | Pick a room. |
| **Settings** | the Boiler Room | Reading, sound, motion and the small model. |

## Settings (environment variables)

Plain names are added; the old names keep working and print a one-line hint. Nothing breaks. *Proposed*; the code aliases come in a later change.

| Plain name | Old name | Sets |
|---|---|---|
| `VEFR_MODEL_URL` | `VEFR_LLAMACPP_URL` | Where the model answers (any server that speaks the common chat format, not only llama.cpp). |
| `VEFR_MEMORY` | `VEFR_VAULT` | Where the session memory is kept. |
| `VEFR_HISTORY` | `VEFR_JOURNAL` | Where the play history is kept. |
| `VEFR_NARRATOR_MODEL` | `VEFR_STORYTELLER` | Which model writes the story lines. |

## People in the studio

Residents are characters, so they keep their names. Their jobs are described in [residents.md](residents.md).

- **Fróði** keeps the Library.
- **Urðr** keeps the Chronicle.
- **Ratatoskr** carries messages between rooms. Ratatoskr is also the old name of the operations command; that job now lives under `vefr` (the old command keeps working).

## Known clashes we still have to fix in the code

These are listed so you are not confused by them in the meantime. Each is a plain-name change with the old name kept as an alias.

- `floor` is the code key for **stakes** and also the old word for a **dungeon floor**.
- `level` used to mean a dungeon map. It now means the hero's growth (see **level**); the map is a **dungeon floor**.
- `VEFR_STORYTELLER` and `VEFR_NARRATE_URL` both name the narrator role.
- `done`, `healthy`, `ok` and `passing` all mean "fine" in different places.
- `unknown` is stored as if it were a health value; it means "not checked".
