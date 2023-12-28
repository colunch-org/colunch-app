import asyncio
from enum import Enum
from pathlib import Path
from urllib.parse import urlencode
import uuid

from markdown2 import (  # pyright: ignore[reportMissingTypeStubs]
    markdown,  # pyright: ignore[reportUnknownVariableType]
)
from pydantic_settings import BaseSettings
from pytube import YouTube  # pyright: ignore[reportMissingTypeStubs]
from starlette.applications import Starlette
from starlette.datastructures import UploadFile
from starlette.requests import Request
from starlette.responses import HTMLResponse
from starlette.routing import Mount, Route, WebSocketRoute
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocket

from aopenai import AudioTranslation, Chat, ChatMsg, Content, ImgContent, TextContent
from prompts import Prompt


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


class Html:
    def __init__(self, html_dir: Path | None = None) -> None:
        html_dir = CONFIG.html_dir if html_dir is None else html_dir

        with open(html_dir / "index.html") as f:
            self.index = f.read()

        with open(html_dir / "preferences.html") as f:
            self.preferences = f.read()

        with open(html_dir / "youtube-url-div.html") as f:
            self.youtube_url_form = f.read()

        with open(html_dir / "youtube-url-ws.html") as f:
            self.youtube_url_ws = f.read()

        with open(html_dir / "images-div.html") as f:
            self.images_form = f.read()

        with open(html_dir / "images-ws.html") as f:
            self.images_ws = f.read()


HTML = Html()


async def homepage(request: Request) -> HTMLResponse:
    return HTMLResponse(HTML.index)


async def youtube_url_form(request: Request) -> HTMLResponse:
    """Div containing the youtube url form."""
    return HTMLResponse(HTML.youtube_url_form)


async def youtube(request: Request) -> HTMLResponse:
    """Div containing the youtube url websocket connection."""
    async with request.form() as form:
        print(form)
        url = form.get("youtube-url")
    if not isinstance(url, str):
        return HTMLResponse("URL not a string.")
    url = urlencode({"youtube-url": url})
    return HTMLResponse(HTML.youtube_url_ws.format(url=url))


async def recipe_from_youtube(ws: WebSocket) -> None:
    """Youtube url websocket."""
    url = ws.query_params["youtube-url"]
    await ws.accept()
    # check is valid
    # return a red input box or notification or something
    yt = YouTube(url)

    await ws.send_text(HTML.youtube_url_form)

    await ws.send_text(
        f'<div id="recipe-content" hx-swap-oob="true">Grabbing audio for {url} ...</div>'
    )
    await asyncio.sleep(0)
    audio = await asyncio.to_thread(yt.streams.get_audio_only)
    await asyncio.sleep(0)

    if not audio:
        raise ValueError("No audio.")

    audio_path = Path(f"{uuid.uuid4().hex}.mp4")

    await asyncio.to_thread(audio.download, filename=str(audio_path))
    await asyncio.sleep(0)

    await ws.send_text(
        '<div id="recipe-content" hx-swap-oob="true">Grabbing transcript ...</div>'
    )
    with open(audio_path, "rb") as audio_file:
        translation = await AudioTranslation().translate(audio=audio_file)

    audio_path.unlink()

    await ws.send_text(
        f"""
        <div id="recipe-content" hx-swap-oob="true">
        <div>Grabbing recipe from the transcript ...</div>
        <br/>
        <div>{translation}</div>
        </div>
        """
    )
    prompt = [ChatMsg(role="system", content=Prompt())]
    msg = f"Transcript: {translation}"
    recipe = await Chat(messages=prompt).chat(msg)
    await ws.send_text(
        f"""<div id="recipe-content" hx-swap-oob="true">
        <div>{markdown(recipe)}</div>
        <br/>
        <div>From the transcript ...</div>
        <div>{translation}</div>
        """
    )
    await ws.send_text('<div id="recipe-from-youtube-ws" hx-swap-oob="true"</div>')

    await ws.close()


async def images_form(request: Request) -> HTMLResponse:
    return HTMLResponse(HTML.images_form)


async def images(request: Request) -> HTMLResponse:
    img_paths: list[Path] = []
    async with request.form() as form:
        print(form.getlist("images"))
        for fobj in form.getlist("images"):
            assert isinstance(fobj, UploadFile)
            contents = await fobj.read()
            ext = Path(fobj.filename).suffix if fobj.filename else ".jpeg"
            print(fobj.filename, ext)
            img_path = Path(f"{uuid.uuid4().hex}{ext}")
            with open(img_path, "wb") as f:
                f.write(contents)
            img_paths.append(img_path)
    url = urlencode({"images": [str(i) for i in img_paths]}, doseq=True)
    return HTMLResponse(HTML.youtube_url_ws.format(url=url))


async def recipe_from_images(ws: WebSocket) -> None:
    img_paths = ws.query_params.getlist("images")
    img_paths = [Path(i) for i in img_paths]

    await ws.accept()
    # send a blank input back
    await ws.send_text(HTML.images_ws)

    content: list[Content] = [TextContent(Prompt())]
    for img_path in img_paths:
        content.append(ImgContent.from_path(img_path))
        img_path.unlink()

    await ws.send_text(
        '<div id="recipe-content" hx-swap-oob="true">Grabbing recipe ...</div>'
    )
    chat = Chat(model="gpt-4-vision-preview")

    recipe = await chat.chat(ChatMsg(role="user", content=content))
    await ws.send_text(
        f"""<div id="recipe-content" hx-swap-oob="true">
        <div>{markdown(recipe)}</div>
        <br/>
        """
    )

    await ws.send_text('<div id="recipe-from-images-ws" hx-swap-oob="true"</div>')

    await ws.close()


app = Starlette(
    routes=[
        Route("/", homepage),
        Route("/youtube-div", youtube_url_form, methods=["GET"]),
        Route("/youtube", youtube, methods=["POST"]),
        WebSocketRoute("/recipe-from-youtube", recipe_from_youtube),
        Route("/images-input-div", images_form, methods=["GET"]),
        Route("/images", images, methods=["POST"]),
        WebSocketRoute("/recipe-from-images", recipe_from_images),
        Mount("/assets", app=StaticFiles(directory="assets"), name="assets"),
    ],
)
