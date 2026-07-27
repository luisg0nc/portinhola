# Portinhola

Self-hosted dashboard for Portuguese household utilities — electricity, gas
and water. Bill ingestion, E-Redes 15-minute consumption data, meter-reading
reminders and auto-reporting, and a tariff switch calculator that replays
your real consumption curve against every known tariff.

Runs on a Raspberry Pi 5 or any small home server. AGPL-3.0.

**Status: early development.** Design spec:
`docs/superpowers/specs/2026-07-27-portinhola-design.md`.

## Run with Docker

```bash
docker compose -f docker-compose.example.yml up --build
```

Then open http://localhost:8000 — the first visit asks you to set a
password. All data lives in `./data`; back it up by copying that folder.

For remote/mobile access put Portinhola behind your reverse proxy with
HTTPS (required for PWA install) and set `PORTINHOLA_COOKIE_SECURE=true`.

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .[dev]
pytest
```
