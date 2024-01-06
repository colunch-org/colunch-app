from uuid import uuid4
from databases import Database
from databases.interfaces import Record

import config
from models import Recipe


CONFIG = config.Config()


CREATE_RECIPES_TABLE = """
CREATE TABLE Recipes (id VARCHAR(64) PRIMARY KEY, text VARCHAR(3000), name VARCHAR(256))
"""


CREATE_RECIPE = """
INSERT INTO Recipes(id, text, name) VALUES (:id, :text, :name)
"""


GET_RECIPE = "SELECT * FROM Recipes WHERE id = :id"


LIST_RECIPES = "SELECT * FROM Recipes"


db = Database(CONFIG.db_url)


class RecipeNotFound(Exception):
    pass


async def create_db() -> None:
    await db.execute(  # pyright: ignore[reportUnknownMemberType]
        query=CREATE_RECIPES_TABLE
    )


async def create_recipe(text: str, name: str) -> str:
    id = uuid4().hex
    await db.execute(  # pyright: ignore[reportUnknownMemberType]
        CREATE_RECIPE, values={"id": id, "text": text, "name": name}
    )
    return id


async def get_recipe(id: str) -> Record:
    result = await db.fetch_one(  # pyright: ignore[reportUnknownMemberType]
        GET_RECIPE, values={"id": id}
    )

    if result is None:
        raise RecipeNotFound(f"{id}")

    return result


async def list_recipes() -> list[Record]:
    result = await db.fetch_all(  # pyright: ignore[reportUnknownMemberType]
        LIST_RECIPES
    )
    return result


class RecipesRepository:
    """Recipes repository."""

    def __init__(self, db: Database) -> None:
        self.db = db

    async def create(self, text: str, name: str) -> Recipe:
        # transaction here or in fancy async with
        id = await create_recipe(text=text, name=name)
        return Recipe(id=id, name=name, text=text)

    async def get(self, id: str) -> Recipe:
        result = await get_recipe(id)
        return Recipe(id=result["id"], name=result["name"], text=result["text"])

    async def list(self) -> tuple[Recipe, ...]:
        result = await list_recipes()
        recipes = [Recipe(id=r["id"], name=r["name"], text=r["text"]) for r in result]
        return tuple(recipes)
