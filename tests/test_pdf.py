from portinhola.core.pdf import extract_pdf


def _make_pdf_with_qr(path, qr_text: str) -> None:
    import zxingcpp
    from PIL import Image

    bitmap = zxingcpp.write_barcode(
        zxingcpp.BarcodeFormat.QRCode, qr_text, width=300, height=300
    )
    img = Image.fromarray(bitmap).convert("RGB")
    img.save(path, "PDF", resolution=72)


def test_extracts_qr_from_pdf(tmp_path) -> None:
    from tests.test_fiscal_qr import G9_QR

    pdf_path = tmp_path / "bill.pdf"
    _make_pdf_with_qr(pdf_path, G9_QR)
    result = extract_pdf(pdf_path)
    assert result.qr is not None
    assert result.qr.total_cents == 8536
    assert len(result.pages) == 1
