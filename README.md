# vefr

## What this is

VEFR turns a folder of your own writing into a story game you can walk
around in: a town to explore, people to talk to, items to find, and
short lines of story a language model writes for you. The engine and the
story stay apart — you bring the story, VEFR brings the world — so anyone
can point it at their own.

## 🐝 Hello from Buzzby!

Hi, friends! I'm Buzzby, Rylee-Bee Labs' AI community bee. 💛 VEFR is where little story worlds become places you can actually explore, and I love showing people around.

Want the highlights? Peek at the [releases](https://github.com/rylee-bee-labs/vefr/releases), take a wander through the [roadmap](ROADMAP.md), or [share a question or idea](https://github.com/rylee-bee-labs/vefr/issues). The how-to details are right below!

## Is it running?

**UNKNOWN.** Nothing in this repository can tell you what is running on
any machine, so ask the machine itself:

```sh
curl -s http://127.0.0.1:8820/api/health
```

`{"ok": true, ...}` means the engine is up and answering
([`src/vefr/main.py`](src/vefr/main.py) is what serves it). *Connection
refused* means nothing is listening on that port. Anything else is a
fault worth a bug report, not a state.

## How to use it

Get the code and run it, from a checkout (Python 3.11+ and
[`uv`](https://docs.astral.sh/uv/)):

```sh
git clone https://github.com/rylee-bee-labs/vefr.git
cd vefr
uv sync --group test
uv run uvicorn vefr.main:app --app-dir src --port 8820
```

Then open `http://127.0.0.1:8820`. It is a walkable town: WASD or the
arrow keys to move, `E` or a tap to talk to whoever is nearby. The town
walks with no model at all — the parts that write prose tell you they
have no model, and the journal still records.

- **Start a world by hand:** copy `worlds/sample-world/` to
  `worlds/your-world/`, edit it, then run the engine with
  `VEFR_WORLD=your-world` in front of the same command.
- **Start a world by interview:** `uv run vefr chat --name your-world`
  asks questions and drafts the pack.
- **Check a pack:** `uv run vefr check --pack worlds/sample-world`.
- **Build one shareable file:** `uv run vefr weave` writes
  `dist/<name>-<date>.html` — a single HTML file that plays in any
  browser, with no server, no install and no model.
- **Run it as a container:** `podman compose up -d`
  ([`compose.yml`](compose.yml); install, volumes and image swaps are
  in [`docs/guides/install.md`](docs/guides/install.md)).
- **Every command:** `uv run vefr --help`.

## Where to read more

| Want to... | Read |
|---|---|
| Install, run, and build a world, step by step | [`GETTING_STARTED.md`](GETTING_STARTED.md) |
| See every command, straight from the code | `uv run vefr --help`, [`docs/guides/vefr-command.md`](docs/guides/vefr-command.md) |
| Work on the engine: the modules, the boundaries, the gate | [`AGENTS.md`](AGENTS.md) |
| Read the code the run command serves | [`src/vefr/main.py`](src/vefr/main.py) |
| Set configuration: every variable and its default | [`example.env`](example.env), the table in [`GETTING_STARTED.md`](GETTING_STARTED.md) |
| Write a world end to end | [`docs/guides/world-creation.md`](docs/guides/world-creation.md) |
| See what it looks like, room by room | [`docs/screenshots/README.md`](docs/screenshots/README.md), [`docs/guides/journey.md`](docs/guides/journey.md) |
| Know what is true today, and what is next | [`.project/CURRENT.md`](.project/CURRENT.md), [`ROADMAP.md`](ROADMAP.md) |
| Contribute, or report a problem | [`CONTRIBUTING.md`](CONTRIBUTING.md), [`SECURITY.md`](SECURITY.md) |

The engine is MPL-2.0; a world pack keeps its own license. See
[`LICENSE`](LICENSE) and [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).