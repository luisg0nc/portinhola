"""Dump a bill PDF's text pages with personal data replaced, for use as a
public test fixture. Review the output manually before committing."""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from portinhola.core.pdf import extract_pdf  # noqa: E402

REPLACEMENTS: list[tuple[str, str]] = [
    (r"Maria Exemplo Silva", "Maria Exemplo Silva"),
    (r"MARIA EXEMPLO SILVA", "MARIA EXEMPLO SILVA"),
    (r"299999998", "299999998"),
    (r"maria@example.com", "maria@example.com"),
    (r"A ?venida Exemplo[^\n]*", "Rua Exemplo, 1"),
    (r"AVEN[^\n]*PR[I]?MAVERA[^\n]*", "RUA EXEMPLO 1"),
    (r"4000-000 CIDADE", "4000-000 CIDADE"),
    (r"CIDADE", "CIDADE"),
    (r"PT50[\d*]{18,}", "PT50000000000000000000000"),
    (r"Mandato: \d+", "Mandato: 10000000000"),
    (r"Mandato\n\d+", "Mandato\n10000000000"),
]


def main(pdf_path: str, out_path: str) -> None:
    pages = extract_pdf(Path(pdf_path)).pages
    text = "\f".join(pages)
    for pattern, repl in REPLACEMENTS:
        text = re.sub(pattern, repl, text)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(text)
    print(f"wrote {out_path} — REVIEW IT MANUALLY before committing")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
