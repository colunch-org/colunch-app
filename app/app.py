import functools
from typing import Any, Awaitable, Callable
from urllib.parse import urlencode

from jinja2 import Environment, FileSystemLoader, select_autoescape
from jinja2.utils import urlize
from markupsafe import Markup
from pinecone.utils.user_agent import urllib3
from starlette.applications import Starlette
from starlette.background import BackgroundTask
from starlette.datastructures import UploadFile
from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse
from starlette.routing import Mount, Route, WebSocketRoute
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocket

from app import config
from domain.llm_service import LLMService
from domain.repository import RecipeVectorRepository
from domain.services import (
    create_recipe,
    search_recipes,
    store_recipe,
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


async def favicon(request: Request) -> FileResponse:
    return FileResponse(CONFIG.images_dir / "favicon.ico")


@aHTMLResponse
async def homepage(request: Request) -> str:
    return TEMPLATES.get_template("index.html").render()


@aHTMLResponse
async def search(request: Request) -> str:
    content = request.query_params["content"]
    n = min(20, int(request.query_params.get("n") or 10))
    recipes = await search_recipes(
        content,
        repository=app.state.repo,
        llm=app.state.llm,
        n=n,
    )
    return TEMPLATES.get_template("recipe-list.html").render(recipes=recipes)


async def create(request: Request) -> HTMLResponse:
    async with request.form() as form:
        if "content" in form:
            description = str(form.get("content", ""))
        else:
            description = str(form.get("description", ""))
        images = form.get("images", [])
    repo: RecipeVectorRepository = request.app.state.repo
    llm: LLMService = request.app.state
    task = BackgroundTask(
        create_recipe,
        description=description,
        images=images,
        repository=repo,
        llm=llm,
    )
    html = """
<div class="alert alert-success alert-dismissible fade show" role="alert">
  <strong>Holy guacamole!</strong> That recipe is in the oven for a couple of minutes ...
  <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
</div>
    """
    return HTMLResponse(html, background=task)


@aHTMLResponse
async def recipe_detail(request: Request) -> str:
    id = request.path_params["id"]
    repo: RecipeVectorRepository = request.app.state.repo
    recipe = await repo.get(id)
    return TEMPLATES.get_template("recipe-detail.html").render(recipe=recipe)


app = Starlette(
    debug=True if CONFIG.env == config.Env.local else False,
    routes=[
        Route("/", homepage),
        Route("/create", create, methods=["POST"]),
        Route("/recipes/", search),
        Route("/recipes/{id}", recipe_detail),
        Route("/favicon", favicon),
        Mount("/assets", StaticFiles(directory="assets")),
    ],
)

app.state.llm = LLMService()
app.state.repo = RecipeVectorRepository()
