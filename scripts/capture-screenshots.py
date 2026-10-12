"""Capture the screenshots gallery: the studio's rooms and the woven player.

Used by CI (screenshots.yml, uploaded as an artifact) and locally to
refresh the committed gallery in docs/screenshots/. It also writes
docs/screenshots/README.md, so the gallery page always lists exactly the
pictures that exist.

Needs a running engine on the sample world and a woven sample file:

    VEFR_WORLD=sample-world uv run uvicorn vefr.main:app --app-dir src --port 8820 &
    uv run ratatoskr weave --pack worlds/sample-world
    uv run python scripts/capture-screenshots.py

Requires: playwright (a test dependency) with chromium installed.
"""
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "screenshots"
ENGINE_URL = os.environ.get("VEFR_SHOTS_URL", "http://127.0.0.1:8820")

# (screen id, file slug, caption) in the order the gallery shows them
ROOMS = [
    ("launcher", "studio-home", "The Studio: the world on the table, worlds on the walls, news, the residents"),
    ("floor", "studio-floor", "The Floor: every department, one door each"),
    ("workshop", "studio-desk", "The Desk: the brief, the creed, the map pinned like a scrap"),
    ("map", "studio-map-room", "The Map Room: regions, their survey, and the drawing table"),
    ("characters", "studio-folks", "The Folks: who lives here, and inviting a new face"),
    ("items", "studio-vault", "The Vault: the forge and what you've kept"),
    ("library", "studio-library", "The Library: the world's books and the studio handbook"),
    ("journal", "studio-chronicle", "The Chronicle: what has happened, every kind in words"),
    ("runes", "studio-casting-table", "The Casting Table: 24 stones and a three-stone cast"),
    ("evidence", "studio-archives", "The Archives: a staircase down to the raw truth"),
    ("hall", "studio-hall", "The Hall: the creed, the town window, the household"),
    ("settings", "studio-boiler-room", "The Boiler Room: reading, sound and motion, and Spark's status"),
]
DAY = ["launcher", "workshop", "library"]
PHONE = ["launcher", "library", "floor"]
DESKTOP = {"width": 1440, "height": 900}
# JPEG keeps the committed gallery small (~4 MB, not ~12 MB of PNG) with no new dependency
SHOT = {"type": "jpeg", "quality": 82}
PHONE_VP = {"width": 390, "height": 844}


def _context(browser, viewport, light="night"):
    ctx = browser.new_context(viewport=viewport, reduced_motion="reduce")
    ctx.add_init_script(
        "try{localStorage.setItem('vefr-light','%s');"
        "localStorage.setItem('vefr.walk',JSON.stringify({skipped:true}))}catch(e){}" % light
    )
    return ctx


def _room(page, screen):
    page.goto(f"{ENGINE_URL}/#{screen}", wait_until="networkidle", timeout=20000)
    page.wait_for_timeout(1200)


def capture_studio(browser, shots):
    ctx = _context(browser, DESKTOP)
    page = ctx.new_page()
    for screen, slug, caption in ROOMS:
        _room(page, screen)
        page.screenshot(path=str(OUT / f"{slug}.jpg"), **SHOT)
        shots.append(("Rooms", f"{slug}.jpg", caption))
    # A book open in the Library, turned to its second page
    _room(page, "library")
    spines = page.locator(".lib-spine")
    if spines.count():
        spines.first.click()
        page.wait_for_timeout(300)
        nxt = page.get_by_role("button", name="Next page")
        if nxt.count():
            nxt.first.click()
            page.wait_for_timeout(300)
        page.screenshot(path=str(OUT / "studio-library-reading.jpg"), **SHOT)
        shots.append(("Moments", "studio-library-reading.jpg", "Reading a book in the Library, one page at a time"))
    # A resident's chat, opened from the Chronicle
    _room(page, "journal")
    ask = page.locator(".greeter__ask")
    if ask.count():
        ask.first.click()
        page.wait_for_timeout(500)
        page.screenshot(path=str(OUT / "studio-resident-chat.jpg"), **SHOT)
        shots.append(("Moments", "studio-resident-chat.jpg", "Asking a resident: Urðr's chat, with her suggested questions"))
    ctx.close()

    ctx = _context(browser, DESKTOP, "day")
    page = ctx.new_page()
    for screen, slug, caption in ROOMS:
        if screen in DAY:
            _room(page, screen)
            page.screenshot(path=str(OUT / f"{slug}-day.jpg"), **SHOT)
            shots.append(("Day in the hall", f"{slug}-day.jpg", caption.split(":")[0] + ", in daylight"))
    ctx.close()

    ctx = _context(browser, PHONE_VP)
    page = ctx.new_page()
    for screen, slug, caption in ROOMS:
        if screen in PHONE:
            _room(page, screen)
            page.screenshot(path=str(OUT / f"{slug}-phone.jpg"), **SHOT)
            shots.append(("On a phone", f"{slug}-phone.jpg", caption.split(":")[0] + ", at 390px"))
    ctx.close()


def capture_player(browser, shots):
    """The woven single-file player: the title, and in game (Begin goes straight in)."""
    woven = sorted((ROOT / "dist").glob("sample-world-*.html"))
    if not woven:
        print("  skip player: no woven HTML in dist/ (run ratatoskr weave first)")
        return
    uri = woven[-1].as_uri()

    def begin(page):
        page.goto(uri, wait_until="networkidle", timeout=20000)
        page.wait_for_timeout(800)

    for scheme in ("dark", "light"):
        suffix = "" if scheme == "dark" else "-light"
        page = browser.new_page(viewport={"width": 1280, "height": 900}, color_scheme=scheme)
        begin(page)
        page.screenshot(path=str(OUT / f"export-title-card{suffix}.jpg"), **SHOT)
        shots.append(("The shareable file", f"export-title-card{suffix}.jpg", f"The title screen ({scheme})"))
        page.close()

    # In game: the view fills the screen; a whisper lands in the speech box.
    for tag, vp, touch in (("", {"width": 1280, "height": 900}, False),
                           ("-phone", {"width": 390, "height": 844}, True)):
        page = browser.new_page(viewport=vp, color_scheme="dark", has_touch=touch, is_mobile=touch)
        begin(page)
        page.click("#ts-enter")
        page.wait_for_timeout(400)
        # A phone gets the touch controls instead of the button row (vefr#428), so there is no Whisper button to
        # press there: the phone picture shows the touch controls, and only the computer picture shows a whisper.
        if not touch:
            page.click("#whisper")
        page.wait_for_timeout(800)
        page.screenshot(path=str(OUT / f"export-in-game{tag}.jpg"), **SHOT)
        what = ("the touch controls, health and mood over the map" if touch
                else "speech box, health, mood and actions over the map")
        where = "on a phone" if touch else "on a computer"
        shots.append(("The shareable file", f"export-in-game{tag}.jpg", f"In game {where}: {what}"))
        page.close()


def write_gallery(shots):
    """docs/screenshots/README.md: every picture, grouped, two per row."""
    lines = [
        "# Screenshots",
        "",
        "The VEFR studio and its shareable player, on the bundled sample world",
        "(Emberfield). Generated by `scripts/capture-screenshots.py`; do not edit",
        "this page by hand: rerun the script and it rewrites the pictures and this",
        "page together.",
        "",
    ]
    groups: dict[str, list] = {}
    for group, name, caption in shots:
        groups.setdefault(group, []).append((name, caption))
    for group, items in groups.items():
        lines += [f"## {group}", "", "| | |", "|---|---|"]
        for i in range(0, len(items), 2):
            cells = []
            for name, caption in items[i:i + 2]:
                cells.append(f"![{caption}]({name})<br>{caption}")
            if len(cells) == 1:
                cells.append("")
            lines.append("| " + " | ".join(cells) + " |")
        lines.append("")
    (OUT / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for old in [*OUT.glob("*.png"), *OUT.glob("*.jpg")]:
        old.unlink()
    shots: list = []
    print("capturing screenshots...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        capture_studio(browser, shots)
        capture_player(browser, shots)
        browser.close()
    write_gallery(shots)
    print(f"done: {len(shots)} pictures + README.md in {OUT}")


if __name__ == "__main__":
    main()
