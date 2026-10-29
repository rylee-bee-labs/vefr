// ---- inlined world pack ----
window.VEFR_WORLD = {{world_json}};
// Ground tiles, keyed by map symbol: the same picture tiles the
// studio's Map Room draws, so a game looks the same shipped as it did
// in the room that made it. Empty when the pack's legend names none.
window.VEFR_TILES = {{tiles_json}};
// Character sprites, keyed by name: `hero` for the player, and one per
// speaker key. The same art the pack's own folder holds, so a character
// looks like someone, not a dot. Empty when the pack names none.
window.VEFR_SPRITES = {{sprites_json}};
// Optional walk sheets, keyed by the same sprite names: a pack that
// puts a `<key>-sheet.png` beside a sprite and describes its frames in
// `<key>.sheet.json` walks through them, frame by frame. Empty for
// every pack with no sheets, so nothing changes without one.
window.VEFR_SPRITE_SHEETS = {{sprite_sheets_json}};
// Each character's size relative to the standard (1.0 = 1.5 tiles tall), from the pack's `player.sprite_scale`.
window.VEFR_SPRITE_SCALE = {{sprite_scale_json}};
// The pack's item catalog, keyed by id: {"name": "...", "sprite": "..."}.
// A drop names one of these; the bag shows the name and draws the sprite
// (a name in window.VEFR_SPRITES). Empty when the pack names none.
window.VEFR_ITEMS = {{items_json}};
// Ground tiles per region: two regions can share a symbol for different
// ground (a town's '.' is grass, a dungeon's '.' is stone floor).
window.VEFR_REGION_TILES = {{region_tiles_json}};
// Edges sheets per region, keyed by map symbol: a legend entry's `edges` (one 4 x 4 picture, the piece
// drawn over a tile chosen by which neighbours share its symbol). Empty when no legend names edges.
window.VEFR_TILE_EDGES = {{tile_edges_json}};
// Lamplight's normal maps per region, keyed by map symbol: `<tile>.normal.webp` beside a tile, in the tile's own
// shape (one picture, variants, or a grid). Empty when the pack has none; its tiles are then lit flat.
window.VEFR_TILE_NORMALS = {{tile_normals_json}};
// Lamplight's standing tiles per region, keyed by map symbol: the height in tiles of each symbol whose tile
// `light.stand` names. Empty when the pack stands none.
window.VEFR_LIGHT_STAND = {{light_stand_json}};
window.VEFR_LOGBOK = {{logbok_json}};
window.VEFR_LEDGER = {{ledger_json}};
window.VEFR_VOICES = {{voices_json}};

// The pack's own books, baked at weave time: what a player can find in
// play (shelf, on the map, from a resident, or earned) and read here.
// Empty when the pack carries no library/ folder.
window.VEFR_LIBRARY = {{library_json}};

// The act's regions, keyed by region name: each holds the region's map
// rows and its geometry/colours. A single-region pack has one entry;
// the woven player reassigns its town when it steps through a door.
window.VEFR_REGIONS = {{regions_json}};
// The act's doors: step on `at` in region `from` and land at `to_at`
// in region `to`. Empty when the act declares none.
window.VEFR_TRANSITIONS = {{transitions_json}};

// The pack's descent block, when it declares one (slice E1): the run
// seed, the tile the descent starts from, and the Sections. `null` for a
// pack that declares none, which is every pack but a descent's.
window.VEFR_DESCENT_DEF = {{descent_json}};
// The pack's optional town states (ADR 0015, E8c): the regions whose look
// follows a story flag, one block for a region or a list of them. The
// literal null when the pack declares none, which is every pack but a
// descent's - and every region of it then plays as it always did.
window.VEFR_TOWN_STATES = {{town_states_json}};
// The act's speakers, grouped by the region they belong to (a speaker
// with no `region` belongs to the act's first region).
window.VEFR_SPEAKERS = {{speakers_json}};
// The shopkeepers, one per region: {region: speaker key}. A speaker
// whose spec carries `"shop": "true"` keeps the shop of its region.
// Empty when the pack has none, so a world with no reward end bakes
// exactly the player it had before.
window.VEFR_SHOPS = {{shops_json}};
// The pack's four rule catalogs, baked only when the pack declares
// one of them: VEFR_RULES is rule DATA (the logic itself is the
// engine, window.VEFR_RULES_ENGINE), and FLAGS/CLAIMS/PEOPLE are the
// truth it reads beside them. All four are the literal null for a
// pack that declares none - no rules, no wiring, no work, and every
// existing pack's exact file.
window.VEFR_RULES = {{rules_json}};
window.VEFR_FLAGS = {{flags_json}};
window.VEFR_CLAIMS = {{claims_json}};
window.VEFR_PEOPLE = {{people_json}};
// The pack's optional stakes (vefr#504): the risk/reward offers THIS
// pack puts to the player, one
// `{"id", "when": <a rule's when>, "risk", "reward", "say"}` each, and
// asked for by the same events a rule hears. The literal null for a
// pack that declares none - which is every pack that never opted in -
// so nothing is offered anywhere by default.
window.VEFR_STAKES = {{stakes_json}};
// The pack's optional sticker album (design/album.md), baked beside
// the rule data. The literal null when the pack declares no album, so
// every existing pack weaves exactly as it did.
window.VEFR_ALBUM_DEF = {{album_json}};
// The pack's optional sound set (docs/guides/rulesets.md): the literal
// null when the pack declares no sound, so every existing pack weaves
// exactly as it did.
window.VEFR_SOUND_DEF = {{sound_json}};
// The pack's optional ambient music (vefr#502): the literal null when the
// pack declares none, so every pack that did not opt in weaves and sounds
// exactly as it did.
window.VEFR_MUSIC_DEF = {{music_json}};
// Where the game begins: {"region": "...", "at": [x, y]}. Empty when the
// act does not say, and then the first region's own hero_start is used.
window.VEFR_START = {{start_json}};
// The door picture: drawn at each transition tile so a way out is not an
// invisible hole in the floor. Empty when the engine has no door art.
window.VEFR_DOOR = {{door_json}};
// A pack's own way pictures by kind (door, stairs-up, stairs-down, trapdoor), and per region.
window.VEFR_WAY_ICONS = {{way_icons_json}};
window.VEFR_REGION_WAY_ICONS = {{region_way_icons_json}};
// Each region's prop pictures by name ({} for a pack with no props).
window.VEFR_PROP_PICS = {{prop_pics_json}};
// Book markers ('map', 'resident'): drawn where a book you have not found
// can be found, so a book is not invisible.
window.VEFR_BOOK_ICONS = {{book_icons_json}};
// The chest picture: a book with `chest: yes` is opened (used) instead of
// stepped on, and drawn as a chest on the floor.
window.VEFR_CHEST_ICON = {{chest_json}};
// The living hazards, keyed by region. Each is
// {id, name, at, hp, atk, sprite} (sight only when the contract names
// it; the player defaults to 6). A region that names none bakes [].
window.VEFR_ENEMIES = {{enemies_json}};
// The hero's own numbers and wake point:
// {"hp": 6, "atk": 2, "wake": {"region": "...", "at": [x, y]}}. Cozy
// death restores the max and wakes the hero at `wake`. A pack whose
// `player.library_url` names an http(s) shelf carries it here too, and
// the pause menu shows a way back; no key for a pack that names none.
window.VEFR_HERO = {{hero_json}};
window.VEFR_SKIN = {{skin_json}};
window.VEFR_GROWTH = {{growth_json}};
// The pack's optional spells block (ADR 0018): {"schools": [...],
// "spells": [{"id", "name", "school", "level?", "heal?"}]}. Every word in
// it is the pack's own. A pack that declares none carries no line at all,
// so it reads as no spells - the hero learns nothing by level and a book
// teaches nothing.
window.VEFR_SPELLS = {{spells_json}};

// The woven pool - real model output baked in at weave time
// (--pool N). Drawn when no live endpoint answers; see poolDraw.
window.VEFR_POOL = {{pool_json}};

// The offline whisper banks - per-speaker fragments written by the
// author (voices/<name>.fragments.md). The composer's last resort
// before honest silence: no pool at all, no model, but the pack's
// own words. See composeFromFragments.
window.VEFR_FRAGMENTS = {{fragments_json}};

// The pack's own grammars, baked from world.json `grammars`: a set of
// hand-written sentence recipes expanded here, offline. `whisper`
// speaks when there is no endpoint, no pool, and no fragment bank;
// `weather` says on arriving in a region; `name` names things. Empty
// when the pack carries none. See grammarExpand.
window.VEFR_GRAMMARS = {{grammars_json}};

