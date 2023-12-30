import asyncio
from enum import Enum
from pathlib import Path
from urllib.parse import urlencode
import uuid

import bs4
import httpx
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

        with open(html_dir / "recipe-method.html") as f:
            self.recipe_method = f.read()

        with open(html_dir / "empty-recipe-method.html") as f:
            self.empty_recipe_method = f.read()

        with open(html_dir / "youtube-url-div.html") as f:
            self.youtube_url_form = f.read()

        with open(html_dir / "empty-youtube-url-div.html") as f:
            self.empty_youtube_url_form = f.read()

        with open(html_dir / "youtube-url-ws.html") as f:
            self.youtube_url_ws = f.read()

        with open(html_dir / "webpage-url-div.html") as f:
            self.webpage_url_form = f.read()

        with open(html_dir / "empty-webpage-url-div.html") as f:
            self.empty_webpage_url_form = f.read()

        with open(html_dir / "webpage-url-ws.html") as f:
            self.webpage_url_ws = f.read()

        with open(html_dir / "images-div.html") as f:
            self.images_form = f.read()

        with open(html_dir / "empty-images-div.html") as f:
            self.empty_images_form = f.read()

        with open(html_dir / "images-ws.html") as f:
            self.images_ws = f.read()


HTML = Html()


async def homepage(request: Request) -> HTMLResponse:
    return HTMLResponse(HTML.index.format(recipe_method=HTML.recipe_method))


async def description_form(request: Request) -> HTMLResponse:
    """Div containing the description form."""
    ...


async def description(request: Request) -> HTMLResponse:
    """Div containing the description websocket connection."""
    ...


async def recipe_from_description(ws: WebSocket) -> None:
    await ws.accept()

    await ws.close()


async def webpage_url_form(request: Request) -> HTMLResponse:
    """Div containing the webpage form."""
    return HTMLResponse(
        f"""
        {HTML.webpage_url_form.format(preferences=HTML.preferences)}
        {HTML.empty_recipe_method}
        """
    )


async def webpage(request: Request) -> HTMLResponse:
    """Div containing the webpage websocket connection."""
    async with request.form() as form:
        print(form)
        print(dict(form.items()))
        url = form.get("webpage-url")
        if not isinstance(url, str):
            return HTMLResponse("URL not a string.")
    params = urlencode(
        {
            "webpage-url": url,
            "servings": form.get("servings", ""),
            "time": form.get("time", ""),
            "vegetarian": form.get("vegetarian", ""),
            "vegan": form.get("vegan", ""),
            "gluten": form.get("gluten", ""),
        }
    )
    return HTMLResponse(
        f"{HTML.webpage_url_ws.format(url=params)}{HTML.empty_webpage_url_form}"
    )


async def recipe_from_webpage(ws: WebSocket) -> None:
    url = ws.query_params["webpage-url"]
    print(url)
    content = ""
    await ws.accept()

    await ws.send_text(
        f'<div id="recipe-content" hx-swap-oob="true">Grabbing content for {url} ...</div>'
    )
    try:
        resp = await httpx.AsyncClient().get(url)
        resp.raise_for_status
        text = resp.text
    except Exception as e:
        print(e)
        await ws.send_text(
            f'<div id="recipe-content" hx-swap-oob="true">Could not fetch {url}</div>'
        )
    else:
        soup = bs4.BeautifulSoup(text, features="html.parser")
        content = soup.text

        await ws.send_text(
            f"""
            <div id="recipe-content" hx-swap-oob="true">
            <div>Grabbing recipe from the content ...</div>
            <br/>
            <div>{content}</div>
            </div>
            """
        )

        prompt = Prompt(
            servings=float(ws.query_params.get("servings", 4)),
            time=float(ws.query_params.get("time", 10) or 10),
            vegetarian=bool(ws.query_params.get("vegetarian")),
            vegan=bool(ws.query_params.get("vegan")),
            gluten=bool(ws.query_params.get("gluten")),
        )

        print(f"###\n{prompt}\n###")

        messages = [ChatMsg(role="system", content=prompt)]
        msg = f"Webpage content: {content}"
        recipe = await Chat(messages=messages).chat(msg)
        await ws.send_text(
            f"""<div id="recipe-content" hx-swap-oob="true">
            <div>{markdown(recipe)}</div>
            <br/>
            <div>From the content ...</div>
            <div>{content}</div>
            """
        )
        await ws.send_text('<div id="recipe-from-webpage-ws" hx-swap-oob="true"></div>')

    await ws.close()


async def youtube_url_form(request: Request) -> HTMLResponse:
    """Div containing the youtube url form."""
    return HTMLResponse(
        f"""
        {HTML.youtube_url_form.format(preferences=HTML.preferences)}
        {HTML.empty_recipe_method}
        """
    )


async def youtube(request: Request) -> HTMLResponse:
    """Div containing the youtube url websocket connection."""
    async with request.form() as form:
        print(form)
        url = form.get("youtube-url")
    if not isinstance(url, str):
        return HTMLResponse("URL not a string.")
    params = urlencode(
        {
            "youtube-url": url,
            "servings": form.get("servings", ""),
            "time": form.get("time", ""),
            "vegetarian": form.get("vegetarian", ""),
            "vegan": form.get("vegan", ""),
            "gluten": form.get("gluten", ""),
        }
    )
    return HTMLResponse(
        f"{HTML.youtube_url_ws.format(url=params)}{HTML.empty_youtube_url_form}"
    )


async def recipe_from_youtube(ws: WebSocket) -> None:
    """Youtube url websocket."""
    url = ws.query_params["youtube-url"]
    await ws.accept()
    # check is valid
    # return a red input box or notification or something
    yt = YouTube(url)

    # await ws.send_text('<div id="youtube-url-div" hx-swap-oob="true"></div>')

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
    prompt = Prompt(
        servings=float(ws.query_params.get("servings", 4)),
        time=float(ws.query_params.get("time", 10) or 10),
        vegetarian=bool(ws.query_params.get("vegetarian")),
        vegan=bool(ws.query_params.get("vegan")),
        gluten=bool(ws.query_params.get("gluten")),
    )
    messages = [ChatMsg(role="system", content=prompt)]
    msg = f"Transcript: {translation}"
    recipe = await Chat(messages=messages).chat(msg)
    await ws.send_text(
        f"""<div id="recipe-content" hx-swap-oob="true">
        <div>{markdown(recipe)}</div>
        <br/>
        <div>From the transcript ...</div>
        <div>{translation}</div>
        """
    )
    await ws.send_text('<div id="recipe-from-youtube-ws" hx-swap-oob="true"></div>')

    await ws.close()


async def images_div(request: Request) -> HTMLResponse:
    return HTMLResponse(f"{HTML.images_form}{HTML.empty_recipe_method}")


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
    params = urlencode({"images": [str(i) for i in img_paths]}, doseq=True)
    return HTMLResponse(
        f"{HTML.images_ws.format(images=params)}{HTML.empty_images_form}"
    )


async def recipe_from_images(ws: WebSocket) -> None:
    img_paths = ws.query_params.getlist("images")
    img_paths = [Path(i) for i in img_paths]

    await ws.accept()
    # await ws.send_text('<div id="images-div" hx-swap-oob="true"></div>')

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
        Route("/webpage-div", webpage_url_form, methods=["GET"]),
        Route("/webpage", webpage, methods=["POST"]),
        WebSocketRoute("/recipe-from-webpage", recipe_from_webpage),
        Route("/images-div", images_div, methods=["GET"]),
        Route("/images", images, methods=["POST"]),
        WebSocketRoute("/recipe-from-images", recipe_from_images),
        Mount("/assets", app=StaticFiles(directory="assets"), name="assets"),
    ],
)
