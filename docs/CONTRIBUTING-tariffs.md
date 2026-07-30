# Contributing tariff data

The switch calculator replays real consumption against every tariff in
`tariffs/`. Keeping those YAML files fresh is the community's job — a
stale price silently skews rankings, so every file must carry its source.

## Schema

One file per plan, in `tariffs/electricity/` or `tariffs/gas/`:

```yaml
supplier: Endesa
supplier_nif: "503504308"       # links the plan to contracts
name: Endesa Tarifa Digital
utility: electricity            # or gas
valid_from: 2026-07-01
valid_to: null                  # set when superseded
source_url: https://…           # price sheet you transcribed
retrieved: 2026-07-28           # when you read it
electricity:
  power_eur_day:                # FINAL prices (supplier + network access)
    "3.45": 0.1850
    "4.6": 0.2467
  energy_eur_kwh:
    simples: { total: 0.1452 }
    bi: { vazio: 0.0980, fora_vazio: 0.1750 }
    tri: { vazio: …, cheias: …, ponta: … }
```

Gas uses `gas.tiers` keyed by escalão with `fixed_eur_day`,
`energy_eur_kwh`, and optional `fixed_reduced_share` (fraction of the
fixed term billed at reduced VAT — check a real bill).

Rules:

- **Final prices only** — what bills actually charge per kWh/day, i.e.
  supplier energy + network access combined. Cross-check against a real
  bill when possible (a G9 bill confirmed 0.0940 + 0.0607 = the printed
  0.1547 €/kWh).
- `source_url` + `retrieved` are mandatory; mark estimated ladder values
  with a comment.
- Levies and VAT rules live in `tariffs/taxes.yaml` — do not bake them
  into plan prices.
- ERSE period tables live in `portinhola/core/cycles.py` +
  `tariffs/cycles/README.md`.
- `pytest tests/test_tariff_loader.py` validates your file.

The best contribution includes a calibration check: replay your own bill
period through your new YAML (Calculator → calibration banner) and state
the delta in the PR.

## Promotional phases

Time-limited discounts ("-15% nos primeiros 12 meses") go in an optional
`promo:` block — `energy_pct`, `fixed_pct` (off potência/termo fixo),
`months`, `conditions`. The calculator shows two totals: steady state
(promo excluded) and "1.º ano" (promo pro-rated over the window).
Permanent conditional discounts (e-invoice/direct-debit) belong in the
prices themselves with a `conditions:` note, not in `promo:`.

## Potência sanity floor

`load_tariffs()` rejects any electricity ladder priced below the
regulated network-access component (0.0498 €/day per kVA): every
supplier passes that through before adding margin, so a value under the
floor is fabricated data, not a cheap tariff. Transcribe ladders from
the supplier's official price sheet; if only one kVA point is published,
derive the others with the access delta and mark them estimated.
