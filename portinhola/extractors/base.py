from abc import ABC, abstractmethod

from portinhola.core.billdata import BillData

_registry: list[type["Extractor"]] = []


class Extractor(ABC):
    name: str
    version: str
    supplier_nifs: frozenset[str]

    @abstractmethod
    def parse(self, pages: list[str]) -> BillData: ...


def register(cls: type[Extractor]) -> type[Extractor]:
    _registry.append(cls)
    return cls


def get_extractor(issuer_nif: str) -> Extractor | None:
    for cls in _registry:
        if issuer_nif in cls.supplier_nifs:
            return cls()
    return None


def all_extractors() -> list[type[Extractor]]:
    return list(_registry)
