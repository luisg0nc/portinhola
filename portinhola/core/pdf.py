from pathlib import Path

import pdfplumber
import pypdfium2 as pdfium
import zxingcpp
from pydantic import BaseModel

from portinhola.core.fiscal_qr import FiscalQR, parse_fiscal_qr


class ExtractedPdf(BaseModel):
    pages: list[str]
    qr: FiscalQR | None


def extract_pdf(path: Path) -> ExtractedPdf:
    with pdfplumber.open(path) as pdf:
        pages = [page.extract_text() or "" for page in pdf.pages]

    qr: FiscalQR | None = None
    doc = pdfium.PdfDocument(path)
    try:
        for page in doc:
            image = page.render(scale=3).to_pil()
            for result in zxingcpp.read_barcodes(image):
                if result.format == zxingcpp.BarcodeFormat.QRCode:
                    parsed = parse_fiscal_qr(result.text)
                    if parsed is not None:
                        qr = parsed
                        break
            if qr is not None:
                break
    finally:
        doc.close()
    return ExtractedPdf(pages=pages, qr=qr)
