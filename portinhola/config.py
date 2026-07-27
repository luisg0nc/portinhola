from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PORTINHOLA_")

    data_dir: Path = Path("./data")
    cookie_secure: bool = False

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.data_dir / 'portinhola.db'}"
