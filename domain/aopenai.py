import os

import httpx
import openai


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


async def quick_chat(
    msg: str,
    *,
    openai_client: openai.AsyncClient | None = None,
    model: str | None = None,
) -> str:
    openai_client = openai.AsyncClient() if openai_client is None else openai_client
    model = DEFAULT_MODEL if model is None else model
    resp = await openai_client.chat.completions.create(
        model=DEFAULT_MODEL,
        messages=[{"role": "user", "content": msg}],
    )
    ans = resp.choices[0].message.content or ""
    return ans.strip()
