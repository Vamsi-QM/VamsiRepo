"""Configuration for VamsiCompanion. Reads environment variables with .env fallback."""

from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Optional


def _load_dotenv(path: Optional[Path] = None) -> None:
    """Load KEY=VALUE lines from a .env file if present. Never overrides real env vars."""
    dotenv = path or Path(__file__).resolve().parent.parent / ".env"
    if not dotenv.exists():
        return
    for raw in dotenv.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


class Config:
    def __init__(self, env=None):
        env = os.environ if env is None else env
        _load_dotenv()

        self.host: str = env.get("HOST", "127.0.0.1")
        self.port: int = int(env.get("PORT", "8765"))
        self.phone_access_enabled: bool = env.get("PHONE_ACCESS_ENABLED", "0").strip().lower() in {
            "1", "true", "yes", "on"
        }

        data_dir = Path(env.get("DATA_DIR", r"D:\VamsiCompanion\data"))
        model_path = Path(env.get("MODEL_PATH", r"D:\VamsiCompanion\models\qwen2.5-1.5b-instruct-q4_k_m.gguf"))
        db_name = env.get("DB_NAME", "companion.db")

        self.data_dir: Path = data_dir
        self.database_path: Path = data_dir / db_name
        self.model_path: Path = model_path
        self.pairing_token_path: Path = data_dir / "pairing_token.txt"

        self.n_ctx: int = int(env.get("N_CTX", "2048"))
        self.n_threads: int = int(env.get("N_THREADS", "8"))
        self.max_tokens: int = int(env.get("MAX_TOKENS", "512"))
        self.temperature: float = float(env.get("TEMPERATURE", "0.7"))

        self.max_turns: int = int(env.get("MAX_TURNS", "12"))
        self.max_tool_iterations: int = int(env.get("MAX_TOOL_ITERATIONS", "4"))
        self.request_timeout_seconds: float = float(env.get("REQUEST_TIMEOUT_SECONDS", "180"))

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def pairing_token(self) -> str:
        env_token = os.environ.get("PAIRING_TOKEN", "").strip()
        if env_token:
            return env_token
        self.ensure_dirs()
        if self.pairing_token_path.exists():
            token = self.pairing_token_path.read_text(encoding="utf-8").strip()
            if token:
                return token
        token = secrets.token_urlsafe(24)
        self.pairing_token_path.write_text(token, encoding="utf-8")
        return token

    @property
    def model_available(self) -> bool:
        return self.model_path.exists()


DEFAULT_CONFIG = Config()
