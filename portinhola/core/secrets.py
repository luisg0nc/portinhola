import os
import secrets
from pathlib import Path


def load_or_create_app_key(data_dir: Path) -> bytes:
    data_dir.mkdir(parents=True, exist_ok=True)
    key_file = data_dir / "app_key"
    if key_file.exists():
        return key_file.read_bytes()
    key = secrets.token_bytes(32)
    key_file.write_bytes(key)
    os.chmod(key_file, 0o600)
    return key
