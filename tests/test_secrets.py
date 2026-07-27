import stat

from portinhola.core.secrets import load_or_create_app_key


def test_creates_32_byte_key(tmp_path) -> None:
    key = load_or_create_app_key(tmp_path)
    assert isinstance(key, bytes)
    assert len(key) == 32


def test_key_is_stable_across_calls(tmp_path) -> None:
    assert load_or_create_app_key(tmp_path) == load_or_create_app_key(tmp_path)


def test_key_file_is_owner_only(tmp_path) -> None:
    load_or_create_app_key(tmp_path)
    mode = stat.S_IMODE((tmp_path / "app_key").stat().st_mode)
    assert mode == 0o600
