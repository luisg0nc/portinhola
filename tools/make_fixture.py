"""Dump a bill PDF's text pages with personal data replaced, for use as a
public test fixture. Review the output manually before committing.

The regex replacement rules live in `tools/fixture_replacements_local.py`
(gitignored, because the patterns themselves contain your real personal
data). Copy `fixture_replacements_example.py` to that name and fill in
your own bill's values.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from portinhola.core.pdf import extract_pdf

try:
    from tools.fixture_replacements_local import REPLACEMENTS
except ImportError:
    sys.exit(
        "tools/fixture_replacements_local.py not found — copy "
        "tools/fixture_replacements_example.py and fill in your values."
    )


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
