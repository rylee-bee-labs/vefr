# Install: `podman compose up`

The engine is a self-contained service. Three commands and you
have a working vefr on your LAN, ready to play with the canary
sample world (Emberfield).

## Quick start

```sh
git clone https://github.com/rylee-bee-labs/vefr.git
cd vefr
podman compose up -d
open http://localhost:8820
```

That's it. The image builds on first `up`; the named volumes
are created automatically; the canary loads by default.

## What the compose does

| Service / volume | What it holds |
|---|---|
| `vefr` service | The engine. Builds from the local `Containerfile`; image is tagged `localhost/vefr:latest`. |
| `vefr-template` volume | Engine-owned templates (`lore/`, `sample-world/`, `poolworld/`). Read-only inside the container. |
| `vefr-worlds` volume | Author canon (anything you `ratatoskr ferry fetch` or copy in). Writable. |
| `vefr-data` volume | Player state (`vault.json`, `journal.json`, `weave.jsonl`, handoff bundles). Writable. |

`network_mode: host` so the engine sees the same LAN as your
other services. The engine's `/api/health` and the web UI
land on `localhost:8820` by default.

## Customizing

### Change the default world

```sh
# Edit compose.yml:
environment:
  VEFR_WORLD: my-canon-pack    # the default
```

Or override at start time:

```sh
VEFR_WORLD=my-canon-pack podman compose up -d
```

### Point at an LLM

Without an LLM backend, the engine boots and serves the UI,
but model-backed endpoints (`/api/rumor`, `/api/forge`,
`/api/npc`, `/api/stefna`) return errors. The engine talks
to any OpenAI-compatible HTTP endpoint. Uncomment one of
these in `compose.yml`:

```yaml
environment:
  # Ollama, llama.cpp's OpenAI shim, LM Studio, or anything
  # that speaks /v1/chat/completions.
  VEFR_LLAMACPP_URL: http://host.lan:8081
  # VEFR_MODEL is the studio/craft model; the storyteller comes from
  # the active Storyteller Pack unless no pack is installed.
  VEFR_MODEL: gpt-oss-20b
```

For ollama specifically, the simplest is to add an `ollama`
service to the same compose file (there is no starter file in the
repo yet).

### Point it at a phone-as-backend

Anywhere the engine can reach an OpenAI-compatible HTTP endpoint,
the engine is happy. That includes:

- `Local LLM Server` on the iPhone (App Store, iOS 26+) - runs Apple's
  Foundation Models on-device, exposes OpenAI + Ollama APIs
- `Crucible LLM Server` or `Pirate LLM Server` - open-source, llama.cpp
  + Metal, sideloadable via AltStore
- A Mac running Ollama / LM Studio, exposed to your LAN

Set `VEFR_LLAMACPP_URL=http://<phone-ip>:11434/v1` (compose: put it
in `environment:` like above) and the game runs entirely off the
laptop, the cloud, and any LAN host.

### Edit a pack in vim

```sh
# Export the canary to a host-side git repo
podman compose exec vefr ratatoskr volumes export \
  --pack sample-world --dest /tmp/edited   # or any host path
# (the export path is inside the container; /tmp/edited is too)
```

For the real workflow, see `docs/guides/volumes-export.md`.

## What "self-contained" gets you

The compose is a *one-file install story*. Anyone with
`podman` (or `docker compose`) can run the engine without
understanding the ro/rw volume split, the surface field, the
journey attachment, or any of the engine's other internals.
They get the UI, the canary, and the export/import tooling
for their own work.

## Production

For multi-host / multi-engine deployments, replace the
compose with your orchestrator of choice (Komodo, Swarm,
K8s) using the same volume layout. The engine itself is
unaware of the orchestration; it just reads the ro template
volume, the rw canon volume, and the rw data volume.

## Limitations / next

- The compose doesn't include an LLM service. The engine is
  built to talk to *any* OpenAI-compatible endpoint; bring
  your own or use a host-side `ollama`/`llama.cpp`. PR
  welcome for an `examples/` directory with starter
  compose files for popular backends.
- `network_mode: host` is convenient for LAN access but
  doesn't compose well in stricter environments. For
  something more portable, switch to a `ports:` mapping
  and document the URL the engine is reachable at.
- No TLS. The engine speaks HTTP. If you expose it on the
  WAN, put it behind a reverse proxy (Caddy, nginx,
  Traefik) with TLS.
