import asyncio
import logging
from pathlib import Path
import uuid

import bs4
import httpx
from pytube import YouTube  # pyright: ignore[reportMissingTypeStubs]

from ajolt import AsyncJolt


logger = logging.getLogger(__name__)


async def text_from_webpage(url: str) -> str:
    resp = await httpx.AsyncClient(timeout=20).get(url)
    resp.raise_for_status
    text = resp.text
    soup = bs4.BeautifulSoup(text, features="html.parser")
    return soup.text


async def audio_from_youtube_url(
    url: str,
    base_path: Path | None = None,
) -> Path:
    logger.info(url)
    base_path = Path("/tmp") if base_path is None else base_path
    yt = YouTube(url)

    logger.info("Getting audio")
    async with AsyncJolt():
        audio = await asyncio.to_thread(yt.streams.get_audio_only)

    if not audio:
        raise ValueError("No audio.")

    audio_path = base_path / f"{uuid.uuid4().hex}.mp4"

    async with AsyncJolt():
        await asyncio.to_thread(audio.download, filename=str(audio_path))

    logger.info("Got audio.")
    return audio_path
