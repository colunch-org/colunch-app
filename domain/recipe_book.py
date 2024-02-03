import asyncio
import base64
import io
from pathlib import Path
from typing import Any
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

from domain.aopenai import DEFAULT_MODEL, MAX_TOKENS, openai_client_factory, quick_chat
from domain.prompts import (
    CREATE_RECIPE_PROMPT,
)  # pyright: ignore[reportMissingTypeStubs]


type UserDescription = str
type PartDescription = str
type Url = str
type RecipeContent = str
type Recipe = dict[str, str]


LLM_CLIENT = openai.AsyncClient()
DB_CLIENT = pinecone.Pinecone()


class AsyncJolt:
    async def __aenter__(self) -> None:
        await asyncio.sleep(0)

    async def __aexit__(self, *args: Any, **kwargs: Any) -> None:
        await asyncio.sleep(0)


async def parse_links(description: UserDescription) -> list[Url]:
    msg = (
        "Please provide all the links in this text, separated by commas. "
        "Include only the links in your response. "
        "If there are no links return <NULL>. "
        f"Text: {description}"
    )

    ans = await quick_chat(msg, openai_client=LLM_CLIENT)
    if ans.lower() == "<null>":
        return []
    return [l.strip() for l in ans.split(",") if l.lower() != "<null>"]


async def parse_part_description(description: UserDescription) -> PartDescription:
    msg = (
        "Please remove all the text from this description pertaining to links. "
        f"Respond only with the remaining text. Text: {description}"
    )
    return await quick_chat(msg, openai_client=LLM_CLIENT)


async def text_from_webpage(url: str) -> str:
    resp = await httpx.AsyncClient(timeout=20).get(url)
    resp.raise_for_status
    text = resp.text
    soup = bs4.BeautifulSoup(text, features="html.parser")
    return soup.text


async def audio_from_youtube_url(
    url: Url,
    base_path: Path | None = None,
) -> Path:
    base_path = Path("/tmp") if base_path is None else base_path
    yt = YouTube(url)

    async with AsyncJolt():
        audio = await asyncio.to_thread(yt.streams.get_audio_only)

    if not audio:
        raise ValueError("No audio.")

    audio_path = base_path / f"{uuid.uuid4().hex}.mp4"

    async with AsyncJolt():
        await asyncio.to_thread(audio.download, filename=str(audio_path))

    return audio_path


async def transcript_from_audio(audio: io.BufferedReader) -> str:
    resp = await LLM_CLIENT.audio.transcriptions.create(
        file=audio,
        model="whisper-1",
    )
    return resp.text


async def link_to_text(link: Url) -> PartDescription:
    # TODO: This is horrible
    base = link.replace("https://", "").replace("http://", "")
    if base.lower().startswith("www.bbcgoodfood.com"):
        text = await text_from_webpage(link)
    elif base.lower().startswith("www.youtube.com"):
        audio_path = await audio_from_youtube_url(link)
        with open(audio_path, "rb") as audio:
            text = await transcript_from_audio(audio)
    else:
        raise ValueError(f"Unable to process url: {link}")
    return text


async def create_recipe_from_text_and_images(
    description: UserDescription,
    images: list[io.BytesIO],
    http_client: httpx.AsyncClient | None = None,
    openai_client: openai.AsyncClient | None = None,
) -> RecipeContent:
    if not (description or images):
        raise ValueError("Provide a description or images.")

    http_client = openai_client_factory() if http_client is None else http_client
    openai_client = LLM_CLIENT if openai_client is None else openai_client

    system_message: ChatCompletionSystemMessageParam = {
        "role": "system",
        "content": CREATE_RECIPE_PROMPT,
    }

    messages: list[ChatCompletionMessageParam] = [system_message]

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
        resp = await openai_client.chat.completions.create(
            model=DEFAULT_MODEL,
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

    resp = await http_client.post(
        "https://api.openai.com/v1/chat/completions",
        json={
            "model": "gpt-4-vision-preview",
            "messages": messages,
            "max_tokens": MAX_TOKENS,
        },
    )

    data = resp.json()

    return data["choices"][0]["message"]["content"] or ""


async def recipe_name(recipe: RecipeContent) -> str:
    msg = f"Please provide an informative but concise name for this recipe: {recipe}"
    return await quick_chat(msg, openai_client=LLM_CLIENT)


async def recipe_summary(recipe: RecipeContent) -> str:
    msg = (
        "Please provide an exciting but informative summary of around 25 words "
        f"for this recipe: {recipe}"
    )
    return await quick_chat(msg, openai_client=LLM_CLIENT)


async def store_recipe(recipe: Recipe):
    idx = DB_CLIENT.Index("recipes")  # pyright: ignore[reportUnknownMemberType]
    if not idx:
        raise ValueError("No Index.")

    # Embedding based on content alone
    emb = await LLM_CLIENT.embeddings.create(
        input=recipe["content"],
        model="text-embedding-3-small",
    )
    vector = emb.data[0].embedding

    async with AsyncJolt():
        await asyncio.to_thread(
            idx.upsert,  # pyright: ignore[reportUnknownArgumentType, reportUnknownMemberType]
            vectors=[{"id": uuid.uuid4().hex, "values": vector, "metadata": recipe}],
        )


async def search_recipes(
    content: str,
    *,
    n: int = 3,
) -> list[Recipe]:
    emb = await LLM_CLIENT.embeddings.create(
        input=content,
        model="text-embedding-3-small",
    )
    vector = emb.data[0].embedding
    idx = DB_CLIENT.Index("recipes")  # pyright: ignore[reportUnknownMemberType]
    if not idx:
        raise ValueError("No Index.")

    async with AsyncJolt():
        res = await asyncio.to_thread(
            idx.query,  # pyright: ignore[reportUnknownArgumentType, reportUnknownMemberType]
            vector=vector,
            top_k=n,
            include_metadata=True,
        )

    return [m["metadata"] for m in res["matches"]]


async def create_recipe(
    *,
    description: UserDescription,
    images: list[io.BytesIO],
) -> Recipe:
    content = await create_recipe_from_text_and_images(
        description=description,
        images=images,
    )
    name = await recipe_name(content)
    summary = await recipe_summary(content)
    recipe = {"content": content, "name": name, "summary": summary}
    await store_recipe(recipe)
    return recipe


async def random_recipes(n: int = 5) -> tuple[str, list[Recipe]]:
    msg = (
        "Create a random phrase that might describe a recipe. "
        "Use around five words and return only the phrase."
    )
    phrase = await quick_chat(msg, openai_client=LLM_CLIENT)
    return phrase, await search_recipes(phrase, n=n)
