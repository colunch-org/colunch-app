from enum import Enum
from pathlib import Path
from urllib.parse import urlencode
import uuid

from pydantic_settings import BaseSettings
from pytube import YouTube  # pyright: ignore[reportMissingTypeStubs]

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket

from aopenai import AudioTranslation, Chat, ChatMsg


# https://www.youtube.com/watch?v=UfOQyurFHAo
# https://www.youtube.com/watch?v=S1NRL9-xOdU


class Env(Enum):
    local = "local"
    dev = "dev"
    prod = "prod"


class Config(BaseSettings):
    env: Env = Env.local
    templates_dir: Path = Path("templates")


CONFIG = Config()


with open(CONFIG.templates_dir / "index.html") as f:
    INDEX_HTML = f.read()


async def homepage(request: Request) -> HTMLResponse:
    return HTMLResponse(INDEX_HTML)


async def youtube(request: Request) -> HTMLResponse:
    async with request.form() as form:
        print(form)
        url = form.get("youtube-url")
    print(url)
    if not isinstance(url, str):
        return HTMLResponse("URL not a string.")
    url = urlencode({"youtube-url": url})
    print(url)
    ws = f"""
    <div hx-ext="ws" ws-connect="/recipe-from-youtube?{url}">
      <div id="chat" hx-swap-oob="beforeend"></div>
    </div>
    """
    return HTMLResponse(ws)


async def recipe_from_youtube(ws: WebSocket) -> None:
    print(ws.query_params)
    url = ws.query_params["youtube-url"]
    await ws.accept()
    # check is valid
    # return a red input box or notification or something
    yt = YouTube(url)

    audio = yt.streams.get_audio_only()

    await ws.send_text("<div>Grabbed audio.</div>")

    if not audio:
        raise ValueError("No audio.")

    audio_path = Path(f"{uuid.uuid4().hex}.mp4")
    print(audio_path)

    audio.download(filename=str(audio_path))

    with open(audio_path, "rb") as audio_file:
        translation = await AudioTranslation().translate(audio=audio_file)

    audio_path.unlink()

    print(translation)
    await ws.send_text(f"<div>{translation}</div>")
    prompt = [
        ChatMsg(
            role="system",
            content="You are a world class assistant for summarising cooking video transcripts",
        ),
    ]

    msg = (
        "List the ingredients and preparation steps for each recipe in the "
        f"following transcript. {translation}"
    )

    recipe = await Chat(messages=prompt).chat(msg)
    print(recipe)
    await ws.send_text(f"<div>{recipe}</div>")


app = Starlette(
    routes=[
        Route("/", homepage),
        Route("/youtube", youtube, methods=["POST"]),
        WebSocketRoute("/recipe-from-youtube", recipe_from_youtube),
    ],
)
