import contextlib
from pathlib import Path
from urllib.parse import urlencode
import uuid

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup
from rich import print
from starlette.applications import Starlette
from starlette.datastructures import UploadFile
from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse
from starlette.routing import Mount, Route, WebSocketRoute
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocket

from app import (
    config,
    db,
    services,
)


# https://www.youtube.com/watch?v=UfOQyurFHAo
# https://www.youtube.com/watch?v=S1NRL9-xOdU


CONFIG = config.Config()


# Async?
# Looks like we cache stuff
# Can always copy this, subclass BaseLoader, and make it do what I want.
TEMPLATES = Environment(
    loader=FileSystemLoader(CONFIG.html_dir),
    autoescape=select_autoescape(),
)


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
    index = TEMPLATES.get_template("index.html")
    recipe_list = TEMPLATES.get_template("recipe-list.html")
    recipe_method = TEMPLATES.get_template("recipe-method.html")
    return HTMLResponse(
        index.render(
            recipe_method=Markup(recipe_method.render()),
            recipes=Markup(recipe_list.render(recipes=recipes)),
        )
    )


async def favicon(request: Request) -> FileResponse:
    return FileResponse(CONFIG.images_dir / "favicon.ico")


async def recipe_detail(request: Request) -> HTMLResponse:
    id = request.path_params["id"]
    recipe = await db.RecipesRepository(db.db).get(id)
    recipe_detail = TEMPLATES.get_template("recipe-detail.html")
    return HTMLResponse(
        recipe_detail.render(
            title=recipe.name,
            text=Markup(recipe.html),
        )
    )


async def description_form(request: Request) -> HTMLResponse:
    """Div containing the description form."""
    return HTMLResponse(
        f"""
        {TEMPLATES.get_template("description-div.html").render()}
        {TEMPLATES.get_template("empty-recipe-method.html").render()}
        """
    )


async def description(request: Request) -> HTMLResponse:
    """Div containing the description websocket connection."""
    async with request.form() as form:
        query_params = form.get("description")
        if not isinstance(query_params, str):
            return HTMLResponse("Description not a string.")
    query_params = urlencode({"description": query_params})
    return HTMLResponse(
        f"""
        {TEMPLATES.get_template("description-ws.html").render(query_params=query_params)}
        {TEMPLATES.get_template("empty-description-div.html").render()}
    """
    )


async def recipe_from_description(ws: WebSocket) -> None:
    description = ws.query_params["description"]
    await ws.accept()
    await ws.send_text(
        f'<div id="recipe-content" hx-swap-oob="true">Grabbing recipe for "{description}" ...</div>'
    )
    recipe = await services.recipe_from_description(description)
    await ws.send_text(
        f"""<div id="recipe-content" hx-swap-oob="true">
        <div>{recipe.html}</div>
        <br/>
        <div>From the description ...</div>
        <div>{description}</div>
        """
    )
    await ws.send_text('<div id="recipe-from-webpage-ws" hx-swap-oob="true"></div>')

    await ws.close()


async def webpage_url_form(request: Request) -> HTMLResponse:
    """Div containing the webpage form."""
    return HTMLResponse(
        f"""
        {TEMPLATES.get_template("webpage-url-div.html").render()}
        {TEMPLATES.get_template("empty-recipe-method.html").render()}
        """
    )


async def webpage(request: Request) -> HTMLResponse:
    """Div containing the webpage websocket connection."""
    async with request.form() as form:
        query_params = form.get("webpage-url")
        if not isinstance(query_params, str):
            return HTMLResponse("URL not a string.")
    query_params = urlencode({"webpage-url": query_params})
    return HTMLResponse(
        f"""
        {TEMPLATES.get_template("webpage-url-ws.html").render(query_params=query_params)}
        {TEMPLATES.get_template("empty-webpage-url-div.html").render()}
    """
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
        {TEMPLATES.get_template('youtube-url-div.html').render()}
        {TEMPLATES.get_template("empty-recipe-method.html").render()}
        """
    )


async def youtube(request: Request) -> HTMLResponse:
    """Div containing the youtube url websocket connection."""
    async with request.form() as form:
        print(form)
        url = form.get("youtube-url")
    if not isinstance(url, str):
        return HTMLResponse("URL not a string.")
    query_params = urlencode({"youtube-url": url})
    return HTMLResponse(
        f"""
        {TEMPLATES.get_template("youtube-url-ws.html").render(query_params=query_params)}
        {TEMPLATES.get_template("empty-youtube-url-div.html").render()}
    """
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
    return HTMLResponse(
        f"""
        {TEMPLATES.get_template("images-div.html").render()}
        {TEMPLATES.get_template("empty-recipe-method.html").render()}
        """
    )


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
    query_params = urlencode({"images": [str(i) for i in img_paths]}, doseq=True)
    return HTMLResponse(
        f"""
        {TEMPLATES.get_template("images-ws.html").render(query_params=query_params)}
        {TEMPLATES.get_template("empty-images-div.html")}
        """
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
        Route("/favicon.ico", favicon),
        Route("/recipes/{id:str}", recipe_detail),
        Route("/description-div", description_form),
        Route("/description", description, methods=["POST"]),
        WebSocketRoute("/recipe-from-description", recipe_from_description),
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
