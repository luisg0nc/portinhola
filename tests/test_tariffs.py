

def test_conditions_field_loads_and_gas_coverage() -> None:
    from portinhola.core.tariffs import load_tariffs

    tariffs = load_tariffs()
    gas = [t for t in tariffs if t.utility == "gas"]
    assert len(gas) >= 7  # G9, EDP, Goldenergy, Galp, Iberdrola, Endesa, SU, Plenitude
    conditioned = [t for t in tariffs if t.conditions]
    assert conditioned, "at least one tariff must carry an eligibility note"
    # every gas tariff prices at least escalões 1 and 2
    for tariff in gas:
        assert {"1", "2"} <= set(tariff.gas.tiers)
