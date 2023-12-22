from enum import Enum
from pathlib import Path
from urllib.parse import urlencode
import uuid

from markdown2 import markdown  # pyright: ignore[reportMissingTypeStubs]
from pydantic_settings import BaseSettings
from pytube import YouTube  # pyright: ignore[reportMissingTypeStubs]
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse
from starlette.routing import Mount, Route, WebSocketRoute
from starlette.staticfiles import StaticFiles
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
    html_dir: Path = Path("assets/html")


CONFIG = Config()


with open(CONFIG.html_dir / "index.html") as f:
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
    <div
      id="recipe-from-youtube-ws"
      hx-swap-oob="true"
      hx-ext="ws"
      ws-connect="/recipe-from-youtube?{url}"
    ></div>
    """
    return HTMLResponse(ws)


async def recipe_from_youtube(ws: WebSocket) -> None:
    print(ws.query_params)
    url = ws.query_params["youtube-url"]
    await ws.accept()
    # check is valid
    # return a red input box or notification or something
    yt = YouTube(url)

    await ws.send_text("""
        <input
          id="youtube-url"
          name="youtube-url"
          type="text"
          class="form-control"
          placeholder="YouTube url ..."
          hx-post="/youtube"
          hx-swap-oob="true"
        ></input>
    """)

    await ws.send_text(f'<div id="recipe-content" hx-swap-oob="true">Grabbing audio for {url} ...</div>')
    audio = yt.streams.get_audio_only()

    if not audio:
        raise ValueError("No audio.")

    audio_path = Path(f"{uuid.uuid4().hex}.mp4")

    audio.download(filename=str(audio_path))

    await ws.send_text('<div id="recipe-content" hx-swap-oob="true">Grabbing transcript ...</div>')
    with open(audio_path, "rb") as audio_file:
        translation = await AudioTranslation().translate(audio=audio_file)

    audio_path.unlink()

    await ws.send_text('<div id="recipe-content" hx-swap-oob="true">Grabbing recipe ...</div>')
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
    await ws.send_text(f'<div id="recipe-content" hx-swap-oob="true">{markdown(recipe)}</div>')
    await ws.send_text('<div id="recipe-from-youtube-ws" hx-swap-oob="true"</div>')

    await ws.close()


app = Starlette(
    routes=[
        Route("/", homepage),
        Route("/youtube", youtube, methods=["POST"]),
        WebSocketRoute("/recipe-from-youtube", recipe_from_youtube),
        Mount("/assets", app=StaticFiles(directory="assets"), name="assets")
    ],
)
