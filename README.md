# Portinhola

Self-hosted dashboard for Portuguese household utilities — electricity, gas
and water. Bill ingestion, E-Redes 15-minute consumption data, meter-reading
reminders and auto-reporting, and a tariff switch calculator that replays
your real consumption curve against every known tariff.

Runs on a Raspberry Pi 5 or any small home server. AGPL-3.0.

**Status: early development.** Design spec:
`docs/superpowers/specs/2026-07-27-portinhola-design.md`.

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .[dev]
pytest
```
