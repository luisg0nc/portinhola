<p align="center">
  <img src="frontend/static/icon.svg" width="88" alt="Portinhola — the little arched door" />
</p>

<h1 align="center">Portinhola</h1>

<p align="center">
  Self-hosted dashboard for Portuguese household utilities —
  electricity, gas and water.
</p>

<p align="center">
  <a href="https://github.com/luisg0nc/portinhola/actions/workflows/ci.yml"><img src="https://github.com/luisg0nc/portinhola/actions/workflows/ci.yml/badge.svg" alt="CI" /></a>
  <a href="https://github.com/luisg0nc/portinhola/actions/workflows/tariff-watch.yml"><img src="https://github.com/luisg0nc/portinhola/actions/workflows/tariff-watch.yml/badge.svg" alt="tariff-watch" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0-b3372c" alt="License: AGPL-3.0" /></a>
  <a href="https://github.com/luisg0nc/portinhola/releases"><img src="https://img.shields.io/badge/release-v0.1.0-c2542e" alt="Release" /></a>
</p>

---

Portinhola ("little door") ingests your utility bills, pulls your real
15-minute electricity consumption from E-Redes, reminds you to submit
meter readings, and — the end-game feature — tells you exactly what every
tariff on the market would have cost **you**, by replaying your actual
consumption curve instead of estimating from monthly totals.

It runs on a Raspberry Pi 5 or any small home server, stores everything
in a single SQLite volume, and never talks to a cloud service on your
behalf. Interface in Portuguese and English. No LLMs, no telemetry, no
accounts — your data stays behind your own little door.

## Features

- **Bill ingestion** — upload a PDF; the fiscal QR (Portaria 195/2020) is
  decoded for issuer NIF, ATCUD, VAT and totals, and per-supplier
  extractors parse every line item, consumption figure and contract
  detail. First upload walks you through creating supply points.
- **15-minute consumption** — connect your E-Redes account with a
  browser-session token or import the Balcão Digital XLSX exports;
  day/month/year charts and period comparison, DST-safe in UTC.
- **Switch calculator** — replays your real curve against every tariff's
  full price vector (energy per ERSE period, potência per day, IEC / CAV /
  DGEG / TOS levies, per-component VAT). Ranks electricity, gas, and
  **dual luz+gás bundles** including sourced dual discounts, the best
  mixed pair, and your current combo. A "1.º ano" view prices in
  promotional phases; a calibration banner shows how closely the engine
  reproduces your latest real bill (reference: within cents).
- **Potência right-sizing** — your real 15-minute peak vs contracted kVA.
- **Meter readings** — fast keypad entry with monotonic validation,
  per-contract reporting windows, reminders (in-app + push via
  [Apprise](https://github.com/caronc/apprise)), and per-contract
  submission guidance (portal link or IVR phone + reference).
- **Dashboard** — live period-to-date cost estimate, monthly cost history
  with averages, yearly totals, contracted power and gas tier at a glance.
- **Community-maintained tariff data** — prices live in YAML with
  mandatory source URLs and retrieval dates, guarded by schema and
  sanity validations (a potência below the regulated network-access
  floor is rejected as fabricated). A weekly
  [tariff-watch](.github/workflows/tariff-watch.yml) job re-parses the
  official price sheets and opens a PR when prices move.

## Supported suppliers (bill extractors)

| Supplier | Utilities | Extractor |
|---|---|---|
| G9 | electricity + gas (dual-fuel bills) | `g9` |
| Águas de Valongo (Be Water) | water | `bewater` |
| EDP Comercial | electricity + gas (multi-invoice PDFs) | `edp` |
| Iberdrola | electricity, gas (2023 + 2024 layouts) | `iberdrola` |

Bills from suppliers without an extractor still work — QR data and manual
entry cover them — and after adding a new extractor the Bills page can
re-run extraction over already-uploaded PDFs.

## Quick start

```bash
docker compose -f docker-compose.example.yml up --build
```

Open http://localhost:8000 — the first visit asks you to set a password.
All state lives in `./data` (SQLite database, encryption key, bill PDFs);
back it up by copying that folder.

For remote/mobile access put Portinhola behind your reverse proxy with
HTTPS (required for PWA install) and set `PORTINHOLA_COOKIE_SECURE=true`.

## Connecting E-Redes

Two ways to get your 15-minute data in:

- **Token import** — log in to the [Balcão Digital](https://balcaodigital.e-redes.pt)
  in your own browser, copy the `aat` cookie value (DevTools →
  Application → Cookies), paste it in Settings → E-Redes. Portinhola
  calls the portal's internal consumption API directly with that token —
  no embedded browser, no reCAPTCHA — walking your history back to the
  portal's horizon and persisting each window as it lands. The token is
  stored encrypted.
- **File import** — upload the portal's XLSX consumption exports on the
  Consumption page (both export layouts supported).

There is no unattended daily sync by design: the `aat` token *is* the
portal session (~91 minutes) and renewing it is gated by reCAPTCHA
verified at the API layer, so no server-side process can mint one.
Paste a fresh token whenever you want to top up; syncs resume where they
left off. (Endpoint shape follows the community
[`ha-eredes`](https://github.com/mrfyda/ha-eredes) integration.)

## Why not just use Poupa Energia?

ADENE's comparator has to estimate from a monthly total. Portinhola has
your actual 15-minute curve, so bi-horário vs simples is decided by your
real usage pattern, levies and VAT tranches are computed per component,
and promotional phases are priced separately from steady state — the
difference between "probably cheaper" and a number you can act on.
Always confirm current prices with the supplier before switching.

## Contributing

The per-supplier pieces are designed to be community-maintained:

- **Bill extractors** — `docs/CONTRIBUTING-extractors.md` (anonymized
  text fixtures required; privacy checklist included).
- **Tariff prices** — `docs/CONTRIBUTING-tariffs.md` (source URL +
  retrieval date mandatory; promo phases and eligibility conditions have
  dedicated fields).
- **Reading reporters** — `docs/CONTRIBUTING-reporters.md` (per-supplier
  submission automation).

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .[dev]
pytest                       # backend
cd frontend && npm ci && npm test && npm run build
```

FastAPI + SQLAlchemy + SQLite on the back, SvelteKit (static adapter)
served by the same process on the front, one container, one volume.

## License

[AGPL-3.0](LICENSE)
