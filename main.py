from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route


async def homepage(request):
    return PlainTextResponse("Hello, World from CoLunch!")


app = Starlette(
    routes=[
        Route("/", homepage),
    ],
)
