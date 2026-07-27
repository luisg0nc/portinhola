from datetime import date

from pydantic import BaseModel


class FiscalQR(BaseModel):
    issuer_nif: str
    buyer_nif: str | None
    doc_type: str
    doc_number: str
    atcud: str | None
    issue_date: date
    total_cents: int
    vat_fields: dict[str, str]
    raw: str


def parse_fiscal_qr(text: str) -> FiscalQR | None:
    fields: dict[str, str] = {}
    for part in text.split("*"):
        if ":" in part:
            key, _, value = part.partition(":")
            fields[key] = value
    if "A" not in fields or "O" not in fields or "F" not in fields:
        return None
    raw_date = fields["F"]
    try:
        issue_date = date(int(raw_date[:4]), int(raw_date[4:6]), int(raw_date[6:8]))
        total_cents = round(float(fields["O"]) * 100)
    except ValueError:
        return None
    vat_keys = [k for k in fields if k[0] in "IJKLMN"]
    return FiscalQR(
        issuer_nif=fields["A"],
        buyer_nif=fields.get("B"),
        doc_type=fields.get("D", "FT"),
        doc_number=fields.get("G", ""),
        atcud=fields.get("H"),
        issue_date=issue_date,
        total_cents=total_cents,
        vat_fields={k: fields[k] for k in vat_keys},
        raw=text,
    )
