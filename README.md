# Portinhola

Self-hosted dashboard for Portuguese household utilities — electricity, gas
and water. Bill ingestion, E-Redes 15-minute consumption data, meter-reading
reminders and auto-reporting, and a tariff switch calculator that replays
your real consumption curve against every known tariff.

Runs on a Raspberry Pi 5 or any small home server. AGPL-3.0.

**Status: early development.** Design spec:
`docs/superpowers/specs/2026-07-27-portinhola-design.md`.

## Bills

Upload a bill PDF and Portinhola decodes its fiscal QR (issuer NIF, ATCUD,
VAT, total) and — when a supplier extractor exists — every line item,
consumption figure and contract detail. The first upload guides you through
creating the supply points and contracts it finds. Manual entry covers
suppliers without an extractor. See `docs/CONTRIBUTING-extractors.md` to
add yours.

| Supplier | Utilities | Extractor |
|---|---|---|
| G9 | electricity + gas (dual-fuel bills) | `g9` |
| Águas de Valongo (Be Water) | water | `bewater` |

## Consumption (E-Redes)

15-minute electricity consumption, two ways in:

- **File import** — download a consumption export (XLSX) from the E-Redes
  Balcão Digital and upload it on the Consumption page. Both the monthly
  and the date-range export layouts are supported; values are converted
  from average kW to kWh and stored DST-safely in UTC.
- **Connected account** — Settings → E-Redes → Connect opens the real
  E-Redes login streamed inside Portinhola; you type your credentials and
  solve the CAPTCHA yourself. Only the session cookies are stored
  (encrypted); a daily job then syncs new data automatically and alerts
  you (in-app + Apprise) when the session expires.

Charts: day (15-min curve), month, year, and period comparison.

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
