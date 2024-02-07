import functools
import io
from typing import Any, Awaitable, Callable

from jinja2 import Environment, FileSystemLoader, select_autoescape
from starlette.applications import Starlette
from starlette.background import BackgroundTask
from starlette.datastructures import UploadFile
from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, RedirectResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from app import config
from domain.llm_service import LLMService
from domain.repository import RecipeVectorRepository
from domain.services import create_recipe, search_recipes


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
    n = min(20, int(request.query_params.get("n") or 5))
    recipes = await search_recipes(
        content,
        repository=app.state.repo,
        llm=app.state.llm,
        n=n,
    )
    return TEMPLATES.get_template("recipe-list.html").render(recipes=recipes)


@aHTMLResponse
async def create_page(request: Request) -> str:
    description = request.query_params.get("description", "")
    return TEMPLATES.get_template("create.html").render(description=description)


async def create(request: Request) -> HTMLResponse | RedirectResponse:
    match request.method.lower():
        case "get":
            description = request.query_params.get("description", "")
            return HTMLResponse(
                TEMPLATES.get_template("create.html").render(description=description)
            )
        case "post":
            async with request.form() as form:
                if "content" in form:
                    description = str(form.get("content", ""))
                else:
                    description = str(form.get("description", ""))
                image_files: list[bytes] = []
                for image in form.getlist("images"):
                    assert isinstance(image, UploadFile)
                    if image.size:
                        # Read these because otherwise trying to do stuff on a file
                        # handle that does not exist.
                        image_files.append(await image.read())

            repo: RecipeVectorRepository = request.app.state.repo
            llm: LLMService = request.app.state.llm
            task = BackgroundTask(
                create_recipe,
                description=description,
                images=[io.BytesIO(i) for i in image_files],
                repository=repo,
                llm=llm,
            )
            # notifications = [
            #     """
            #     <div class="alert alert-success alert-dismissible fade show" role="alert">
            #       <strong>Holy guacamole!</strong> That recipe is in the oven for a couple of minutes ...
            #       <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            #     </div>
            #     """
            # ]
            return RedirectResponse("/", status_code=303, background=task)
        case _:
            raise ValueError("Unsupported method.")


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
        Route("/create", create, methods=["GET", "POST"]),
        Route("/recipes/", search),
        Route("/recipes/{id}", recipe_detail),
        Route("/favicon.ico", favicon),
        Mount("/assets", StaticFiles(directory="assets")),
    ],
)

app.state.llm = LLMService()
app.state.repo = RecipeVectorRepository()
