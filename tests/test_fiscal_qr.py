from datetime import date

from portinhola.core.fiscal_qr import parse_fiscal_qr

G9_QR = (
    "A:504435302*B:299999998*C:PT*D:FT*E:N*F:20260709*G:FC FAE/0000003*"
    "H:CCCCCCCC-000003*I1:PT*I3:35.24*I4:2.11*I7:39.03*I8:8.98*N:11.09*"
    "O:85.36*Q:gtRh*R:2057*"
)


def test_parses_g9_style_qr() -> None:
    qr = parse_fiscal_qr(G9_QR)
    assert qr is not None
    assert qr.issuer_nif == "504435302"
    assert qr.buyer_nif == "299999998"
    assert qr.doc_type == "FT"
    assert qr.doc_number == "FC FAE/0000003"
    assert qr.atcud == "CCCCCCCC-000003"
    assert qr.issue_date == date(2026, 7, 9)
    assert qr.total_cents == 8536
    assert qr.vat_fields["I3"] == "35.24"
    assert qr.raw == G9_QR


def test_rejects_non_fiscal_text() -> None:
    assert parse_fiscal_qr("www.valongo-bewater.com.pt") is None
    assert parse_fiscal_qr("") is None
