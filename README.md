# Portinhola

Self-hosted dashboard for Portuguese household utilities — electricity, gas
and water. Bill ingestion, E-Redes 15-minute consumption data, meter-reading
reminders and auto-reporting, and a tariff switch calculator that replays
your real consumption curve against every known tariff.

Runs on a Raspberry Pi 5 or any small home server. AGPL-3.0.

**Status: early development.**

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
| EDP Comercial | electricity + gas (multi-invoice PDFs) | `edp` |
| Iberdrola | electricity, gas (2023 + 2024 layouts) | `iberdrola` |

After adding a new extractor, the Bills page offers "re-run extractors"
to fill in line items for bills that were previously QR-only.

## Consumption (E-Redes)

15-minute electricity consumption, two ways in:

- **File import** — download a consumption export (XLSX) from the E-Redes
  Balcão Digital and upload it on the Consumption page. Both the monthly
  and the date-range export layouts are supported; values are converted
  from average kW to kWh and stored DST-safely in UTC.
- **Connected account (token import)** — copy one value from your own
  browser: log in, open DevTools (F12) → Application → Cookies →
  balcaodigital.e-redes.pt, and paste the `aat` cookie value into
  Settings → E-Redes (step-by-step guide included). Saving syncs
  immediately: Portinhola calls the portal's internal consumption API
  directly with that token — no browser, no reCAPTCHA — and stores the
  intervals. "Sync now" repeats it on demand. The token is stored
  encrypted. (Endpoint and request shape follow the community
  [`ha-eredes`](https://github.com/mrfyda/ha-eredes) integration.)

  **Why there's no unattended daily sync:** the `aat` token *is* the
  portal session and lasts only ~91 minutes. Minting a new one is gated
  by invisible reCAPTCHA, verified at the API layer — replaying a captured
  reCAPTCHA token returns 403, and the session cookie alone returns 401.
  So no server-side process can renew it. In practice: import a token
  whenever you want fresh data (it pulls everything up to today in one
  call), and use the XLSX file import for bulk history.

Charts: day (15-min curve), month, year, and period comparison.

## Switch calculator

The end-game feature: instead of estimating from a monthly total (as
ADENE's Poupa Energia must), Portinhola replays your real 15-minute
consumption curve against every tariff's full price vector — energy per
ERSE period, potência per day, IEC/CAV/DGEG levies and per-component VAT
— producing the actual counterfactual bill for each plan and cycle
option. A calibration banner shows how closely the engine reproduces
your latest real bill (the reference implementation lands within cents).
Extras: gas tariff ranking from billed kWh, potência right-sizing from
your real 15-minute peak, and a live period-to-date cost estimate on the
dashboard.

Tariff prices are community-maintained YAML with mandatory source URLs
and retrieval dates (`docs/CONTRIBUTING-tariffs.md`) — always confirm
current prices with the supplier before switching.

## Meter readings

Fast reading entry for electricity, gas and water — big keypad, previous
value shown, monotonic validation (with a meter-swap override). Each
contract can have a reporting window (e.g. G9's days 7–9); a daily job
reminds you (in-app + push) when the window opens and no reading exists.
Submission guidance is per contract: portal link, or phone + reference
for IVR lines (Be Water prints both on its bills). Portal automation
modules plug into `portinhola/reporters/` —
see `docs/CONTRIBUTING-reporters.md`.

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
