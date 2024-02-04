import asyncio
import base64
from enum import Enum
import io

import httpx
import openai
from openai.types.chat import (
    ChatCompletionMessageParam,
    ChatCompletionUserMessageParam,
    ChatCompletionSystemMessageParam,
)

from data import audio_from_youtube_url, text_from_webpage
from domain.aopenai import openai_client_factory, quick_chat
from domain.models import Recipe
from domain.prompts import CREATE_RECIPE_PROMPT


class Model(Enum):
    GPT_35_TURBO = "gpt-3.5-turbo"
    GPT_4_TURBO = "gpt-4-turbo-preview"


async def parse_links(description: str, openai_client: openai.AsyncClient) -> list[str]:
    msg = (
        "Please provide all the links in this text, separated by commas. "
        "Include only the links in your response. "
        "If there are no links return <NULL>. "
        f"Text: {description}"
    )

    ans = await quick_chat(msg, openai_client=openai_client)
    if ans.lower() == "<null>":
        return []
    return [l.strip() for l in ans.split(",") if l.lower() != "<null>"]


async def parse_part_description(
    description: str,
    openai_client: openai.AsyncClient,
) -> str:
    msg = (
        "Please remove all the text from this description pertaining to links. "
        f"Respond only with the remaining text. Text: {description}"
    )
    return await quick_chat(msg, openai_client=openai_client)


async def transcript_from_audio(
    audio: io.BufferedReader,
    openai_client: openai.AsyncClient,
) -> str:
    resp = await openai_client.audio.transcriptions.create(
        file=audio,
        model="whisper-1",
    )
    return resp.text


async def link_to_text(link: str, openai_client: openai.AsyncClient) -> str:
    # TODO: This is horrible
    base = link.replace("https://", "").replace("http://", "")
    if base.lower().startswith("www.bbcgoodfood.com"):
        text = await text_from_webpage(link)
    elif base.lower().startswith("www.youtube.com"):
        audio_path = await audio_from_youtube_url(link)
        with open(audio_path, "rb") as audio:
            text = await transcript_from_audio(audio, openai_client=openai_client)
    else:
        raise ValueError(f"Unable to process url: {link}")
    return text


class LLMService:
    def __init__(
        self,
        openai_client: openai.AsyncClient | None = None,
        http_client: httpx.AsyncClient | None = None,
        max_tokens: int = 3000,
    ) -> None:
        self.http_client = (
            openai_client_factory() if http_client is None else http_client
        )
        self.openai_client = (
            openai.AsyncClient() if openai_client is None else openai_client
        )
        self.max_tokens = max_tokens

    async def qa(self, q: str, *, model: Model = Model.GPT_4_TURBO) -> str:
        return await quick_chat(q, openai_client=self.openai_client, model=model.value)

    async def create_recipe(
        self,
        *,
        description: str,
        images: list[io.BufferedReader],
    ) -> str:
        if not (description or images):
            raise ValueError("Provide a description or images.")

        system_message: ChatCompletionSystemMessageParam = {
            "role": "system",
            "content": CREATE_RECIPE_PROMPT,
        }

        messages: list[ChatCompletionMessageParam] = [system_message]

        if description:
            links = await parse_links(description, openai_client=self.openai_client)
            part_description = await parse_part_description(
                description, openai_client=self.openai_client
            )
            coros = [
                link_to_text(link, openai_client=self.openai_client) for link in links
            ]
            link_texts = await asyncio.gather(*coros)
            full_description = "\n".join([part_description] + link_texts)
            text_message: ChatCompletionUserMessageParam = {
                "role": "user",
                "content": full_description,
            }
            messages.append(text_message)

        if not images:
            resp = await self.openai_client.chat.completions.create(
                model=Model.GPT_4_TURBO.value,
                messages=messages,
            )

            return resp.choices[0].message.content or ""

        image_message: ChatCompletionUserMessageParam = {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": (
                            "data:image/jpeg;base64,"
                            f"{base64.b64encode(image_data.read()).decode('utf-8')}"
                        ),
                    },
                }
                for image_data in images
            ],
        }

        messages.append(image_message)

        resp = await self.http_client.post(
            "https://api.openai.com/v1/chat/completions",
            json={
                "model": "gpt-4-vision-preview",
                "messages": messages,
                "max_tokens": self.max_tokens,
            },
        )

        data = resp.json()

        return data["choices"][0]["message"]["content"] or ""

    async def recipe_name(self, recipe: str) -> str:
        msg = (
            "Please provide an informative but concise name for this recipe: "
            f"{recipe}"
        )
        return await self.qa(msg)

    async def recipe_summary(self, recipe: str) -> str:
        msg = (
            "Please provide an exciting but informative summary of around 25 words "
            f"for this recipe: {recipe}"
        )
        return await self.qa(msg)

    async def embeddings(self, content: Recipe | str) -> list[float]:
        if isinstance(content, Recipe):
            content = content.content
        emb = await self.openai_client.embeddings.create(
            input=content,
            model="text-embedding-3-small",
        )
        return emb.data[0].embedding

    async def random_phrase(self) -> str:
        msg = (
            "Create a random phrase that might describe a recipe. "
            "Use around five words and return only the phrase."
        )
        return await self.qa(msg)
