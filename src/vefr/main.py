from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .replies import (CommissionsReply, DeferReply, EventReply, GotItReply, LibraryReply,
                      ModeReply, StickerBook, TeachReply, TeachState)

import html
import json
import os
import re
import threading
from datetime import date, datetime, timezone
from pathlib import Path

from . import (
    combat,
    desk,
    enhance,
    forge,
    inspect as inspect_mod,
    journal,
    lore,
    sessions,
    starred,
    trace,
)
from .stefna import generate_letter
from .export import export_story
from .forge import ItemCard, forge_item, keep_item, list_vault
from .generator import generate_rumor
from .npc import generate_line
from .paths import app_home, safe_pack_name, data_dir, resolve_under
from .world import load_world, current_act

PURPOSE = "a rumor engine for playable worlds"


def _app_title() -> str:
    try:
        return load_world()["title"]
    except Exception:
        return "vefr"


app = FastAPI(title=_app_title(), version="2.0.0", description=PURPOSE.capitalize())

# VEFR as a Worlds room (Play-Nice room/0): its Library, for Worlds to gather.
from .room import _Refused as _RoomRefused, refused_handler as _room_refused, router as _room_router  # noqa: E402

app.include_router(_room_router)
app.add_exception_handler(_RoomRefused, _room_refused)
WEB = app_home() / "web"


class _WebStatics(StaticFiles):
    """Serve web/ assets with revalidate-on-every-use.

    The plain StaticFiles mount ships ETags but no Cache-Control, so
    browsers heuristic-cache the UI and serve stale HTML/CSS/JS while
    we iterate. "no-cache" keeps 304 revalidation (fast) but never a
    stale 200.
    """

    def file_response(self, *args, **kwargs):
        resp = super().file_response(*args, **kwargs)
        resp.headers["Cache-Control"] = "no-cache"
        return resp


if WEB.is_dir():
    app.mount("/static", _WebStatics(directory=str(WEB)), name="static")
# The reading row's "What does that mean?" link points at the
# glossary under docs/guides/. Serve the guides read-only so the
# link lands on the file instead of a 404 (dev checkouts + container
# installs that ship docs/ alongside web/).
DOCS = app_home() / "docs" / "guides"
if DOCS.is_dir():
    app.mount("/docs/guides", StaticFiles(directory=str(DOCS)), name="guides")


class RumorRequest(BaseModel):
    phase: str = "whispers"
    theme: str | None = None


class NpcRequest(BaseModel):
    phase: str = "whispers"
    speaker: str | None = None  # None -> the pack's first speaker


@app.get("/api/health")
def health():
    return {"ok": True, "service": "vefr", "purpose": PURPOSE}


@app.post("/api/rumor")
def rumor(req: RumorRequest, session: str = ""):
    with trace.span("/api/rumor", phase=req.phase, session=session or "default") as sp:
        card = generate_rumor(req.phase, req.theme, sid=session or None)
        sp.set(speaker=card.speaker)
    journal.log(
        "rumor",
        sid=session,
        phase=req.phase,
        speaker=card.speaker,
        whisper=card.whisper,
        is_true=card.is_true,
    )
    return card


@app.post("/api/forge")
def forge_roll():
    with trace.span("/api/forge"):
        return forge_item()


@app.post("/api/vault")
def vault_keep(item: ItemCard, session: str = ""):
    """A typed body, not a bare dict: a shape error is a 422 naming
    the missing field. The route used to model_validate a bare dict
    and answered a caller's typo with a bare 500."""
    result = keep_item(item, sid=session)
    # Only a kept item is journalled - a forge roll nobody took is a
    # thing that never happened.
    journal.log("item_forged", sid=session, name=item.name, bond=item.bond, lore=item.lore)
    return result


@app.get("/api/vault")
def vault_list(session: str = ""):
    items = list_vault(sid=session)
    return {"items": items, "starred": starred.list_starred()}


@app.post("/api/vault/star/{index}")
def vault_star(index: int, session: str = ""):
    """Star a kept vault item - same shape as the journal star route."""
    from fastapi import HTTPException

    items = list_vault()
    if index < 0 or index >= len(items):
        raise HTTPException(status_code=404, detail=f"no vault item at index {index}")
    return starred.star(
        {
            "kind": "item_forged",
            "name": items[index].get("name", ""),
            "lore": items[index].get("lore", ""),
            "speaker": "",
        }
    )


@app.post("/api/vault/remove/{index}")
def vault_remove(index: int, session: str = ""):
    """Drop a kept item from the vault; undoable for 60s."""
    from fastapi import HTTPException

    removed = forge.remove(index, sid=session)
    if removed is None:
        raise HTTPException(status_code=404, detail=f"no vault item at index {index}")
    return {"removed": True, "item": removed, "undo_window_s": forge.UNDO_WINDOW_S}


@app.post("/api/vault/undo")
def vault_undo(session: str = ""):
    """Restore the most recently removed vault item."""
    from fastapi import HTTPException

    restored = forge.undo(sid=session)
    if restored is None:
        raise HTTPException(
            status_code=400,
            detail="nothing to undo - either nothing was removed, "
            f"or the {forge.UNDO_WINDOW_S}s window has elapsed",
        )
    return {"restored": True, "item": restored}


@app.post("/api/stefna")
def stefna(session: str = ""):
    with trace.span("/api/stefna", session=session or "default"):
        letter = generate_letter()
    journal.log("stefna_letter", sid=session, letter=letter.letter)
    return letter


@app.post("/api/npc")
def npc(req: NpcRequest, session: str = ""):
    """An unknown speaker (or a voice-less pack) is a 404 in plain
    English - the engine's own words, not a RuntimeError 500."""
    from fastapi import HTTPException

    try:
        with trace.span("/api/npc", phase=req.phase, session=session or "default") as sp:
            spoken = generate_line(req.phase, req.speaker, sid=session or None)
            sp.set(speaker=spoken.speaker)
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    journal.log("npc_line", sid=session, phase=req.phase, speaker=spoken.speaker, line=spoken.line)
    return spoken


class CombatAction(BaseModel):
    kind: str
    phase: str | None = None
    target: str | None = None


@app.post("/api/combat/action")
def combat_action(req: CombatAction, session: str = ""):
    """Record a combat action (attack, console, hurl, ...).

    The action is just a journal entry. The HUD has whatever
    costume it wants (HP bar, encounter prompt, verb buttons);
    the engine doesn't change any game state. The surface is
    a costume, the costume is the point.
    """
    with trace.span(
        "/api/combat/action",
        kind=req.kind,
        phase=req.phase or "default",
        session=session or "default",
    ):
        try:
            entry = combat.record_combat_action(
                kind=req.kind,
                phase=req.phase,
                target=req.target,
                session=session,
                allowed=combat.verbs_for_pack(load_world()),
            )
        except ValueError as e:
            from fastapi import HTTPException

            raise HTTPException(status_code=400, detail=str(e))
    return entry


class DeskVerify(BaseModel):
    whisper: str
    verdict: str


class DeskPrint(BaseModel):
    headline: str


@app.post("/api/desk/verify")
def desk_verify(req: DeskVerify, session: str = ""):
    """Judge a whisper this session heard. The engine compares the
    verdict against the truth it actually sent - the Desk is where
    is_true finally gets consumed."""
    from fastapi import HTTPException

    try:
        return desk.verify(session or None, req.whisper, req.verdict)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/api/desk/print")
def desk_print(req: DeskPrint, session: str = ""):
    """Print a headline. What the paper says, the world hears:
    later prompts carry the printed list."""
    from fastapi import HTTPException

    try:
        entry = desk.print_headline(session or None, req.headline)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return entry


@app.get("/api/desk/facts")
def desk_facts(session: str = ""):
    """The session's derived world knowledge: confirmed, debunked,
    printed. Replay of the journal - always honest, never stale."""
    return {"facts": desk.facts(session or None)}


@app.get("/api/world")
def world():
    """The town payload - everything the renderer needs, from the pack.

    Returns the always-array shape: the world's metadata at the top
    level, plus `act` (the current act) and `regions` (named regions
    of the current act). The renderer is a single-region experience
    in this PR; `regions.town` is the same data the legacy
    `town` block used to expose, so the web layer can read either
    path during the migration.
    """
    w = load_world()
    act = current_act(w)
    region = act["regions"].get("town", {})
    # Town metadata can come from three places, in priority order:
    #   1. The region's contract.json (acts shape, convention-driven)
    #   2. The act's _town_legacy (acts shape, transitional)
    #   3. The legacy flat-shape town block (in _town_legacy too)
    # The contract wins so a future PR can move the canary's
    # data to town/contract.json without the API route changing.
    legacy = act.get("_town_legacy", {}) or region.get("contract", {})
    # The map lives in one of two places: the region's map_text
    # (acts shape, served by the loader from town/map.md) or the
    # legacy block's `map` key (flat shape, served from the
    # pack-level world.json). Union them so the web layer doesn't
    # care which shape the pack is in.
    raw_map = region.get("map_text", "") or "\n".join(legacy.get("map", []))
    town_map = [ln for ln in raw_map.splitlines() if ln.strip()]
    speakers = [
        {
            "key": key,
            "name": spec["name"],
            "at": spec["at"],
            "near": spec["near"],
            "seeds": spec.get("seeds", {}),
        }
        for key, spec in act["speakers"].items()
    ]
    return {
        "title": w["title"],
        "creed": w.get("creed", ""),
        "phases": list(w["phases"].keys()),
        "surface": w["surface"],
        "hp": combat.hp_for_pack(w) if w["surface"] == "combat" else None,
        "act": {
            "id": act["id"],
            "title": act["title"],
            "verbs": combat.verbs_for_pack({"acts": [act]}) if act.get("verbs") else [],
            "floor": act.get("floor", "costume"),
            "tone": act.get("tone", ""),
            "ruleset": act.get("ruleset", "ambient"),
        },
        "regions": {"town": {"map_text": town_map}},
        "tile": legacy.get("tile", 32),
        "bg": legacy.get("bg", "#131311"),
        "map": town_map,
        "legend": legacy.get("legend", {}),
        "pois": legacy.get("pois", {}),
        "hero_start": legacy.get("hero_start", [1, 1]),
        "hero_color": legacy.get("hero_color", "#e8e5df"),
        "watch": legacy.get("watch", {}),
        "sanctuary_tiles": legacy.get("sanctuary_tiles", []),
        "water_by_phase": legacy.get("water_by_phase", {}),
        "flood_tiles": legacy.get("flood_tiles", []),
        "speakers": speakers,
        "speaker_color": legacy.get("speaker_color", "#8b939c"),
        "speaker_head": legacy.get("speaker_head", "#d8d5cf"),
    }


@app.get("/api/journal")
def journal_list(session: str = ""):
    entries = journal.list_entries(sid=session)
    return {
        "entries": entries,
        "starred": starred.list_starred(),
    }


@app.post("/api/journal/star/{index}")
def journal_star(index: int, session: str = ""):
    """Append the entry at `index` to starred-whispers.md in the pack.

    The file lands on disk in the same place as logbok.md - next
    `ratatoskr ferry fetch --pull` ships it to the deploy host. Idempotent:
    starring the same entry twice appends a second line.
    """
    entries = journal.list_entries(sid=session)
    if index < 0 or index >= len(entries):
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=f"no journal entry at index {index}")
    return starred.star(entries[index])


@app.post("/api/journal/remove/{index}")
def journal_remove(index: int, session: str = ""):
    """Remove one journal entry. Refuses the last entry of its kind.

    The removed entry is stashed server-side for one minute; call
    /api/journal/undo within that window to bring it back.
    """
    from fastapi import HTTPException

    try:
        removed = journal.remove(index, sid=session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if removed is None:
        raise HTTPException(status_code=404, detail=f"no journal entry at index {index}")
    return {"removed": True, "entry": removed, "undo_window_s": journal.UNDO_WINDOW_S}


@app.post("/api/journal/undo")
def journal_undo(session: str = ""):
    """Restore the most recently removed entry, if still in the undo window."""
    from fastapi import HTTPException

    restored = journal.undo(sid=session)
    if restored is None:
        raise HTTPException(
            status_code=400,
            detail="nothing to undo - either nothing was removed, "
            f"or the {journal.UNDO_WINDOW_S}s window has elapsed",
        )
    return {"restored": True, "entry": restored}


@app.post("/api/journal/clear")
def journal_clear(session: str = ""):
    journal.clear(sid=session)
    return {"cleared": True}


class RewindRequest(BaseModel):
    at: int  # keep entries[:at] - same semantics as the fork's cut


class ForkRequest(BaseModel):
    at: int  # keep entries[:at]


class MoveRequest(BaseModel):
    """One arrival the town renderer witnessed.

    `poi` is where the hero stands (a place name from the pack, or
    the world title when between places); `x`/`y` are tile
    coordinates; `phase` is the world's phase at the moment of
    arrival. The client only posts on change of place, never per
    tile - a walk logs visits, not footsteps.
    """

    poi: str
    x: int
    y: int
    phase: str | None = None


@app.post("/api/journal/move")
def journal_move(req: MoveRequest, session: str = ""):
    """Journal one arrival - where the hero actually stood.

    The town renderer posts this when the place under the hero
    changes, so the export's "The Fen Walked" section can witness
    the journey the way it witnesses whispers and lines. Pure
    bookkeeping: no model call, no validation against the map -
    the client is the only thing that knows where the hero is.
    """
    entry = journal.log(
        "move",
        sid=session,
        poi=req.poi,
        x=req.x,
        y=req.y,
        phase=req.phase,
    )
    return {"logged": True, "entry": entry}


@app.post("/api/journal/rewind")
def journal_rewind(req: RewindRequest, session: str = ""):
    """Cut the journal back to entries[:at]; the tail is undoable 60s.

    The vault is left untouched: possessions were forged before the
    cut, and the UI confirms before calling.
    """
    from fastapi import HTTPException

    result = journal.rewind(req.at, sid=session)
    if result is None:
        raise HTTPException(status_code=404, detail=f"nothing to rewind at {req.at}")
    result["undo_window_s"] = journal.UNDO_WINDOW_S
    return result


@app.post("/api/journal/rewind/undo")
def journal_rewind_undo(session: str = ""):
    """Bring back the tail of the most recent rewind, within the window."""
    from fastapi import HTTPException

    restored = journal.rewind_undo(sid=session)
    if restored is None:
        raise HTTPException(
            status_code=400,
            detail="nothing to undo - either nothing was rewound, "
            f"or the {journal.UNDO_WINDOW_S}s window has elapsed",
        )
    return restored


@app.post("/api/journal/fork")
def journal_fork(req: ForkRequest, session: str = ""):
    """Copy journal[:at] + the vault into a new session; parent pointer kept.

    The current session is never modified - forking branches, never
    cuts. The new session's journal opens with one `fork` entry
    describing where it came from, and sessions/<sid>.meta.json
    records the parent for tooling.
    """
    entries = journal.list_entries(sid=session)
    at = max(0, min(req.at, len(entries)))
    new_sid = sessions.new_id()
    journal.set_entries(entries[:at], sid=new_sid)
    forge.set_vault(forge.list_vault(sid=session), sid=new_sid)
    parent = sessions.clean(session)
    sessions.write_meta(
        new_sid,
        {"parent": parent, "fork_at": at, "at": sessions.now_iso()},
    )
    label = "the default playthrough" if sessions.is_default(session) else f"session {parent}"
    journal.log(
        "fork",
        sid=new_sid,
        parent=parent,
        fork_at=at,
        note=f"forked from {label} with {at} entries kept",
    )
    return {
        "session": new_sid,
        "parent": parent,
        "fork_at": at,
        "kept": at,
        "url": f"/?session={new_sid}",
    }


# --------------------------------------------------------------- builder

# The builder surface in the web UI: stateless turn-based chat with
# the local model, plus thin wrappers around vefr's import/validate/
# verify commands. The web UI holds the conversation history; the
# server is just "given the history so far, write the next line".
# Same `chat.draft()` machinery as the CLI interview, but driven by
# fetch() from the page instead of input() in a terminal.

BUILDER_SYSTEM = (
    "You are a warm, curious world-building collaborator helping "
    "an author shape their own story. Plain prose, never purple, "
    "never a lecture. Reply with one short paragraph (2-5 sentences) "
    "or one short list. If the author is stuck, ask a focused question. "
    "Stay grounded in the pack they're editing - if they reference "
    "a character or place by name, treat that as part of their canon. "
    "Never invent facts about the story; when you don't know, ask. "
    "You propose edits and directions; you do not commit canon or mutate the pack."
)


class BuilderChatTurn(BaseModel):
    message: str
    history: list[dict] = []  # [{role, content}] pairs
    world: str | None = None  # pack to focus on (None = current)


@app.post("/api/builder/chat")
def builder_chat(turn: BuilderChatTurn):
    """One turn of the builder-mode chat. Stateless, proposal-only."""
    from .chat import draft

    # `world` names the pack this turn focuses on (None = current). It
    # isn't read further yet, but a traversal-shaped value must still
    # never be accepted by a builder route.
    _safe_world_name(turn.world)

    # Replay the history briefly so the model has context. We keep it
    # short - the page holds the long view.
    context_lines = []
    for h in turn.history[-6:]:
        if h.get("role") in ("user", "assistant") and h.get("content"):
            who = "Author" if h["role"] == "user" else "Builder"
            context_lines.append(f"{who}: {h['content']}")
    context = "\n".join(context_lines)
    prompt = turn.message
    if context:
        prompt = f"(recent conversation)\n{context}\n\nAuthor: {turn.message}"
    text = draft(prompt, system=BUILDER_SYSTEM)

    return {"reply": text}


class AchievementEvent(BaseModel):
    event: str               # a name the sticker book listens for (visit, room_visit, map_paint, ...)
    data: dict = {}          # short plain fields, e.g. {"room": "map"}
    local: dict = {}         # the person's own clock: date, hour, minute, weekday (Mon=0)


@app.post("/api/achievements/event", response_model=EventReply)
def achievements_event(ev: AchievementEvent):
    """Tally something the author did in the studio; say which stickers were just earned."""
    from . import achievements

    try:
        out = achievements.record(ev.event, ev.data, ev.local)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"earned": [{k: d[k] for k in ("id", "name", "how", "group", "kind", "shine")} for d in out["earned"]],
            "total": out["total"]}


@app.get("/api/achievements", response_model=StickerBook)
def achievements_book():
    """Ratatoskr's sticker book: every sticker, earned or not (secrets stay ???)."""
    from . import achievements

    return achievements.book()


class TeachTurn(BaseModel):
    message: str  # the author's own words from the turn the builder just answered


class TeachTerm(BaseModel):
    term: str


@app.post("/api/teach/recognize", response_model=TeachReply)
def teach_recognize(turn: TeachTurn):
    """After a builder reply: did the author just use a design idea Fróði can name?

    Called by the page after the reply is shown (never blocks it). Returns
    {"teach": card | null, "why_not": reason}; a card is recorded as offered.
    """
    from . import teach
    from .room import load_glossary

    return teach.recognize(turn.message, load_glossary())


@app.post("/api/teach/got-it", response_model=GotItReply)
def teach_got_it(req: TeachTerm):
    """The author tapped Got it: two of those and the idea counts as familiar."""
    from . import teach
    from .room import load_glossary

    if req.term not in teach.teachable(load_glossary()):
        raise HTTPException(status_code=404, detail="that isn't an idea Fróði teaches")
    rec = teach.record_got_it(req.term)
    return {"term": req.term, "stage": teach.stage(rec), "got_it": rec["got_it"]}


@app.get("/api/teach", response_model=TeachState)
def teach_state():
    """Every idea Fróði teaches, with where this person is with each."""
    from . import teach
    from .room import load_glossary

    seen = teach.load()["concepts"]
    out = {}
    for key, e in teach.teachable(load_glossary()).items():
        rec = seen.get(key)
        out[key] = {"group": e["teach"], "stage": teach.stage(rec) if rec else "new",
                    "offered": (rec or {}).get("offered", 0), "got_it": (rec or {}).get("got_it", 0),
                    "first_context": (rec or {}).get("first_context", "")}
    home = teach.worlds("GET", "/api/learning")
    mode = teach.MODE_FROM_WORLDS.get((home or {}).get("mode"))
    return {"concepts": out, "mode": mode}


class TeachMode(BaseModel):
    mode: str  # build | tips | off (VEFR's words for Worlds' build | occasional | plain)


@app.put("/api/teach/mode", response_model=ModeReply)
def teach_mode(req: TeachMode):
    """Fróði's notes setting, written through to Worlds so one person has one switch."""
    from . import teach

    if req.mode not in teach.MODE_TO_WORLDS:
        raise HTTPException(status_code=422, detail="mode must be build, tips or off")
    home = teach.worlds("PUT", "/api/learning/mode", {"mode": teach.MODE_TO_WORLDS[req.mode]})
    return {"mode": req.mode, "shared": bool(home)}


@app.get("/api/spark/health")
def spark_health_route():
    """Spark's liveness as VEFR sees it: up, down, or timed out.

    A graded payload, never an exception - a dead Spark is a state of
    the world the UI can show, not a 500. The probe also records the
    round-trip so 'slow but alive' is distinguishable from 'gone'.
    """
    from . import spark as spark_mod

    try:
        probe = spark_mod.health()
        return {
            "ok": True,
            "spark": "available",
            **probe,
            "profile": spark_mod.profile()["key"],
            "model": spark_mod.profile()["alias"],
        }
    except Exception as exc:  # noqa: BLE001 - down is data, not a crash
        return {
            "ok": False,
            "spark": "unavailable",
            "url": spark_mod.spark_url(),
            "error": f"{exc.__class__.__name__}: {exc}",
            "profile": spark_mod.profile()["key"],
        }


class SparkTaskRequest(BaseModel):
    task: str  # a TASK_CONTRACTS key: npc, state_edit, dialogue, lore, narrate
    user: str  # the task's own payload, in the task's language
    speaker: str | None = None
    state: dict | None = None
    world: bool = True


@app.post("/api/spark/task")
def spark_task(req: SparkTaskRequest):
    """The production Spark path: context in, validated result out.

    Fail-closed by design - SparkUnreachable and schema failures come
    back as graded payloads naming the escalation path, never as an
    applied guess. The model proposes; this route validates; VEFR
    applies. `escalated=true` names a response VEFR routed to K2
    instead (the generator seam), so a Spark outage degrades to the
    pre-Spark behavior rather than an error.
    """
    from . import spark as spark_mod

    if req.task not in spark_mod.TASK_CONTRACTS:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=422,
            detail=f"unknown spark task {req.task!r}; known: {sorted(spark_mod.TASK_CONTRACTS)}",
        )
    try:
        result, meta = spark_mod.spark_call(
            req.task, req.user, speaker=req.speaker, state=req.state
        )
        meta.pop("response", None)  # the debug view lives in inspect
        return {"ok": True, "spark": "ok", "result": result, "meta": meta, "escalated": False}
    except spark_mod.SparkUnavailable as exc:
        return {
            "ok": False,
            "spark": "unavailable",
            "error": f"{exc.__class__.__name__}: {exc}",
            "escalated": False,
            "hint": "escalate to K2 or degrade",
        }
    except spark_mod.SparkMalformed as exc:
        # Spark answered twice with garbage. That is data about Spark,
        # not a license to apply an unvalidated proposal: fail closed,
        # offer the K2 path.
        return {"ok": False, "spark": "malformed", "error": f"{exc}", "escalated": False}


@app.get("/api/spark/inspect")
def spark_inspect(task: str, user: str, speaker: str | None = None, call: bool = False):
    """Development view of the Context Builder (read-only by default).

    Shows the profile, model, context sections, approximate prompt
    size, and the exact messages Spark would receive - the answer to
    'did the model fail, or did VEFR give it bad context?'. With
    call=true it also runs the task and returns the response plus the
    validation result. Never mutates anything.
    """
    from . import spark as spark_mod
    from fastapi import HTTPException

    if task not in spark_mod.TASK_CONTRACTS:
        raise HTTPException(
            status_code=422,
            detail=f"unknown spark task {task!r}; known: {sorted(spark_mod.TASK_CONTRACTS)}",
        )
    view = spark_mod.inspect_context(task, user, speaker=speaker)
    if not call:
        return {"ok": True, **view}
    try:
        result, meta = spark_mod.spark_call(task, user, speaker=speaker)
        return {"ok": True, **view, "validation": "ok", "response": meta.get("response", "")}
    except spark_mod.SparkUnavailable as exc:
        return {"ok": False, **view, "validation": f"unavailable: {exc}"}
    except spark_mod.SparkMalformed as exc:
        return {"ok": False, **view, "validation": f"malformed: {exc}"}


@app.post("/api/spark/escalate")
def spark_escalate():
    """Run the escalation self-check: the benchmark's fixed probes
    through the live Spark, scored against known ground truth. The
    integrated answer to 'does the resident model still know what is
    not its job?' - and, transitively, whether the K2 path it names is
    still the escalation target."""
    from . import spark as spark_mod

    try:
        decisions = spark_mod.classify_escalation(spark_mod.ESCALATION_PROBES)
        ok, detail = spark_mod.escalation_verdict(decisions)
        return {
            "ok": ok,
            "escalation": detail,
            "decisions": [d.model_dump() for d in decisions],
            "escalation_target": "K2 via VEFR_LLAMACPP_URL",
        }
    except spark_mod.SparkUnavailable as exc:
        return {"ok": False, "error": f"{exc}", "decisions": []}


@app.get("/api/library", response_model=LibraryReply)
def library_shelves(world: str | None = None):
    """The Library: the current world's books and the studio's own shelf.

    Books are authored markdown (worlds/<name>/library/*.md and the
    engine's web/library/*.md); nothing here calls a model. Each book
    carries its pages and how it is found, in words, for the reader.
    """
    from .library import found_words, load_library, load_shelf, studio_shelf_dir
    from .paths import pack_dir

    try:
        name = safe_pack_name(world)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    try:
        w = load_world(name)
        pack = pack_dir(name)
        world_books = load_library(pack)
        title = w.get("title", "")
    except Exception:  # a missing or broken pack still shows the studio shelf
        world_books, title = [], ""

    def shape(b: dict) -> dict:
        return {k: b[k] for k in ("id", "title", "kind", "found", "at", "speaker", "when", "pages")} | {
            "found_words": found_words(b), "shelf": str((b.get("extra") or {}).get("shelf", ""))}

    return {
        "world": title,
        "books": [shape(b) for b in world_books],
        "studio": [shape(b) for b in load_shelf(studio_shelf_dir())],
    }


# The features catalog is read-only. `pack`, when given, is a request
# value that becomes a path segment: it is held to a bare lowercase
# world name before worlds_dir() joins it, so "../elsewhere" and an
# absolute path are refused at the edge and never joined.
_FEATURES_PACK_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


@app.get("/api/features")
def features_report(pack: str | None = None):
    """What VEFR can do, and (with `pack`) what one world uses.

    No `pack`: the catalog alone, `features.report(None)`. A named
    pack must be a bare world name (letters, digits and dashes) that
    resolves under worlds/; a path-shaped name is a 400, an unknown
    world a 404. Deterministic: no model call ever runs here.
    """
    from . import features
    from .paths import worlds_dir

    if pack is None:
        return features.report(None)
    if not _FEATURES_PACK_RE.match(pack):
        raise HTTPException(
            status_code=400,
            detail="pack must be a bare world name (letters, digits and dashes)",
        )
    world = resolve_under(worlds_dir(), pack)
    if not (world / "world.json").is_file():
        raise HTTPException(status_code=404, detail=f"no world named {pack!r}")
    return features.report(world)


@app.get("/api/runes")
def runes_registry():
    """The full 24-rune Elder Futhark registry for the gallery view.

    Each rune includes its stave (the carved shape), aettir,
    short meaning, long meaning, and the engine phase it anchors.
    The web UI uses this to render the rune gallery - the player
    can see all 24 staves + meanings at a glance.
    """
    from .runes import RUNES, PHASE_ANCHOR

    return {
        "runes": [
            {
                "name": r.name,
                "stave": r.stave,
                "aettir": r.aettir,
                "short": r.short,
                "long": r.long,
                "engine_phase": r.engine_phase,
            }
            for r in RUNES
        ],
        "anchors": {
            phase: {"name": r.name, "stave": r.stave, "short": r.short}
            for phase, r in PHASE_ANCHOR.items()
        },
    }


@app.get("/api/runes/cast")
def runes_cast(phase: str | None = None):
    """Today's cast - three runes for the current moment.

    Seeded from (world_name, current ISO minute). Same cast within
    a session-minute; new cast every minute. The model sees this
    same cast in its system prompt; the player sees it in the UI.
    Pass ?phase=X to get the cast for a specific phase.
    """
    from datetime import datetime, timezone
    from .runes import cast_for, render_for_prompt, seed_for

    pack_phases = list(load_world().get("phases", {}).keys())
    if not phase:
        phase = pack_phases[0] if pack_phases else "whispers"
    iso_minute = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M")
    seed = seed_for("api.runes.cast", phase, iso_minute)
    cast_result = cast_for(seed, phase=phase)
    return {
        "phase": phase,
        "seed": seed,
        "iso_minute": iso_minute,
        "positions": [
            {"position": pos, "name": r.name, "stave": r.stave, "short": r.short, "long": r.long}
            for pos, r in cast_result
        ],
        "prompt_block": render_for_prompt(cast_result),
    }


@app.post("/api/builder/lore")
def builder_lore(req: lore.LorePreviewRequest):
    """Preview a lore pack's mood-board for a topic + seeds.

    Reads the pack's textures.md / names.md / questions.md,
    threads them through one LLM call, returns the wandering-poets
    shape: {textures, names[], questions[]}. No canonical fields -
    lore is mood, not canon.
    """
    from fastapi import HTTPException
    from .lore import preview_lore

    # A lore pack is still a bare pack name: worlds/lore/<lore>/ is
    # joined from this value in lore.py, so same rule as a world.
    _safe_world_name(req.lore)

    try:
        result = preview_lore(req)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return result.model_dump()


@app.post("/api/builder/lore/list")
def builder_lore_list():
    """Every lore pack with a manifest of files."""
    from .lore import list_lore

    return [_e.model_dump() for _e in list_lore()]


@app.get("/api/builder/worlds")
def builder_worlds():
    """Every pack under worlds/ that has a world.json.

    Surfaces the engine-shipped packs (sample-world + lore packs)
    alongside any pack the author has imported via `ferry fetch`.
    The page uses this to populate the world picker in the Builder
    tab.
    """
    from .world import discover_packs

    out = []
    for entry in discover_packs():
        p = Path(entry["path"])
        try:
            w = json.loads((p / "world.json").read_text(encoding="utf-8"))
            # Acts-shape packs put speakers inside the per-act
            # contract; flat packs put them at the top level.
            speakers: list[str] = []
            if (p / "acts").is_dir():
                for ad in sorted((p / "acts").iterdir()):
                    if not ad.is_dir() or ad.name.startswith("."):
                        continue
                    act_w = json.loads((ad / "world.json").read_text(encoding="utf-8"))
                    speakers.extend(act_w.get("speakers", {}).keys())
            else:
                speakers = list(w.get("speakers", {}).keys())
            out.append(
                {
                    "name": entry["name"],
                    "title": w.get("title", entry["name"]),
                    "phases": list(w.get("phases", {}).keys()),
                    "speakers": speakers,
                    "source": entry["source"],
                }
            )
        except (json.JSONDecodeError, OSError):
            continue
    return {"worlds": out}


def _sample_scaffold():
    """The engine-shipped sample pack a new world is copied from.

    Template mount first (container installs), then the rw canon
    mount (dev checkouts ship sample-world under worlds/). None when
    neither tree has it, so the caller can say so plainly.
    """
    from .paths import template_dir, worlds_dir

    for base in (template_dir(), worlds_dir()):
        cand = base / "sample-world"
        if (cand / "world.json").is_file():
            return cand
    return None


class BuilderWorldCreateRequest(BaseModel):
    name: str
    title: str | None = None
    premise: str | None = None


class BuilderWorldActiveRequest(BaseModel):
    name: str


@app.post("/api/builder/worlds")
def builder_worlds_create(req: BuilderWorldCreateRequest):
    """Start a new world from the served UI - the phone user's `norns chat`.

    The same scaffold copy and the same world.json fields the CLI
    interview would set, with no terminal involved. `name` must be a
    bare pack name (never a path), an existing name is refused rather
    than overwritten, and the new world becomes the active one so the
    Desk shows it immediately.
    """
    from .chat import create_world
    from .paths import set_active_world, worlds_dir

    name = _safe_world_name(req.name.strip())
    if not name:
        raise HTTPException(status_code=400, detail="world must be a bare pack name")
    dest = resolve_under(worlds_dir(), name)
    if dest.exists():
        raise HTTPException(status_code=409, detail=f"a world named {name!r} already lives here")
    scaffold = _sample_scaffold()
    if scaffold is None:
        raise HTTPException(status_code=500, detail="the sample-world scaffold is missing")
    try:
        create_world(
            dest,
            scaffold,
            title=(req.title or "").strip() or None,
            premise=(req.premise or "").strip() or None,
        )
    except FileExistsError:
        raise HTTPException(status_code=409, detail=f"a world named {name!r} already lives here")
    try:
        title = json.loads((dest / "world.json").read_text(encoding="utf-8")).get("title", name)
    except (json.JSONDecodeError, OSError):
        title = name
    set_active_world(name)
    load_world.cache_clear()
    return {"name": name, "title": title}


@app.post("/api/builder/worlds/active")
def builder_worlds_active(req: BuilderWorldActiveRequest):
    """Switch the world the engine serves - no restart.

    Validates a bare pack name that resolves to a real pack under
    either mount, records it as the runtime override (in memory + a
    small file under data/), and returns the newly active world.
    VEFR_WORLD still beats this when the operator sets it; the
    override only fills the gap the env var used to require a restart
    for.
    """
    from .paths import set_active_world, template_dir, worlds_dir

    name = _safe_world_name(req.name.strip())
    if not name:
        raise HTTPException(status_code=400, detail="world must be a bare pack name")
    pack = resolve_under(worlds_dir(), name)
    if not (pack / "world.json").is_file():
        pack = resolve_under(template_dir(), name)
    if not (pack / "world.json").is_file():
        raise HTTPException(status_code=404, detail=f"no world named {name!r}")
    pinned = os.environ.get("VEFR_WORLD")
    if pinned and pinned != name:
        # The operator's env always wins (paths.world_name), so saying
        # "active" here would be a lie: the page would keep serving the
        # pinned world. Refuse, and say how to unpin.
        raise HTTPException(status_code=409, detail=(
            f"This studio is pinned to {pinned!r} by its server settings "
            "(VEFR_WORLD). Remove that setting and restart the studio to "
            "switch worlds from the page."))
    set_active_world(name)
    load_world.cache_clear()
    try:
        title = json.loads((pack / "world.json").read_text(encoding="utf-8")).get("title", name)
    except (json.JSONDecodeError, OSError):
        title = name
    return {"name": name, "title": title, "active": True}


@app.post("/api/builder/import")
def builder_import(payload: dict):
    """Thin wrapper around `ratatoskr ferry fetch --pull`.

    Payload: {repo: 'owner/name', name: 'your-pack-name'}
    """
    from .cli import GITEA_BASE, cmd_import
    import argparse

    args = argparse.Namespace(
        repo=payload.get("repo", ""),
        name=_safe_world_name(payload.get("name")),
        base=payload.get("base", GITEA_BASE),
        target=payload.get("target", "local"),
        pull=payload.get("pull", True),
        dry_run=False,
    )
    rc = cmd_import(args)
    return {"rc": rc}


@app.post("/api/builder/validate")
def builder_validate(payload: dict):
    """Run maplab.validate on the named pack."""
    from .maplab import load_pack, validate
    from .paths import pack_dir

    name = _safe_world_name(payload.get("name"))
    try:
        pack = pack_dir(name)
        w = load_pack(pack)
        errors = validate(w, pack_dir=pack)
    except Exception as e:  # noqa: BLE001
        return {"errors": [f"validate failed: {e}"], "ok": False}
    return {"errors": errors, "ok": len(errors) == 0, "pack": str(pack)}


@app.post("/api/builder/verify")
def builder_verify(payload: dict):
    """Verify the live deployment's served world against the live URL."""
    from .maplab import verify_live

    url = payload.get("url", "http://127.0.0.1:8820")
    ok, errors = verify_live(url)
    return {"ok": bool(ok), "errors": errors, "url": url}


# --------------------------------------------------------------- weave file

# The served builder's "Make shareable file" pair. `ratatoskr weave`
# is terminal-only; a phone user with no terminal needs the same
# packaging from the page. The build is the CLI's own build_web core,
# so the bytes match `ratatoskr weave` exactly. Output is server-owned
# (VEFR_WEAVE_DIR or app_home()/dist) - a request never names a path -
# and one weave runs at a time.

_WEAVE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\.html$")
_WEAVE_LOCK = threading.Lock()


def _safe_world_name(name: str | None) -> str | None:
    """Validate a request's pack/world name; a bad one is a 400.

    The rule itself (and its regex) lives in paths.safe_pack_name() -
    this is only the HTTP edge that turns its ValueError into the
    builder's standard 400.
    """
    try:
        return safe_pack_name(name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _weave_output_dir() -> Path:
    """Where the served builder drops woven files. Server-owned only.

    VEFR_WEAVE_DIR is operator config (deploys/tests); otherwise the
    repo/container's dist/, the same tree `ratatoskr weave` writes to.
    """
    env = os.environ.get("VEFR_WEAVE_DIR")
    return Path(env) if env else app_home() / "dist"


class BuilderWeaveRequest(BaseModel):
    world: str | None = None  # pack to weave (None = current), like the other builder routes


@app.post("/api/builder/weave")
def builder_weave(req: BuilderWeaveRequest | None = None):
    """Weave the current world into one shareable HTML file.

    Resolves the pack exactly as the other /api/builder routes do
    (pack_dir over the named pack or the current world), builds it
    with the CLI's own packaging core into a server-owned directory,
    and returns {name, size_bytes, built_at, download_url}. A second
    weave while one is running gets 409 instead of racing the output.
    """
    from .cli import build_web
    from .paths import pack_dir

    # A bare pack name only: this route bundles whatever it resolves
    # into a downloadable file, so "../elsewhere" must never reach pack_dir.
    world = _safe_world_name(req.world if req else None)
    pack = pack_dir(world)
    if not (pack / "world.json").exists():
        raise HTTPException(status_code=404, detail=f"pack not found: {pack.name}")
    if not _WEAVE_LOCK.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="a weave is already running")
    try:
        safe = re.sub(r"[^A-Za-z0-9._-]+", "-", pack.name).strip("-") or "world"
        out_path = build_web(
            pack,
            _weave_output_dir(),
            out_name=f"{safe}-{date.today().isoformat()}.html",
        )
    finally:
        _WEAVE_LOCK.release()
    stat = out_path.stat()
    return {
        "name": out_path.name,
        "size_bytes": stat.st_size,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "download_url": f"/api/builder/weave/file/{out_path.name}",
    }


def _woven_file(name: str) -> Path:
    """Resolve a request's woven-file name to a server-written file, or 404.

    Shared by the download and play routes so both hold the same strict
    lookup: `name` must match `_WEAVE_NAME_RE` and then be found among
    the files the server wrote in `_weave_output_dir()`. The request
    string is never joined onto a path - path traversal never reaches
    FileResponse.
    """
    if not _WEAVE_NAME_RE.match(name):
        raise HTTPException(status_code=404, detail="no such woven file")
    out_dir = _weave_output_dir()
    # Look the name up among the files the server wrote rather than
    # joining it onto a path: the request never builds a filesystem path.
    woven = {p.name: p for p in out_dir.glob("*.html") if p.is_file()} if out_dir.is_dir() else {}
    target = woven.get(name)
    if target is None:
        raise HTTPException(status_code=404, detail="no such woven file")
    return target


_WOVEN_TITLE_RE = re.compile(r"<title>(.*?)</title>", re.DOTALL)


def _woven_title(path: Path) -> str:
    """The game's own title, as its weave baked it into <title>.

    The launcher lists each game under the name the game carries
    itself - the identity is the game's, never the shell's. The title
    sits in the woven file's head, so only the first block is read; a
    file without one (or one that cannot be read) falls back to its
    file name, never to a made-up label.
    """
    try:
        with path.open("rb") as fh:
            head = fh.read(8192).decode("utf-8", errors="replace")
    except OSError:
        return path.stem
    m = _WOVEN_TITLE_RE.search(head)
    return html.unescape(m.group(1)).strip() if m else path.stem


@app.get("/api/builder/weave/file/{name}")
def builder_weave_file(name: str):
    """Download a woven file as an attachment.

    Same strict name lookup as the play route; anything bad is refused
    before the disk is touched (path traversal never reaches
    FileResponse).
    """
    target = _woven_file(name)
    return FileResponse(target, media_type="text/html", filename=target.name)


def _serve_woven_playback(target: Path) -> FileResponse:
    """A woven game, inline, behind the sandbox CSP.

    The one way a woven page is served around people: inline (never an
    attachment) so a frame renders it, plus a sandbox CSP with no
    allow-same-origin, so a woven page (which may come from an imported
    pack) can never reach the page around it. The studio pane and the
    launcher both serve through this builder, so the two doors to a
    game cannot drift apart.
    """
    return FileResponse(
        target,
        media_type="text/html",
        content_disposition_type="inline",
        filename=target.name,
        # NOTE: the SAME strict sandbox as the pane's iframe (no allow-same-origin), so opening this URL directly
        # in a tab cannot give a woven page (which may come from an imported pack) the surrounding origin.
        headers={"Content-Security-Policy": "sandbox allow-scripts"},
    )


@app.get("/api/builder/weave/play/{name}")
def builder_weave_play(name: str):
    """Serve a woven file inline so the studio can play it in a pane.

    Same strict lookup as the download route, but `Content-Disposition:
    inline` (never an attachment) so an iframe renders it, plus a
    sandbox CSP so the woven player can never reach the studio page.
    """
    return _serve_woven_playback(_woven_file(name))


# ── the game-neutral launcher (vefr#454) ───────────────────────────────
# A SMALL shared shell around the existing woven Player (Rylee's
# 2026-10-16 decision): the launcher lists games and opens each one
# whole; it owns no title screen, no controls, no game logic, and it
# is separate from the studio's authoring interface.


@app.get("/api/launcher/games")
def launcher_games():
    """The woven games this server holds, for the game-neutral launcher.

    The launcher's whole listing, first step: every file the server has
    woven, newest first, each under the title the game itself baked
    into its <title> - the identity is the game's, never the shell's.
    The list walks the same glob `_woven_file()` looks a name up in,
    so the list and the door can never disagree about what exists.
    A pack that was never woven is not listed: the launcher opens
    games, it does not make them (weave-on-demand is a later step).
    """
    out_dir = _weave_output_dir()
    found: list[tuple[float, str, str]] = []
    if out_dir.is_dir():
        for p in out_dir.glob("*.html"):
            # The same name rule the door applies (_woven_file), so nothing is listed that would 404.
            if not p.is_file() or not _WEAVE_NAME_RE.fullmatch(p.name):
                continue
            found.append((p.stat().st_mtime, p.name, _woven_title(p)))
    # Newest weave first, then by name; the launcher shows a pack's
    # latest build at the top of the shelf.
    found.sort(key=lambda entry: (-entry[0], entry[1]))
    return {
        "games": [
            {"name": name, "title": title, "play_url": f"/api/launcher/play/{name}"}
            for _, name, title in found
        ]
    }


@app.get("/api/launcher/play/{name}")
def launcher_play(name: str):
    """Open a woven game in the existing Player.

    The same strict name lookup as every woven-file route - matched
    against `_WEAVE_NAME_RE`, then found among the files the server
    wrote; the request string is never joined onto a path - and the
    same sandboxed serving as the studio pane. The game arrives whole:
    its own title screen, skin and rules, untouched by the shell.
    """
    return _serve_woven_playback(_woven_file(name))


@app.get("/api/starred")
def starred_list():
    """Which entries are starred - mirror of the journal/starred pair.

    Surfaced separately so the UI can mark already-starred entries
    on page load without parsing the starred file itself.
    """
    return {"starred": starred.list_starred()}


@app.get("/api/trace")
def trace_list(limit: int = 100):
    """The engine's own trace - what actually ran, newest last.

    Dev-UI instrumentation only: never in the journal, never in the
    export, never in the packaged game.
    """
    return {"events": trace.recent(limit)}


@app.get("/api/weave")
def weave_list(limit: int = 200):
    """The engine's weave log - what the loader did, newest first.

    The weave log is fire-and-forget; the ring is in-memory, the
    file is on disk. The builder's Weave tab polls this route.
    """
    return inspect_mod.recent_weave(limit)


@app.get("/api/builder/resolved")
def builder_resolved():
    """The merged world the engine sees, after convention resolution.

    A mirror of load_world()'s return value with engine-only
    bookkeeping stripped. The builder renders this in the
    "what does the engine see?" view so the author can compare
    it against their on-disk files.
    """
    return inspect_mod.resolved_world()


@app.get("/api/builder/aspects")
def builder_aspects(phase: str | None = None):
    """Active world aspects for the Dev Overlay & Aspect Inspector.

    Returns loaded pack aspects, active act metadata, active regions,
    speaker seed matrices, current rune cast, and recent trace events.
    """
    return inspect_mod.pack_aspects(phase=phase)


class CommissionRequest(BaseModel):
    module: str
    world: str | None = None  # pack to read (None = current), like the other builder routes


@app.get("/api/builder/commissions", response_model=CommissionsReply)
def builder_commissions():
    """The commission board: the small jobs the residents are waiting on.

    Reads the active pack through the same loader the rest of the studio
    uses. A pack that can't be read is an empty board, not an error - the
    Hall should still open and say nothing is waiting. Rules-only: no model
    call is made anywhere behind this route.
    """
    from . import commissions
    from .maplab import load_pack
    from .paths import pack_dir, world_name

    name = world_name()
    try:
        w = load_pack(pack_dir(name))
    except Exception:  # noqa: BLE001 - an unreadable pack is an empty board, never a 500
        return {"world": name, "commissions": []}
    return {"world": name, "commissions": commissions.board(w)}


@app.post("/api/builder/commissions/defer", response_model=DeferReply)
def builder_commission_defer(req: CommissionRequest):
    """Set a commission aside for later.

    Deferral is the maker's own state, kept outside the pack, so the board
    still shows a finished job as done no matter how it was once set aside.
    An unknown module is the caller's mistake (400), not a silent no-op.
    """
    from . import commissions

    # The body's world is validated only so a traversal-shaped name is
    # refused at the edge; deferral itself is studio-wide, not per-pack.
    _safe_world_name(req.world)
    try:
        commissions.defer(req.module)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=f"no commission named {req.module!r}") from exc
    return {"ok": True, "module": req.module, "deferred": True}


@app.post("/api/builder/commissions/resume", response_model=DeferReply)
def builder_commission_resume(req: CommissionRequest):
    """Take a commission back off the shelf, so the Hall offers it again."""
    from . import commissions

    _safe_world_name(req.world)
    try:
        commissions.resume(req.module)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=f"no commission named {req.module!r}") from exc
    return {"ok": True, "module": req.module, "deferred": False}


@app.post("/api/builder/enhance/map")
def builder_enhance_map(req: enhance.MapEnhanceRequest):
    """Contextual AI Enhance for POI and map descriptions.

    Enriches sensory descriptions and interactive details for a
    point of interest or room using loaded pack canon and active tone.
    """
    with trace.span("/api/builder/enhance/map", region=req.region, poi=req.poi_name):
        return enhance.enhance_map(req)


@app.post("/api/builder/map/propose")
def builder_map_propose(payload: dict):
    """The storyteller's pen - the model proposes a validated town redraw.

    Same machinery as the `norns chat` interview (chat.propose_map):
    run-length rows at the current map's exact dimensions, legend
    characters only, gated by maplab.validate's geometry and
    reachability checks before anything is returned. This route never
    writes to the pack - the web room treats the result as a sketch
    the author can paint over and keep as a keepsake.
    """
    from . import chat
    from .maplab import load_pack
    from .paths import pack_dir

    name = _safe_world_name(payload.get("name"))
    story = (payload.get("story") or "").strip()
    mood = (payload.get("mood") or "").strip() or "quiet"
    try:
        pack = pack_dir(name)
        w = load_pack(pack)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "reason": f"couldn\u2019t open the pack: {e}"}
    town = w.get("town") or {}
    if not town.get("map") or not town.get("legend"):
        return {"ok": False, "reason": "this world has no map to sketch yet"}
    try:
        rows = chat.propose_map(story or w.get("title", ""), mood, w, pack)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "reason": f"the surveyor couldn\u2019t reach a pen: {e}"}
    if not rows:
        return {
            "ok": False,
            "reason": "the surveyor drew nothing usable \u2014 describe it differently, or paint it yourself",
        }
    return {
        "ok": True,
        "grid": rows,
        "legend": town.get("legend", {}),
        "dimensions": [len(rows), len(rows[0])],
    }


@app.post("/api/builder/map/check")
def builder_map_check(payload: dict):
    """The engine checks a storyteller's sketch before it's kept.

    Purely deterministic: the draft grid is swapped into a copy of
    the unified pack and run through the same maplab.validate gate
    as `norns validate` - shape, legend coverage, hero placement,
    reachability of every door, poi and speaker. Never writes.
    """
    from .maplab import load_pack, validate
    from .paths import pack_dir

    name = _safe_world_name(payload.get("name"))
    grid = payload.get("grid") or []
    if not isinstance(grid, list) or not grid or not all(isinstance(r, str) for r in grid):
        return {"ok": False, "errors": ["the sketch needs a rectangular grid of text rows"]}
    try:
        pack = pack_dir(name)
        w = load_pack(pack)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "errors": [f"couldn\u2019t open the pack: {e}"]}
    town = w.get("town") or {}
    if not town.get("map") or not town.get("legend"):
        return {"ok": False, "errors": ["this world has no map to check yet"]}
    # The sketch replaces only the ground; everything else is the
    # pack's own proven content.
    w["town"]["map"] = grid
    errors = validate(w)
    return {"ok": not errors, "errors": errors}


def _map_rows_from_payload(payload: dict) -> list[str]:
    """The draft rows a build request carries, or a 422 explaining why not.

    `grid` is what /api/builder/map/check already accepts (a list of
    text rows); `segments` is the CLI's run-length shape
    ({"rows": [[["H", 4], ...], ...]}) so a caller can replay a
    `norns build-map` input verbatim. Both funnel through maplab's
    own builders, so the rows are the same rows the CLI would use.
    """
    grid = payload.get("grid")
    if grid is not None:
        if not isinstance(grid, list) or not grid or not all(isinstance(r, str) for r in grid):
            raise HTTPException(
                status_code=422,
                detail="the map needs a rectangular grid of text rows",
            )
        return grid
    segments = payload.get("segments")
    if segments is not None:
        from .maplab import build_map

        raw = segments.get("rows") if isinstance(segments, dict) else segments
        try:
            return build_map(raw)
        except (KeyError, TypeError, ValueError, SystemExit) as exc:
            raise HTTPException(
                status_code=422,
                detail=f"those segments don’t build a map: {exc}",
            ) from exc
    raise HTTPException(
        status_code=422,
        detail="send a grid of text rows (or run-length segments) to build",
    )


def _map_file_target(pack: Path, w: dict) -> Path:
    """The single file maplab.write_pack writes the map into.

    Acts-shape packs (the served builder's own worlds) keep the map
    in acts/<act>/<region>/map.md, exactly as write_pack() does.
    Flat-shape packs keep it inside world.json. This mirrors
    write_pack() so the backup lands on the file that is about to
    be overwritten.
    """
    if "acts" in w or (pack / "acts").is_dir():
        act_id = w.get("_act_id") or "act-1"
        return pack / "acts" / act_id / "town" / "map.md"
    return pack / "world.json"


def _backup_map_file(target: Path) -> Path:
    """Copy `target` beside itself as <name>.bak-<timestamp>.

    Never overwrites an existing backup: a second build in the same
    second gets a -2, -3, ... suffix, so no map is ever lost to a
    fast double-commit.
    """
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup = target.with_name(f"{target.name}.bak-{stamp}")
    n = 1
    while backup.exists():
        backup = target.with_name(f"{target.name}.bak-{stamp}-{n}")
        n += 1
    backup.write_bytes(target.read_bytes())
    return backup


# ------------------------------------------------- place a character

# A kept face becomes a REAL speaker: one entry in the act's
# `speakers` plus a voice file under the region's voices/. The id and
# the region both become path parts, so each is held to one lowercase
# dash-word before any disk probe (CodeQL py/path-injection). The
# resolved path is then checked with cli._inside() as a hard backstop.
_SPEAKER_SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{0,31}$")
_PLACE_LIMITS = {"voice": 4000, "display_name": 64, "near": 64, "seed": 280}


def _speaker_slug(raw, what: str) -> str:
    """A path-safe id/region, or a 422 naming what was wrong.

    The rule is the request-facing guard for anything that becomes a
    filename (the character id, the region): one lowercase word of
    letters, digits and dashes. Anything else - '..', '/', '\\',
    uppercase, spaces, empty, over 32 chars - is refused here, so no
    disk probe ever sees it.
    """
    if not isinstance(raw, str) or not _SPEAKER_SLUG_RE.match(raw):
        raise HTTPException(
            status_code=422,
            detail=(
                f"the {what} must be 1-32 characters: lowercase letters, "
                "digits or dashes, starting with a letter"
            ),
        )
    return raw


def _speakers_file_target(pack: Path, w: dict) -> Path:
    """The file that holds the act's speakers.

    Acts-shape packs keep them in acts/<act>/world.json (the file
    maplab.write_pack overwrites); flat-shape packs keep them inside
    the pack-level world.json.
    """
    if "acts" in w or (pack / "acts").is_dir():
        act_id = w.get("_act_id") or "act-1"
        return pack / "acts" / act_id / "world.json"
    return pack / "world.json"


def _voice_target(pack: Path, w: dict, cid: str, region: str) -> tuple[Path | None, str]:
    """The voice file for a placed character, and its pack-relative name.

    Acts-shape packs put it in acts/<act>/<region>/voices/<id>.md;
    flat packs in voices/<id>.md. The returned path is None when the
    resolved target would leave the pack (the CodeQL guard), so the
    caller refuses before any is_dir/is_file/mkdir/open/write_text.
    """
    from .cli import _inside

    if "acts" in w or (pack / "acts").is_dir():
        act_id = w.get("_act_id") or "act-1"
        rel = f"acts/{act_id}/{region}/voices/{cid}.md"
    else:
        rel = f"voices/{cid}.md"
    resolved = _inside(os.path.realpath(pack), *rel.split("/"))
    return (Path(resolved) if resolved is not None else None), rel


def _validate_placement(pack: Path, w: dict, voice_rel: str, voice_text: str) -> list[str]:
    """Run maplab.validate with the not-yet-written voice file in place.

    The validator checks that a speaker's voice file exists on disk, so
    a dry run needs the file present. It goes into a throwaway copy of
    the pack: the real pack is never touched before a committed write,
    which is what makes `preview` read-only and keeps a refused
    placement off the disk entirely.
    """
    import shutil
    import tempfile

    from .maplab import validate

    from .cli import _inside

    with tempfile.TemporaryDirectory(prefix="vefr-place-") as td:
        tmp_pack = Path(td) / pack.name
        shutil.copytree(pack, tmp_pack)
        # The voice path is built from the validated id and region; the real-path check is the
        # backstop CodeQL (py/path-injection) wants right before any mkdir or write.
        resolved = _inside(os.path.realpath(tmp_pack), *voice_rel.split("/"))
        if resolved is None:
            return ["the character's voice file would leave the pack"]
        target = Path(resolved)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(voice_text, encoding="utf-8")
        return validate(w, pack_dir=tmp_pack)


@app.post("/api/builder/map/build")
def builder_map_build(payload: dict):
    """Commit a storyteller's sketch as this world's map - for real.

    The drawing table proposes and checks; this is the one builder
    route that writes. The draft runs through the same maplab.validate
    gate as /api/builder/map/check first - a draft that doesn't hold
    is refused with the validator's errors in words (422). An
    existing map is never clobbered by accident: without `force` the
    route answers 409, and only then does it write - through the
    CLI's own path (maplab.write_pack), so the bytes match
    `norns build-map` for the same input. The previous map file is
    copied beside it as <name>.bak-<timestamp> before the overwrite.
    Deterministic: no model call ever runs here.
    """
    from .maplab import load_pack, validate, write_pack
    from .paths import pack_dir

    name = _safe_world_name(payload.get("name"))
    rows = _map_rows_from_payload(payload)
    force = payload.get("force") is True

    pack = pack_dir(name)
    if not (pack / "world.json").is_file():
        raise HTTPException(status_code=404, detail=f"pack not found: {pack.name}")
    try:
        w = load_pack(pack)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"couldn’t open the pack: {e}") from e
    town = w.get("town") or {}
    if not town.get("legend"):
        raise HTTPException(status_code=422, detail="this world has no legend to draw a map with")

    # The previous map survives in `previous` for the backup step;
    # the draft replaces only the ground, everything else is the
    # pack's own proven content.
    previous = list(town.get("map") or [])
    w["town"]["map"] = rows
    errors = validate(w, pack_dir=pack)
    if errors:
        raise HTTPException(status_code=422, detail=" · ".join(errors))
    if previous and not force:
        raise HTTPException(
            status_code=409,
            detail="a map already exists — send force to replace it",
        )

    target = _map_file_target(pack, w)
    backup_rel = None
    if previous and target.is_file():
        backup = _backup_map_file(target)
        backup_rel = str(backup.relative_to(pack))
    write_pack(pack, w)
    # /api/world is cached; a committed map must show on the next read.
    load_world.cache_clear()
    # The map build is a kept edit from day one: log it and add its EDITS.md
    # line. The response shape is unchanged - the log lives behind the route.
    from . import edits

    edits.record(
        _edit_who(payload),
        "map_build",
        pack.name,
        [str(target.relative_to(pack))],
        backup_rel,
        "painted the map",
        pack,
    )
    return {
        "written": True,
        "path_rel": str(target.relative_to(pack)),
        "backup_rel": backup_rel,
    }


# Who a kept edit is logged as. The studio is the player's tool (the player
# keeps the edit), so that is the default; an explicit "crew" in the request
# records a helper/automation instead. Anything else falls back to the player.
def _edit_who(payload: dict) -> str:
    who = payload.get("who") if isinstance(payload, dict) else None
    return who if who in ("player", "crew") else "player"


@app.post("/api/builder/character/place")
def builder_character_place(payload: dict):
    """Place a kept face in the world - for real.

    A face the storyteller drafted is only a vault card until it is
    placed. This is the route that makes it a speaker: one entry in
    the act's `speakers` plus a voice file in the region's voices/.
    It mirrors POST /api/builder/map/build - the pack name goes through
    _safe_world_name(), the id and region are path-safe before any disk
    probe, the placement is engine-chosen (chat._pick_tile) or checked
    against maplab's own walkability/reachability, maplab.validate()
    gates the result in plain sentences, an existing id is never
    clobbered without `force` (409), the speakers file is backed up
    beside itself, and the write goes through maplab.write_pack so the
    bytes match what the CLI would write. `preview: true` is a dry run
    that writes nothing. Deterministic: no model call ever runs here.
    """
    from . import chat
    from .maplab import load_pack, reach, walkable
    from .maplab import write_pack
    from .paths import pack_dir

    name = _safe_world_name(payload.get("name"))
    cid = _speaker_slug(payload.get("id"), "character id")
    # The region is request data too and becomes a path part: guard it
    # before the pack is read. When the caller leaves it out it is
    # resolved from the pack below.
    region_raw = payload.get("region")
    region_requested = (
        _speaker_slug(region_raw, "region name") if region_raw is not None else None
    )
    preview = payload.get("preview") is True
    force = payload.get("force") is True

    pack = pack_dir(name)
    if not (pack / "world.json").is_file():
        raise HTTPException(status_code=404, detail=f"pack not found: {pack.name}")
    try:
        w = load_pack(pack)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"couldn’t open the pack: {e}") from e

    has_acts = "acts" in w or (pack / "acts").is_dir()
    if has_acts:
        regions = list((w.get("regions") or {}).keys())
        if not regions:
            regions = [w.get("_region") or "town"]
        region = region_requested or w.get("_region") or regions[0]
        if region not in regions:
            raise HTTPException(
                status_code=422,
                detail=f"this world has no region named {region!r}",
            )
    else:
        region = region_requested or "town"

    speakers = w.get("speakers")
    if not isinstance(speakers, dict):
        speakers = {}
    w["speakers"] = speakers
    if cid in speakers and not force:
        raise HTTPException(
            status_code=409,
            detail="a character with that id already exists — send force to replace it",
        )

    # The tile checks below run against the room the person is going INTO: its map, its legend, its
    # arrival tile and the people who already stand in it. (They used to read the home room for every
    # region, so a tile was judged against the wrong map; found placing a cat in a pack's home room.)
    wr = w
    if has_acts:
        home = w.get("_region") or regions[0]
        geo = (w.get("regions") or {}).get(region)
        if region != home:
            if not (isinstance(geo, dict) and geo.get("map") and geo.get("legend")):
                raise HTTPException(
                    status_code=422, detail=f"the {region} room has no map to place anyone on yet"
                )
            wr = dict(w)
            wr["town"] = dict(geo)
        wr = dict(wr)
        wr["speakers"] = {
            k: v for k, v in speakers.items()
            if isinstance(v, dict) and (v.get("region") or home) == region
        }
    town = wr.get("town")
    if not isinstance(town, dict) or not town.get("map") or not town.get("legend"):
        raise HTTPException(
            status_code=422, detail="this world has no map to place anyone on yet"
        )
    town.setdefault("hero_start", [1, 1])

    # Where they stand. With no `at`, the interview's own deterministic
    # rule chooses; with one, the tile must be walkable, reachable and
    # free - the same checks maplab owns, never re-implemented here.
    flooded = {tuple(t) for t in town.get("flood_tiles", [])}
    start = tuple(town["hero_start"])
    taken = {start} | {
        tuple(s["at"])
        for s in wr["speakers"].values()
        if isinstance(s, dict) and s.get("at")
    }
    at_raw = payload.get("at")
    if at_raw is None:
        tile = chat._pick_tile(wr)
        if tile is None:
            raise HTTPException(
                status_code=422, detail="there is nowhere left to stand in this world"
            )
    else:
        if (
            not isinstance(at_raw, (list, tuple))
            or len(at_raw) != 2
            or not all(isinstance(v, int) and not isinstance(v, bool) for v in at_raw)
        ):
            raise HTTPException(status_code=422, detail="at must be a tile [x, y]")
        tile = (int(at_raw[0]), int(at_raw[1]))
        if not walkable(wr, *tile):
            raise HTTPException(
                status_code=422, detail=f"the tile {list(tile)} is not walkable"
            )
        if tile in flooded:
            raise HTTPException(
                status_code=422, detail=f"the tile {list(tile)} is flood ground"
            )
        if tile not in reach(wr, start, flooded=flooded or None):
            raise HTTPException(
                status_code=422,
                detail=f"the tile {list(tile)} is not reachable from the hero's start",
            )
        if tile in taken:
            raise HTTPException(
                status_code=422, detail=f"someone already stands at {list(tile)}"
            )

    # One short line per phase the world defines. A phase with no seed
    # of its own falls back to the first seed given.
    phases = list(w.get("phases") or {})
    if not phases:
        raise HTTPException(
            status_code=422, detail="this world defines no phases to seed"
        )
    given = payload.get("seeds")
    if not isinstance(given, dict):
        given = {}
    ordered = [
        v.strip() for v in given.values() if isinstance(v, str) and v.strip()
    ]
    if not ordered:
        raise HTTPException(
            status_code=422, detail="give at least one seed line for the character"
        )
    first_seed = ordered[0]
    seeds = {}
    for phase in phases:
        line = given.get(phase)
        # No character cap is applied: the woven speech box
        # (web/packaged.html - `.npc-line` and showSpeech) renders a
        # line with no truncation or line-clamp, and the seed is fed to
        # the model as shape, not shown verbatim. There is no cap to
        # match, so none is invented here.
        seeds[phase] = (
            line.strip() if isinstance(line, str) and line.strip() else first_seed
        )

    voice_text = payload.get("voice")
    if not isinstance(voice_text, str) or not voice_text.strip():
        raise HTTPException(status_code=422, detail="a voice file needs some words")
    # Plain size limits so one request cannot write a huge file into a pack (chosen by the orchestrator,
    # 2026-10-01; Rylee may change them): voice 4000, name 64, near 64, each seed line 280 characters.
    if len(voice_text) > _PLACE_LIMITS["voice"]:
        raise HTTPException(status_code=422, detail=f"the voice is too long (at most {_PLACE_LIMITS['voice']} characters)")
    for key in ("display_name", "near"):
        val = payload.get(key)
        if isinstance(val, str) and len(val.strip()) > _PLACE_LIMITS[key]:
            raise HTTPException(status_code=422, detail=f"the {key.replace('_', ' ')} is too long (at most {_PLACE_LIMITS[key]} characters)")
    for phase_key, line in (payload.get("seeds") or {}).items() if isinstance(payload.get("seeds"), dict) else []:
        if isinstance(line, str) and len(line.strip()) > _PLACE_LIMITS["seed"]:
            raise HTTPException(status_code=422, detail=f"a seed line is too long (at most {_PLACE_LIMITS['seed']} characters)")
    # Match the keeper.md shape: the body verbatim, one trailing newline.
    voice_text = voice_text.rstrip("\n") + "\n"

    display_name = payload.get("display_name")
    if not isinstance(display_name, str) or not display_name.strip():
        raise HTTPException(
            status_code=422, detail="give the character a display_name"
        )
    near = payload.get("near")
    near = near.strip() if isinstance(near, str) and near.strip() else "nearby"

    voice_path, voice_rel = _voice_target(pack, w, cid, region)
    if voice_path is None:
        raise HTTPException(
            status_code=422,
            detail="the character's voice file would leave the pack",
        )

    spec = {
        "name": display_name.strip(),
        "at": [tile[0], tile[1]],
        "near": near,
        "voice_file": f"voices/{cid}.md",
        "seeds": seeds,
    }
    if has_acts:
        spec["region"] = region
    speakers[cid] = spec

    # Validate before any committed write, with the voice file staged
    # in a throwaway copy so the real pack is untouched on refusal.
    errors = _validate_placement(pack, w, voice_rel, voice_text)
    if errors:
        raise HTTPException(status_code=422, detail=" · ".join(errors))

    preview_body = {
        "id": cid,
        "region": region,
        "speaker": spec,
        "voice_file": voice_rel,
        "voice_text": voice_text,
        "at": [tile[0], tile[1]],
    }
    speakers_file = _speakers_file_target(pack, w)
    files = [str(speakers_file.relative_to(pack)), voice_rel]
    if preview:
        return {
            "ok": True,
            "written": False,
            "files": files,
            "backup": None,
            "preview": preview_body,
        }

    backup_rel = None
    if speakers_file.is_file():
        backup = _backup_map_file(speakers_file)
        backup_rel = str(backup.relative_to(pack))
    voice_path.parent.mkdir(parents=True, exist_ok=True)
    voice_path.write_text(voice_text, encoding="utf-8")
    write_pack(pack, w)
    # /api/world is cached; a committed placement must show on the next read.
    load_world.cache_clear()
    # A kept placement is a named edit: it goes in the log and the pack's
    # EDITS.md. The response shape stays exactly what T1 pinned.
    from . import edits

    edits.record(
        _edit_who(payload),
        "place_character",
        pack.name,
        files,
        backup_rel,
        f"put {spec['name']} at {near}",
        pack,
    )
    return {
        "ok": True,
        "written": True,
        "files": files,
        "backup": backup_rel,
        "preview": preview_body,
    }


@app.post("/api/builder/edits/undo")
def builder_edits_undo(payload: dict):
    """Put the last kept edit back - ONE level, in plain words.

    Restores the file from the backup the edit recorded, removes any file the
    edit created, drops its log line from data/edits.jsonl and its line from
    the pack's EDITS.md. Nothing to undo is a 404 in a plain sentence; a log
    line whose backup is missing, or points outside the pack, is a 409 - never
    a silent no-op. Every path that came from the log goes through cli._inside
    before any disk probe, exactly like a request-supplied path.
    """
    from . import edits
    from .cli import _inside
    from .paths import pack_dir

    name = _safe_world_name(payload.get("name"))
    pack = pack_dir(name)
    if not (pack / "world.json").is_file():
        raise HTTPException(status_code=404, detail=f"pack not found: {pack.name}")
    world = pack.name

    entry = edits.last_for(world)
    if entry is None:
        raise HTTPException(
            status_code=404, detail="there is nothing to undo in this world"
        )

    backup_rel = entry.get("backup")
    if not isinstance(backup_rel, str) or not backup_rel or os.path.isabs(backup_rel):
        raise HTTPException(
            status_code=409, detail="that edit has no backup to put back"
        )
    restore_rel = edits.backup_source(backup_rel)
    if restore_rel is None:
        raise HTTPException(
            status_code=409, detail="that backup was not made by this studio"
        )

    base = os.path.realpath(pack)

    def _in_pack(rel: str) -> str | None:
        # A log path is pack-relative; an absolute one is refused before the
        # guard (whose join would otherwise treat "/x" as base/x).
        if os.path.isabs(rel):
            return None
        return _inside(base, *rel.replace("\\", "/").split("/"))

    backup = _in_pack(backup_rel)
    restore = _in_pack(restore_rel)
    if backup is None or restore is None:
        raise HTTPException(
            status_code=409,
            detail="that edit's backup is outside the game folder, so I won't touch it",
        )
    if not os.path.isfile(backup):
        raise HTTPException(
            status_code=409,
            detail=(
                f"the backup for that edit is missing ({backup_rel}), "
                "so there is nothing to put back"
            ),
        )

    # Restore first, then clear away what the edit added: every touched file
    # except the one that had a backup was new, so it goes. (One level only -
    # a forced replace whose new file had no backup cannot be fully undone and
    # is documented as such.)
    Path(restore).write_bytes(Path(backup).read_bytes())
    touched = entry.get("files")
    for rel in touched if isinstance(touched, list) else []:
        if not isinstance(rel, str) or rel == restore_rel:
            continue
        created = _in_pack(rel)
        if created is not None and os.path.isfile(created):
            os.remove(created)
    if os.path.isfile(backup):
        os.remove(backup)

    edits.drop_last(world)
    edits.drop_summary(pack, entry)
    load_world.cache_clear()
    note = entry.get("note") or entry.get("edit") or "edited the game"
    return {"ok": True, "undone": note, "message": f"Undid the last edit: {note}."}


@app.post("/api/builder/face/roll")
def builder_face_roll(payload: dict):
    """Invite a new face: model-drafted, engine-placed, never written.

    The model only suggests prose (name, role, seed line); where
    they stand comes from the interview's own deterministic rule
    (reachable from the hero's start, not on anyone's spot, not on
    flood ground). The web room keeps the card as a vault item
    (kind "face") only when the storyteller says so.
    """
    from . import chat
    from .maplab import load_pack
    from .paths import pack_dir

    name = _safe_world_name(payload.get("name"))
    mood = (payload.get("mood") or "").strip() or "quiet"
    try:
        pack = pack_dir(name)
        w = load_pack(pack)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "reason": f"couldn\u2019t open the pack: {e}"}
    town = w.get("town") or {}
    if not town.get("map") or not town.get("legend"):
        return {"ok": False, "reason": "this world has no map to place anyone on yet"}
    tile = chat._pick_tile(w)
    if tile is None:
        return {"ok": False, "reason": "there is nowhere left to stand in this world"}
    try:
        face = chat.propose_face(w.get("title", ""), mood, w)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "reason": f"the keeper couldn\u2019t reach a pen: {e}"}
    if not face:
        return {
            "ok": False,
            "reason": "the keeper drew nothing usable \u2014 try again, or write the face yourself",
        }
    return {"ok": True, "face": {**face, "at": list(tile)}}


@app.post("/api/builder/enhance/voice")
def builder_enhance_voice(req: enhance.VoiceEnhanceRequest):
    """Contextual AI Enhance for NPC voices and speech rules.

    Drafts cadence rules, seed dialogue, and strike prompts for
    world characters in the requested tone.
    """
    with trace.span("/api/builder/enhance/voice", speaker=req.speaker_name):
        return enhance.enhance_voice(req)


@app.post("/api/builder/enhance/item")
def builder_enhance_item(req: enhance.ItemEnhanceRequest):
    """Contextual AI Enhance for item flavor, enchants, and curses.

    Crafts quiet enchantments and subtle, non-gory curses anchored
    in the world's forge texture.
    """
    with trace.span("/api/builder/enhance/item", kind=req.kind, bond=req.bond):
        return enhance.enhance_item(req)


@app.post("/api/handoff")
def handoff_create():
    """Write a markdown bundle to data/handoffs/. Returns the path
    so the builder can show a "saved to X" link.

    The bundle has sections the author fills in (what I tried,
    what I saw, what I've already done) plus auto-filled context
    (resolved world, recent weave events). It is the AI-buddy
    handoff format; see docs/guides/handoff.md.
    """
    inspect_mod._ensure_data_dir()

    out_dir = data_dir() / "handoffs"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = inspect_mod.build_handoff(out_dir)
    return {"path": str(path), "filename": path.name}


@app.get("/api/wiki")
def wiki(session: str = ""):
    """The world's wiki, auto-generated from canon + play - read-only.

    Characters are the pack's voices joined to what they actually
    said this session (npc_line entries, newest last). Relics are
    the session's kept items, canon order. The counts give the
    session's shape at a glance. No model calls - the wiki is a
    lens on data that already exists.
    """
    w = load_world()
    speakers = current_act(w)["speakers"]
    entries = journal.list_entries(sid=session)
    by_speaker: dict[str, list[dict]] = {}
    for e in entries:
        if e.get("kind") == "npc_line":
            by_speaker.setdefault(e.get("speaker") or "a voice", []).append(
                {"at": e.get("at", ""), "phase": e.get("phase", ""), "line": e.get("line", "")}
            )
    characters = []
    for key, spec in speakers.items():
        spoken = by_speaker.get(spec["name"], [])
        characters.append(
            {
                "key": key,
                "name": spec["name"],
                "lines": len(spoken),
                "recent": spoken[-3:],
            }
        )
    # A journal speaker the canon doesn't name still belongs here -
    # generated whispers sometimes speak through strangers.
    known = {spec["name"] for spec in speakers.values()}
    for speaker, spoken in by_speaker.items():
        if speaker not in known:
            characters.append(
                {
                    "key": "",
                    "name": speaker,
                    "lines": len(spoken),
                    "recent": spoken[-3:],
                }
            )
    return {
        "characters": characters,
        "relics": forge.list_vault(sid=session),
        "rumors": sum(1 for e in entries if e.get("kind") == "rumor"),
        "letters": sum(1 for e in entries if e.get("kind") in ("stefna_letter", "bell_letter")),
    }


@app.get("/api/export", response_class=PlainTextResponse)
def export(session: str = ""):
    """The whole playthrough as markdown - one section per dev UI
    tab, in the order the player met them. See export.py for the
    shape. Raw text, easy to download.
    """
    return PlainTextResponse(export_story(sid=session), media_type="text/markdown")


@app.get("/api/export/tabs", response_class=PlainTextResponse)
def export_tabs_list():
    """List of available per-tab exports, for the web UI to render
    as 'Export this tab' buttons."""
    return PlainTextResponse(
        "\n".join(["town", "rumors", "vault", "stefna", "voices", "journal"]),
        media_type="text/plain",
    )


@app.get("/api/export/tabs/{name}", response_class=PlainTextResponse)
def export_tab(name: str, session: str = ""):
    """One tab's worth of the world as markdown.

    The web UI's "Export this tab" button posts here; the result
    is a complete document (canon + that tab) ready to download.
    """
    from fastapi import HTTPException
    from .export import export_tab as render_tab, _TAB_NAMES

    if name not in _TAB_NAMES:
        raise HTTPException(
            status_code=404,
            detail=f"unknown tab {name!r}; expected one of {list(_TAB_NAMES)}",
        )
    return PlainTextResponse(render_tab(name, sid=session), media_type="text/markdown")


@app.get("/")
def index():
    # Primary UI: the workshop shell (app.html). The historical Board
    # shell lives on as /static/index.html (and as the canonical
    # board markup the shipped-JS tests lock in).
    idx = WEB / "app.html"
    if idx.is_file():
        return FileResponse(idx, headers={"Cache-Control": "no-cache"})
    return PlainTextResponse("vefr engine running (web UI unbundled)", status_code=200)


@app.get("/launcher")
def launcher_page():
    # The game-neutral launcher (vefr#454): a door of its own, beside
    # the studio. The studio is the authoring house; this page is the
    # one a player walks through - it lists the woven games
    # (GET /api/launcher/games) and opens each in the existing Player
    # (GET /api/launcher/play/{name}). The page owns no game chrome;
    # each game keeps its own face inside the frame.
    page = WEB / "launcher.html"
    if page.is_file():
        return FileResponse(page, headers={"Cache-Control": "no-cache"})
    return PlainTextResponse("vefr launcher running (web UI unbundled)", status_code=200)
