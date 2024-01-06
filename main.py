import contextlib
from pathlib import Path
from urllib.parse import urlencode
import uuid

from rich import print
from starlette.applications import Starlette
from starlette.datastructures import UploadFile
from starlette.requests import Request
from starlette.responses import HTMLResponse
from starlette.routing import Mount, Route, WebSocketRoute
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocket

import config
import db
import html_templates as html
import services


# https://www.youtube.com/watch?v=UfOQyurFHAo
# https://www.youtube.com/watch?v=S1NRL9-xOdU


CONFIG = config.Config()


HTML = html.Html()


@contextlib.asynccontextmanager
async def lifespan(app: Starlette):
    await db.db.connect()
    try:
        await db.create_db()
    except:
        print("Could not create DB.")
    yield
    await db.db.disconnect()
    # await db.db.execute(  # pyright: ignore[reportUnknownMemberType]
    #     "DROP TABLE Recipes"
    # )


async def homepage(request: Request) -> HTMLResponse:
    recipes = await db.RecipesRepository(db.db).list()
    recipes_html = "<ul>"
    for recipe in recipes:
        print(recipe)
        recipes_html += f'<li><a href="/recipes/{recipe.id}">{recipe.name}</a></li>'
    recipes_html += "</ul>"
    return HTMLResponse(
        HTML.index.format(
            recipe_method=HTML.recipe_method,
            recipes=recipes_html,
        )
    )


async def recipe_detail(request: Request) -> HTMLResponse:
    id = request.path_params["id"]
    recipe = await db.RecipesRepository(db.db).get(id)
    return HTMLResponse(recipe.html)


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
        url = form.get("webpage-url")
        if not isinstance(url, str):
            return HTMLResponse("URL not a string.")
    params = urlencode({"webpage-url": url})
    return HTMLResponse(
        f"{HTML.webpage_url_ws.format(url=params)}{HTML.empty_webpage_url_form}"
    )


async def recipe_from_webpage(ws: WebSocket) -> None:
    url = ws.query_params["webpage-url"]
    await ws.accept()
    await ws.send_text(
        f'<div id="recipe-content" hx-swap-oob="true">Grabbing content for {url} ...</div>'
    )
    content = ""

    try:
        content = await services.text_from_webpage(url)
    except Exception as e:
        print(repr(e))
        await ws.send_text(
            f'<div id="recipe-content" hx-swap-oob="true">Could not fetch {url}</div>'
        )
    else:
        await ws.send_text(
            f"""
            <div id="recipe-content" hx-swap-oob="true">
            <div>Grabbing recipe from the content ...</div>
            <br/>
            <div>{content}</div>
            </div>
            """
        )

        recipe = await services.recipe_from_webpage_text(content)
        await ws.send_text(
            f"""<div id="recipe-content" hx-swap-oob="true">
            <div>{recipe.html}</div>
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
    await ws.send_text(
        f'<div id="recipe-content" hx-swap-oob="true">Grabbing audio for {url} ...</div>'
    )

    audio_path = await services.audio_from_youtube_url(url)

    await ws.send_text(
        '<div id="recipe-content" hx-swap-oob="true">Grabbing transcript ...</div>'
    )
    translation = await services.transcript_from_audio(audio_path)

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
    recipe = await services.recipe_from_transcript(translation)
    await ws.send_text(
        f"""<div id="recipe-content" hx-swap-oob="true">
        <div>{recipe.html}</div>
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
        for fobj in form.getlist("images"):
            assert isinstance(fobj, UploadFile)
            contents = await fobj.read()
            ext = Path(fobj.filename).suffix if fobj.filename else ".jpeg"
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
    await ws.send_text(
        '<div id="recipe-content" hx-swap-oob="true">Grabbing recipe ...</div>'
    )

    recipe = await services.recipe_from_images(img_paths)
    await ws.send_text(
        f"""<div id="recipe-content" hx-swap-oob="true">
        <div>{recipe.html}</div>
        </div>
        """
    )

    await ws.send_text('<div id="recipe-from-images-ws" hx-swap-oob="true"</div>')

    await ws.close()


app = Starlette(
    routes=[
        Route("/", homepage),
        Route("/recipes/{id:str}", recipe_detail),
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
    lifespan=lifespan,
)
