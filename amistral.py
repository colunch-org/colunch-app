import asyncio
import os
from typing import Any

import httpx


BASE_URL = "https://api.mistral.ai/v1/"


class MistralClient:
    def __init__(
        self,
        model: str = "mistral-medium",
        token: str | None = None,
        messages: list[dict[str, str]] | None = None,
        safe_mode: bool = True,
    ) -> None:
        self.model = model
        self.token = os.environ.get("MISTRAL_API_KEY") if token is None else token
        self.aclient = httpx.AsyncClient(
            base_url=BASE_URL,
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=60 * 5,
        )
        self.client = httpx.Client(
            base_url=BASE_URL,
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=60 * 5,
        )
        self.messages = [] if messages is None else messages
        self.safe_mode = safe_mode

    @property
    def payload(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "messages": self.messages,
            "safe_mode": self.safe_mode,
        }

    def add_user_message(self, msg: str) -> None:
        self.messages.append(
            {
                "role": "user",
                "content": msg,
            }
        )

    async def achat(self, msg: str) -> str:
        self.add_user_message(msg)
        resp = await self.aclient.post("/chat/completions", json=self.payload)
        data = resp.json()
        ans = data["choices"][0]["message"]
        self.messages.append(ans)
        return ans["content"]

    def chat(self, msg: str) -> str:
        self.add_user_message(msg)
        resp = self.client.post("/chat/completions", json=self.payload)
        data = resp.json()
        ans = data["choices"][0]["message"]
        self.messages.append(ans)
        return ans["content"]


async def main() -> None:
    cl = MistralClient()

    while True:
        qu = input("Qu: ")
        if qu.lower() in ("q", "quit", "exit"):
            break
        ans = await cl.achat(qu)
        print(ans)


if __name__ == "__main__":
    from rich import print

    asyncio.run(main())
