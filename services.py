"""Functionality behind the routes."""

import asyncio
from pathlib import Path
from typing import Iterable
import uuid

import bs4
import httpx
from pytube import YouTube  # pyright: ignore[reportMissingTypeStubs]

from aopenai import AudioTranslation, Chat, ChatMsg, Content, ImgContent, TextContent
import db
from models import Recipe
from prompts import CreateRecipePrompt


async def recipe_from_images(img_paths: Iterable[Path]) -> Recipe:
    content: list[Content] = [TextContent(CreateRecipePrompt())]
    for img_path in img_paths:
        content.append(ImgContent.from_path(img_path))
        img_path.unlink()

    chat = Chat(model="gpt-4-vision-preview")

    text = await chat.chat(ChatMsg(role="user", content=content))
    await db.create_recipe(text)
    return Recipe(text)


async def audio_from_youtube_url(url: str) -> Path:
    yt = YouTube(url)

    await asyncio.sleep(0)
    audio = await asyncio.to_thread(yt.streams.get_audio_only)
    await asyncio.sleep(0)

    if not audio:
        raise ValueError("No audio.")

    audio_path = Path(f"{uuid.uuid4().hex}.mp4")

    await asyncio.sleep(0)
    await asyncio.to_thread(audio.download, filename=str(audio_path))
    await asyncio.sleep(0)

    return audio_path


async def transcript_from_audio(audio: Path) -> str:
    with open(audio, "rb") as audio_file:
        translation = await AudioTranslation().translate(audio=audio_file)
    return translation


async def recipe_from_transcript(text: str) -> Recipe:
    prompt = CreateRecipePrompt()
    messages = [ChatMsg(role="system", content=prompt)]
    msg = f"Transcript: {text}"
    text = await Chat(messages=messages).chat(msg)
    await db.create_recipe(text)
    return Recipe(text)


async def text_from_webpage(url: str) -> str:
    resp = await httpx.AsyncClient().get(url)
    resp.raise_for_status
    text = resp.text
    soup = bs4.BeautifulSoup(text, features="html.parser")
    return soup.text


async def recipe_from_webpage_text(text: str) -> Recipe:
    prompt = CreateRecipePrompt()
    messages = [ChatMsg(role="system", content=prompt)]
    msg = f"Webpage content: {text}"
    text = await Chat(messages=messages).chat(msg)
    await db.create_recipe(text)
    return Recipe(text)
