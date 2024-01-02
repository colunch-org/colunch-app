from enum import Enum
from pathlib import Path

from pydantic_settings import BaseSettings


class Env(Enum):
    local = "local"
    dev = "dev"
    prod = "prod"


class Config(BaseSettings):
    env: Env = Env.local
    html_dir: Path = Path("assets/html")
    db_url: str = "sqlite+aiosqlite:///colunch.db"
