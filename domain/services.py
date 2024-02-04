import io
import uuid

from domain.llm_service import LLMService
from domain.models import Recipe
from domain.repository import RecipeVectorRepository


async def store_recipe(
    recipe: Recipe,
    *,
    repository: RecipeVectorRepository,
    llm: LLMService,
) -> None:
    vector = await llm.embeddings(recipe)
    await repository.add(recipe=recipe, vector=vector)


async def search_recipes(
    content: Recipe | str,
    *,
    repository: RecipeVectorRepository,
    llm: LLMService,
    n: int = 3,
) -> list[Recipe]:
    if isinstance(content, Recipe):
        content = content.content
    vector = await llm.embeddings(content)
    return await repository.search(vector, n=n)


async def create_recipe(
    *,
    description: str,
    images: list[io.BufferedReader],
    repository: RecipeVectorRepository,
    llm: LLMService,
) -> Recipe:
    content = await llm.create_recipe(description=description, images=images)
    name = await llm.recipe_name(content)
    summary = await llm.recipe_summary(content)
    recipe = Recipe(id=uuid.uuid4().hex, name=name, summary=summary, content=content)
    await store_recipe(recipe, repository=repository, llm=llm)
    return recipe
