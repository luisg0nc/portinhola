"""Run all tariff parsers and watchers; write summary.md + state.json.

Exit code is always 0 — outcomes are reported via files so the workflow
can branch on them:
  - updated tariff YAMLs (parser results)      → PR material
  - state.json hash refreshes                  → PR material
  - summary.md                                 → PR body
  - failures / watch changes listed in summary → issue material
    (also emitted as issues.json for the workflow)
"""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from tools.tariff_watch import watch
from tools.tariff_watch.apply import apply_updates
from tools.tariff_watch.base import TARIFFS_DIR, ParseFailed, fetch
from tools.tariff_watch.parsers import endesa, galp, goldenergy, regulated_gas

STATE_PATH = Path(__file__).parent / "state.json"
SUMMARY_PATH = Path(__file__).parent / "summary.md"
ISSUES_PATH = Path(__file__).parent / "issues.json"

PARSERS = [galp, endesa, goldenergy, regulated_gas]


def main(check_only: bool = False) -> int:
    today = datetime.now(UTC).date()
    changed_files: list[str] = []
    failures: list[str] = []
    watch_changes: list[str] = []

    for module in PARSERS:
        name = module.__name__.rsplit(".", 1)[-1]
        try:
            updates = module.parse(fetch(module.URL))
            for rel_path, fields in updates.items():
                path = TARIFFS_DIR / rel_path
                if check_only:
                    continue
                if apply_updates(path, fields, today):
                    changed_files.append(rel_path)
        except ParseFailed as exc:
            failures.append(f"{name}: {exc}")
        except Exception as exc:  # noqa: BLE001 - network errors must surface, not crash
            failures.append(f"{name}: fetch/apply error: {exc}")

    state = json.loads(STATE_PATH.read_text()) if STATE_PATH.exists() else {}
    parsed_urls = {module.URL for module in PARSERS}
    for url, files in watch.watched_urls(parsed_urls).items():
        try:
            fingerprint, changed = watch.check(url, state.get(url))
        except Exception as exc:  # noqa: BLE001
            failures.append(f"watch {url}: {exc}")
            continue
        if changed:
            watch_changes.append(f"{url} (affects: {', '.join(files)})")
        state[url] = fingerprint
    if not check_only:
        STATE_PATH.write_text(json.dumps(state, indent=1, sort_keys=True) + "\n")

    lines = [f"# Tariff watch — {today.isoformat()}", ""]
    lines.append("## Updated from official sources")
    lines += [f"- `{f}`" for f in changed_files] or ["- nothing changed"]
    if watch_changes:
        lines += ["", "## Watched sources with price changes (review manually)"]
        lines += [f"- {w}" for w in watch_changes]
    if failures:
        lines += ["", "## Failures (source layout changed?)"]
        lines += [f"- {f}" for f in failures]
    SUMMARY_PATH.write_text("\n".join(lines) + "\n")
    ISSUES_PATH.write_text(
        json.dumps({"watch_changes": watch_changes, "failures": failures}, indent=1)
        + "\n"
    )
    print(SUMMARY_PATH.read_text())
    return 0


if __name__ == "__main__":
    sys.exit(main(check_only="--check" in sys.argv))
