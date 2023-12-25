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
    print(url)
    ws = f"""
    <div
      id="recipe-from-images-ws"
      hx-swap-oob="true"
      hx-ext="ws"
      ws-connect="/recipe-from-images?{url}"
    ></div>
    """
    return HTMLResponse(ws)


async def recipe_from_images(ws: WebSocket) -> None:
    img_paths = ws.query_params.getlist("images")
    img_paths = [Path(i) for i in img_paths]
    print(img_paths)

    prompt = (
        "You are a world class assistant for listing cooking ingredients in images and, "
        "where it appears one or more of the images contains a finished dish, "
        "providing the preparation steps, as well as required finishing steps, "
        "to achieve the finished dish including a likely "
        "amount of time each step will take where appropriate. "
        "Ingredients should include quanties approproiate for the recipe. "
        "Assume the images all relate to the same recipe unless explicitly told otherwise. "
        "Do not tell me the utensils or what the ingredients are inside or on top of "
        "but use them to help identify the ingredients. "
        "Where you are unsure, you can use other ingredients likely to be "
        "paired with the identified ingredients to help inform the list. "
        "Where you are still unsure, provide the three most likely options."
        "Format your response in correct markdown but do not tell me the markdown is correct. "
    )

    await ws.accept()
    # send a blank input back
    await ws.send_text(
        """    
        <input
        id="images"
        name="images"
        type="file"
        class="form-control"
        hx-swap-oob="true"
        multiple
        ></input>
        """
    )

    content: list[Content] = [TextContent(prompt)]
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


async def recipe_from_youtube(ws: WebSocket) -> None:
    url = ws.query_params["youtube-url"]
    await ws.accept()
    # check is valid
    # return a red input box or notification or something
    yt = YouTube(url)

    await ws.send_text(
        """
        <input
          id="youtube-url"
          name="youtube-url"
          type="text"
          class="form-control"
          placeholder="YouTube url ..."
          hx-post="/youtube"
          hx-swap-oob="true"
        ></input>
    """
    )

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
    prompt = [
        ChatMsg(
            role="system",
            content=(
                "You are a world class assistant for summarising cooking video transcripts. "
            ),
        ),
    ]

    msg = (
        "List the ingredients and preparation steps for each recipe in the "
        "following transcript. Each preparation step should make sense in isolation. "
        "If you think there are corrections to be made, make them in place but identify "
        "where corrections have been made. "
        "Include notes at the end of the response and suggest three similar recipes "
        "with a brief descriptions."
        "Format your response in correct markdown but do not tell me the markdown is correct. "
        f"Transcript: {translation}"
    )

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


app = Starlette(
    routes=[
        Route("/", homepage),
        Route("/youtube", youtube, methods=["POST"]),
        WebSocketRoute("/recipe-from-youtube", recipe_from_youtube),
        Route("/images", images, methods=["POST"]),
        WebSocketRoute("/recipe-from-images", recipe_from_images),
        Mount("/assets", app=StaticFiles(directory="assets"), name="assets"),
    ],
)
