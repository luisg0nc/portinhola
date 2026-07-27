from portinhola.core.billdata import BillData
from portinhola.extractors.base import Extractor, get_extractor, register


def test_registry_lookup_by_nif() -> None:
    @register
    class Dummy(Extractor):
        name = "dummy"
        version = "1"
        supplier_nifs = frozenset({"999999990"})

        def parse(self, pages: list[str]) -> BillData:
            return BillData(
                supplier_name="Dummy",
                period_start=None,
                period_end=None,
                supplies=[],
                lines=[],
            )

    found = get_extractor("999999990")
    assert found is not None
    assert found.name == "dummy"
    assert get_extractor("000000000") is None
