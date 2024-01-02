from uuid import uuid4
from databases import Database

import config


CONFIG = config.Config()


CREATE_RECIPES_TABLE = """
CREATE TABLE Recipes (id VARCHAR(64) PRIMARY KEY, text VARCHAR(3000))
"""


CREATE_RECIPES = """
INSERT INTO Recipes(id, text) VALUES (:id, :text)
"""


db = Database(CONFIG.db_url)


async def create_db() -> None:
    await db.execute(  # pyright: ignore[reportUnknownMemberType]
        query=CREATE_RECIPES_TABLE
    )


async def create_recipe(text: str) -> None:
    await db.execute(  # pyright: ignore[reportUnknownMemberType]
        CREATE_RECIPES, values={"id": uuid4().hex, "text": text}
    )


class RecipesRepository:
    """Recipes repository."""
