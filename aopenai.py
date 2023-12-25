import asyncio
import base64
from enum import Enum
from io import BufferedReader
import os
from pathlib import Path
from typing import Any, Protocol, Self

import httpx


OPENAI_TOKEN = os.environ.get("OPENAI_API_KEY")
MAX_TOKENS = 3000


def openai_client(token: str | None = None) -> httpx.AsyncClient:
    token = OPENAI_TOKEN if token is None else token
    return httpx.AsyncClient(
        base_url="https://api.openai.com/v1/",
        headers={
            "Authorization": f"Bearer {OPENAI_TOKEN}",
            "OpenAI-Beta": "assistants=v1",
        },
        timeout=60 * 2,
    )


def encode_image(image_path: Path | str):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


system_msg = {
    "role": "system",
    "content": (
        "You are a helpful assistant."
        # " who gives answers in a format consistent with GitHub flavour markdown. "
        # "Do not tell me the answer is consistent with GitHub flavour markdown and "
        # "do not include the ``` fences."
    ),
}


class Content(Protocol):
    def to_dict(self) -> dict[str, Any]:
        ...


class ContentType(Enum):
    text = "text"
    image_url = "image_url"


class TextContent:
    type = ContentType.text

    def __init__(self, text: str) -> None:
        self.text = text

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type.value, "text": self.text}


class ImgContent:
    type = ContentType.image_url

    @classmethod
    def from_path(cls, path: Path | str) -> Self:
        base64_image = encode_image(path)
        url = f"data:image/jpeg;base64,{base64_image}"
        return cls(url=url)

    def __init__(self, url: str) -> None:
        self.url = url

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type.value, "image_url": {"url": self.url}}


class ChatMsg:
    def __init__(self, *, role: str, content: str | list[Content]) -> None:
        self.role = role
        self.content = content

    def to_dict(self) -> dict[str, Any]:
        content = (
            self.content
            if isinstance(self.content, str)
            else [c.to_dict() for c in self.content]
        )
        return {"role": self.role, "content": content}


class Chat:
    @classmethod
    def from_system_prompt(
        cls,
        prompt: str,
        *,
        model: str = "gpt-4-1106-preview",
        client: httpx.AsyncClient | None = None,
    ) -> Self:
        messages: list[ChatMsg] = [ChatMsg(role="system", content=prompt)]
        return cls(model=model, messages=messages, client=client)

    def __init__(
        self,
        *,
        model: str = "gpt-4-1106-preview",
        messages: list[ChatMsg] | None = None,
        max_tokens: int = MAX_TOKENS,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.model = model
        self._messages: list[ChatMsg] = [] if messages is None else messages
        self.max_tokens = max_tokens
        self._client = openai_client() if client is None else client

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "messages": [m.to_dict() for m in self._messages],
            "max_tokens": self.max_tokens,
        }

    async def _chat_raw(self, data: dict[str, Any]) -> list[ChatMsg]:
        resp = await self._client.post("chat/completions", json=data)
        data = resp.json()
        if "error" in data:
            raise ValueError(f"Problem creating completion. {data}")
        return [ChatMsg(**c["message"]) for c in data["choices"]]

    async def send_messages(self) -> list[ChatMsg]:
        return await self._chat_raw(self.to_dict())

    async def chat(self, msg: str | ChatMsg) -> str:
        chat_msg = ChatMsg(role="user", content=msg) if isinstance(msg, str) else msg
        self._messages.append(chat_msg)
        chat_msgs = await self.send_messages()
        self._messages.extend(chat_msgs)
        s = ""
        for part in chat_msgs:
            if isinstance(part.content, str):
                s += "\n" + part.content
            else:
                raise RuntimeError("Non-string response content not supported.")
        return s

    async def close(self) -> None:
        await self._client.aclose()


class AudioTranslation:
    def __init__(
        self,
        *,
        model: str = "whisper-1",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.model = model
        self._client = openai_client() if client is None else client

    async def translate(
        self, audio: BufferedReader, *, response_format: str = "text"
    ) -> str:
        resp = await self._client.post(
            "audio/translations", files={"file": audio}, data={"model": self.model}
        )
        data = resp.json()
        if "error" in data:
            raise ValueError(f"Problem creating translation. {data}")
        text = data.get("text")
        if not "text":
            raise ValueError(
                "Problem creating translation. "
                "Possibly wrong format. Expecting a 'text' key. "
                f"{data}"
            )
        return text


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
