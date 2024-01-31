import asyncio
import base64
import io
import os
from pathlib import Path
from typing import Any, Protocol
import uuid

import bs4
import httpx
import openai
from openai.types.chat import (
    ChatCompletionMessageParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
)
import pinecone  # pyright: ignore[reportMissingTypeStubs]
from pytube import YouTube  # pyright: ignore[reportMissingTypeStubs]

from domain.prompts import CreateRecipePrompt


type UserDescription = str
type PartDescription = str
type Url = str
type RecipeContent = str


LLM_CLIENT = openai.AsyncClient()
DB_CLIENT = pinecone.Pinecone()


class AsyncJolt:
    async def __aenter__(self) -> None:
        await asyncio.sleep(0)

    async def __aexit__(self, *args: Any, **kwargs: Any) -> None:
        await asyncio.sleep(0)


async def parse_links(description: UserDescription) -> list[Url]:
    resp = await LLM_CLIENT.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "user",
                "content": (
                    "Please provide all the links in this text, separated by commas. "
                    "Include only the links in your response. "
                    "If there are no links return <NULL>. "
                    f"Text: {description}"
                ),
            }
        ],
    )
    return [
        l.strip()
        for l in (resp.choices[0].message.content or "").split(",")
        if l.lower() != "<null>"
    ]


async def parse_part_description(description: UserDescription) -> PartDescription:
    resp = await LLM_CLIENT.chat.completions.create(
        model="gpt-4-turbo-preview",
        messages=[
            {
                "role": "user",
                "content": (
                    "Please remove all the text from this description pertaining to links. "
                    f"Respond only with the remaining text. Text: {description}"
                ),
            }
        ],
    )
    return (resp.choices[0].message.content or "").strip()


async def text_from_webpage(url: str) -> str:
    resp = await httpx.AsyncClient(timeout=20).get(url)
    resp.raise_for_status
    text = resp.text
    soup = bs4.BeautifulSoup(text, features="html.parser")
    return soup.text


async def audio_from_youtube_url(url: Url) -> Path:
    yt = YouTube(url)

    async with AsyncJolt():
        audio = await asyncio.to_thread(yt.streams.get_audio_only)

    if not audio:
        raise ValueError("No audio.")

    audio_path = Path(f"{uuid.uuid4().hex}.mp4")

    async with AsyncJolt():
        await asyncio.to_thread(audio.download, filename=str(audio_path))

    return audio_path


async def transcript_from_audio(audio: Path) -> str:
    with open(audio, "rb") as audio_file:
        resp = await LLM_CLIENT.audio.transcriptions.create(
            file=audio_file,
            model="whisper-1",
        )
    return resp.text


async def link_to_text(link: Url) -> PartDescription:
    base = link.replace("https://", "").replace("http://", "")
    if base.lower().startswith("www.bbcgoodfood.com"):
        text = await text_from_webpage(link)
    elif base.lower().startswith("www.youtube.com"):
        audio_path = await audio_from_youtube_url(link)
        text = await transcript_from_audio(audio_path)
    else:
        raise ValueError(f"Unable to process url: {link}")
    return text


async def create_recipe_from_text_and_images(
    description: UserDescription,
    images: list[io.BytesIO],
) -> RecipeContent:
    if not (description or images):
        raise ValueError("Provide a description or images.")

    system_message: ChatCompletionSystemMessageParam = {
        "role": "system",
        "content": str(CreateRecipePrompt()),
    }

    messages: list[ChatCompletionMessageParam] = [system_message]

    # munge text content
    if description:
        links = await parse_links(description)
        part_description = await parse_part_description(description)
        coros = [link_to_text(link) for link in links]
        link_texts = await asyncio.gather(*coros)
        full_description = "\n".join([part_description] + link_texts)
        text_message: ChatCompletionUserMessageParam = {
            "role": "user",
            "content": full_description,
        }
        messages.append(text_message)

    if not images:
        resp = await LLM_CLIENT.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=messages,
        )

        return resp.choices[0].message.content or ""

    # image bytes to base64 encoding
    image_message: ChatCompletionUserMessageParam = {
        "role": "user",
        "content": [
            {
                "type": "image_url",
                "image_url": {
                    # TODO: just how much work is this?
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

    resp = await httpx.AsyncClient(
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {os.environ.get('OPENAI_API_KEY')}",
        },
        timeout=60 * 5,
    ).post(
        "https://api.openai.com/v1/chat/completions",
        json={
            "model": "gpt-4-vision-preview",
            "messages": messages,
            "max_tokens": 3000,
        },
    )

    data = resp.json()

    return data["choices"][0]["message"]["content"] or ""


async def recipe_name(recipe: RecipeContent) -> str:
    msg = f"Please provide an informative but concise name for this recipe: {recipe}"
    resp = await LLM_CLIENT.chat.completions.create(
        model="gpt-4-turbo-preview",
        messages=[{"role": "user", "content": msg}],
    )
    return resp.choices[0].message.content or ""


async def recipe_summary(recipe: RecipeContent) -> str:
    msg = (
        "Please provide an exciting but informative summary of around 25 words "
        f"for this recipe: {recipe}"
    )
    resp = await LLM_CLIENT.chat.completions.create(
        model="gpt-4-turbo-preview",
        messages=[{"role": "user", "content": msg}],
    )
    return resp.choices[0].message.content or ""


async def store_recipe(recipe: RecipeContent):

    emb = await LLM_CLIENT.embeddings.create(
        input=recipe,
        model="text-embedding-3-small",
    )
    vector = emb.data[0].embedding
    idx = DB_CLIENT.Index("recipes")
    async with AsyncJolt():
        await asyncio.to_thread(
            idx.upsert,
            vectors=[
                {
                    "id": uuid.uuid4().hex,
                    "values": vector,
                    "metadata": {"content": recipe},
                }
            ],
        )


class RecipeGenerator(Protocol):
    async def __await__(self, description: UserDescription) -> RecipeContent: ...


class RecipeBook:
    def __init__(
        self,
        generate: RecipeGenerator,
    ) -> None:
        self._generate = generate
