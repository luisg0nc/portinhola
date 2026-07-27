from pathlib import Path

FIXTURES = Path(__file__).parent


def load_pages(rel_path: str) -> list[str]:
    return (FIXTURES / rel_path).read_text().split("\f")
