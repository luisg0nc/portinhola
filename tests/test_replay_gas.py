"""Gas golden test against real 2026-07 G9 bill line arithmetic:
  349 kWh energy: 23.80 + 13.62 (redes) = 37.42 €  → combined 0.10722 €/kWh
  termo fixo 30 d: 2.23 (23%) + 1.49 (6%) = 3.72 €  → 0.1240 €/day
  IEC 349 kWh × 0.0152532 = 5.32 €
  TOS Valongo volumetric 349 kWh × 0.0091129 = 3.18 €
"""

from portinhola.core.replay import replay_gas
from portinhola.core.tariffs import load_tariffs, load_taxes

TARIFFS = {t.id: t for t in load_tariffs()}
TAXES = load_taxes()


def test_golden_g9_gas_components() -> None:
    sim = replay_gas(349.0, 30, TARIFFS["g9-gas"], TAXES, tier="2", municipality="valongo")
    by_label = {line.label: line for line in sim.lines}
    assert abs(by_label["energy"].amount_cents - 3742) <= 1
    assert abs(by_label["fixed_standard"].amount_cents - 223) <= 1
    assert abs(by_label["fixed_reduced"].amount_cents - 149) <= 1
    assert abs(by_label["iec"].amount_cents - 532) <= 1
    # TOS = 349 × 0.0091129 + 30 × 0.0106082 = 3.18 + 0.32
    assert abs(by_label["tos"].amount_cents - (318 + 32)) <= 1
    assert by_label["fixed_reduced"].vat_rate == 6
    assert by_label["energy"].vat_rate == 23


def test_unknown_tier_raises() -> None:
    import pytest

    with pytest.raises(ValueError, match="tier"):
        replay_gas(100.0, 30, TARIFFS["g9-gas"], TAXES, tier="9")
