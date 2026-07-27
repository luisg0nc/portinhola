from abc import ABC, abstractmethod

from pydantic import BaseModel

from portinhola.db.models import Contract


class Confirmation(BaseModel):
    reference: str
    detail: str = ""


_registry: list[type["Reporter"]] = []


class Reporter(ABC):
    name: str
    version: str
    supplier_nifs: frozenset[str]
    assisted: bool = False

    def supports(self, contract: Contract) -> bool:
        return contract.supplier_nif in self.supplier_nifs

    @abstractmethod
    def submit(self, readings: dict[str, float], contract: Contract) -> Confirmation: ...


def register(cls: type[Reporter]) -> type[Reporter]:
    _registry.append(cls)
    return cls


def get_reporter(supplier_nif: str) -> Reporter | None:
    for cls in _registry:
        if supplier_nif in cls.supplier_nifs:
            return cls()
    return None
