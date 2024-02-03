import functools
from typing import Any, Awaitable, Callable

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup
from starlette.applications import Starlette
from starlette.datastructures import UploadFile
from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse
from starlette.routing import Mount, Route, WebSocketRoute
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocket

from app import config


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


def aHTMLResponse(route: Callable[..., Awaitable[str | tuple[str, int]]]):
    @functools.wraps(route)
    async def wrapper(*args: Any, **kwargs: Any) -> HTMLResponse:
        resp = await route(*args, **kwargs)
        if not isinstance(resp, tuple):
            html, code = resp, 200
        else:
            html, code = resp
        return HTMLResponse(html, status_code=code)

    return wrapper


@aHTMLResponse
async def homepage(request: Request) -> str:
    recipes = ...
    index = TEMPLATES.get_template("index.html")
    recipe_list = TEMPLATES.get_template("recipe-list.html")
    recipe_method = TEMPLATES.get_template("recipe-method.html")
    return index.render(
        recipe_method=Markup(recipe_method.render()),
        recipes=Markup(recipe_list.render(recipes=recipes)),
    )


async def favicon(request: Request) -> FileResponse:
    return FileResponse(CONFIG.images_dir / "favicon.ico")


@aHTMLResponse
async def recipe_detail(request: Request) -> str:
    id = request.path_params["id"]
    recipe = {"id": id, "name": "Nigle", "summary": "Thornberry", "content": "Smashing"}
    return TEMPLATES.get_template("recipe-detail.html").render(
        name=recipe.get("name", ""),
        summary=recipe.get("summary", ""),
        content=Markup(recipe.get("content", "")),
    )
