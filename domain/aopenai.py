import os

import httpx


OPENAI_TOKEN = os.environ.get("OPENAI_API_KEY")
MAX_TOKENS = 3000
TIMEOUT = 60 * 2
DEFAULT_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4-turbo-preview")


def openai_client_factory(token: str | None = None) -> httpx.AsyncClient:
    token = OPENAI_TOKEN if token is None else token
    return httpx.AsyncClient(
        base_url="https://api.openai.com/v1/",
        headers={
            "Authorization": f"Bearer {OPENAI_TOKEN}",
            "Content-Type": "application/json",
            "OpenAI-Beta": "assistants=v1",
        },
        timeout=TIMEOUT,
    )
