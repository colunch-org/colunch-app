import asyncio
import os
from typing import Any

import httpx


OPENAI_TOKEN = os.environ.get("OPENAI_API_KEY")


def openai_client(token: str | None = None) -> httpx.AsyncClient:
    token = OPENAI_TOKEN if token is None else token
    return httpx.AsyncClient(
        base_url="https://api.openai.com/v1/",
        headers={
            "Authorization": f"Bearer {OPENAI_TOKEN}",
            "OpenAI-Beta": "assistants=v1",
        },
    )


system_msg = {
    "role": "system",
    "content": (
        "You are a helpful assistant."
        # " who gives answers in a format consistent with GitHub flavour markdown. "
        # "Do not tell me the answer is consistent with GitHub flavour markdown and "
        # "do not include the ``` fences."
    ),
}


class ChatMsg:
    def __init__(self, *, role: str, content: str) -> None:
        self.role = role
        self.content = content

    def dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


class Chat:
    def __init__(
        self,
        *,
        model: str = "gpt-4-1106-preview",
        messages: list[ChatMsg] | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.model = model
        self._messages: list[ChatMsg] = [] if messages is None else messages
        self._client = openai_client() if client is None else client

    def dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "messages": [m.dict() for m in self._messages],
        }

    async def chat(self, msg: str) -> str:
        self._messages.append(ChatMsg(role="user", content=msg))
        resp = await self._client.post("chat/completions", json=self.dict())
        data = resp.json()
        if "error" in data:
            raise ValueError(f"Problem creating completion. {data}")
        chat_msgs = [ChatMsg(**c["message"]) for c in data["choices"]]
        self._messages.extend(chat_msgs)
        return "\n".join(c.content for c in chat_msgs)

    async def close(self) -> None:
        await self._client.aclose()


async def main():
    chat = Chat()
    while True:
        msg = input("Qu: ")
        if msg in ["q", "Q"]:
            break
        print(await chat.chat(msg))
        print()
    await chat.close()


if __name__ == "__main__":
    asyncio.run(main())
