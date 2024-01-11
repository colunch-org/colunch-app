from jinja2 import Environment
from markdown2 import (  # pyright: ignore[reportMissingTypeStubs]
    markdown,  # pyright: ignore[reportUnknownVariableType]
)
from markupsafe import Markup

from app.domain.models import Recipe


class RecipeDetail:
    def __init__(
        self,
        recipe: Recipe,
        *,
        environment: Environment,
        template_name: str = "recipe-detail.html",
    ) -> None:
        self.recipe = recipe
        self.env = environment
        self.name = template_name

    @property
    def title(self) -> str:
        return self.recipe.name

    @property
    def content(self) -> str:
        return Markup(markdown(self.recipe.text))

    def render(self) -> str:
        return self.env.get_template(self.name).render(recipe=self)
